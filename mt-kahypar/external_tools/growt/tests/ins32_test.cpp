/*******************************************************************************
 * tests/in_test.cpp
 *
 * basic insert and find test for more information see below
 *
 * Part of Project growt - https://github.com/TooBiased/growt.git
 *
 * Copyright (C) 2015-2016 Tobias Maier <t.maier@kit.edu>
 *
 * All rights reserved. Published under the BSD-2 license in the LICENSE file.
 ******************************************************************************/
#include <iostream>
#include <random>

#ifdef GROWT_RSS_MODE
#include <stdio.h>
static constexpr bool rss_mode = true;
size_t                get_rss()
{
    long  rss = 0L;
    FILE* fp  = NULL;
    if ((fp = fopen("/proc/self/statm", "r")) == NULL)
        return (size_t)0L; /* Can't open? */
    if (fscanf(fp, "%*s%ld", &rss) != 1)
    {
        fclose(fp);
        return (size_t)0L; /* Can't read? */
    }
    fclose(fp);
    return (size_t)rss;
}
#else
static constexpr bool rss_mode = false;
constexpr size_t      get_rss() { return 0; }
#endif

#include "utils/command_line_parser.hpp"
#include "utils/debug.hpp"
#include "utils/default_hash.hpp"
#include "utils/output.hpp"
#include "utils/pin_thread.hpp"
#include "utils/thread_coordination.hpp"

#include "tests/selection.hpp"

/*
 * This Test is meant to test the tables performance on uniform random inputs.
 * 0. Creating 2n random keys
 * 1. Inserting n elements (key, index) - the index can be used for validation
 * 2. Looking for n elements - using different keys (likely not finding any)
 * 3. Looking for the n inserted elements (hopefully finding all)
 *    (correctness test using the index)
 */

const static uint32_t range = (1ull << 30) - 1;
namespace otm               = utils_tm::out_tm;
namespace ttm               = utils_tm::thread_tm;
namespace dtm               = utils_tm::debug_tm;

using ins_config = table_config<uint32_t,
                                uint32_t,
                                utils_tm::hash_tm::default_hash,
                                allocator_type>;
using table_type = typename ins_config::table_type;

// using table_type = typename table_config<size_t,
//                                          size_t,
//                                          utils_tm::hash_tm::default_hash,
//                                          allocator_type>::table_type;

alignas(64) static table_type hash_table = table_type(0);
alignas(64) static uint32_t* keys;
alignas(64) static std::atomic_size_t current_block;
alignas(64) static std::atomic_size_t errors;


int generate_random(size_t n)
{
    std::uniform_int_distribution<uint32_t> dis(2, range);

    ttm::execute_blockwise_parallel(
        current_block, n, [&dis](size_t s, size_t e) {
            std::mt19937_64 re(s * 10293903128401092ull);

            for (size_t i = s; i < e; i++) { keys[i] = dis(re); }
        });

    return 0;
}

template <class Hash>
int fill(Hash& hash, size_t end)
{
    auto err = 0u;

    ttm::execute_parallel(current_block, end, [&hash, &err](size_t i) {
        auto key    = keys[i];
        auto output = hash.insert(key, i + 2);

        if (!output.second)
        {
            // Insertion failed? Possibly already inserted.
            dtm::if_debug("Warning: failed insertion");
            auto data = output.first;
            if (!(keys[(*data).second - 2] == key))
            {
                std::cout << "!" << std::flush;
                ++err;
            }
        }
    });

    errors.fetch_add(err, std::memory_order_relaxed);
    return 0;
}


template <class Hash>
int find_unsucc(Hash& hash, size_t end)
{
    auto err = 0u;

    ttm::execute_parallel(current_block, end, [&hash, &err](size_t i) {
        auto key = keys[i];

        auto data = hash.find(key);

        if (data != hash.end())
        {
            // Random key found (unexpected)
            dtm::if_debug("Warning: found one of the random keys");
            if (!(keys[(*data).second - 2] == key))
            {
                std::cout << "?" << std::flush;
                ++err;
            }
        }
    });

    errors.fetch_add(err, std::memory_order_relaxed);
    return 0;
}

template <class Hash>
int find_succ(Hash& hash, size_t end)
{
    auto err = 0u;

    ttm::execute_parallel(current_block, end, [&hash, &err](size_t i) {
        auto key = keys[i];

        auto data = hash.find(key);

        if (data == hash.end() || (*data).second != i + 2)
        {
            dtm::if_debug("Warning: can't find inserted key");

            if (!(keys[(*data).second - 2] == key))
            {
                std::cout << "!" << std::flush;
                ++err;
            }
        }
    });

    errors.fetch_add(err, std::memory_order_relaxed);
    return 0;
}

template <class ThreadType>
struct test_in_stages
{
    static int execute(ThreadType t, size_t n, size_t cap, size_t it)
    {
        utils_tm::pin_to_core(t.id);

        if (ThreadType::is_main) { keys = new uint32_t[2 * n]; }

        // STAGE0 Create Random Keys
        {
            if (ThreadType::is_main) current_block.store(0);
            t.synchronized(generate_random, 2 * n);
        }

        [[maybe_unused]] size_t start_rss = get_rss();

        for (size_t i = 0; i < it; ++i)
        {
            // STAGE 0.1
            t.synchronized(
                [cap](bool m) {
                    if (m) hash_table = table_type(cap);
                    return 0;
                },
                ThreadType::is_main);

            t.out << otm::width(5) << i << otm::width(5) << t.p
                  << otm::width(11) << n << otm::width(11) << cap << std::flush;

            t.synchronize();

            using handle_type = typename table_type::handle_type;
            handle_type hash  = hash_table.get_handle();


            // STAGE2 n Insertions
            {
                if (ThreadType::is_main) current_block.store(0);

                auto duration = t.synchronized(fill<handle_type>, hash, n);

                t.out << otm::width(12) << duration.second / 1000000.;
            }

            // STAGE3 n Finds Unsuccessful
            {
                if (ThreadType::is_main) current_block.store(n);

                auto duration =
                    t.synchronized(find_unsucc<handle_type>, hash, 2 * n);

                t.out << otm::width(12) << duration.second / 1000000.;
            }

            // STAGE4 n Finds Successful
            {
                if (ThreadType::is_main) current_block.store(0);

                auto duration = t.synchronized(find_succ<handle_type>, hash, n);

                t.out << otm::width(12) << duration.second / 1000000.;
                t.out << otm::width(12) << errors.load();
            }

            if constexpr (rss_mode)
            {
                t.out << otm::width(20) << get_rss() - start_rss;
            }

            if (ThreadType::is_main)
            {
                // errors.store(0);
                if (errors.exchange(0))
                {
                    /* currently do nothing */
                    // size_t counter = 0;
                    // for (auto it = hash.begin(); it != hash.end(); ++it)
                    // {
                    //     counter++;
                    // }
                    // t.out << " found " << counter << " elements";
                }
            }

            t.out << std::endl;

            // Some Synchronization
            t.synchronize();
        }

        if (ThreadType::is_main) { delete[] keys; }

        return 0;
    }
};



int main(int argn, char** argc)
{
    utils_tm::command_line_parser c{argn, argc};
    size_t                        n   = c.int_arg("-n", 10000000);
    size_t                        p   = c.int_arg("-p", 4);
    size_t                        cap = c.int_arg("-c", n);
    size_t                        it  = c.int_arg("-it", 5);
    if (!c.report()) return 1;

    otm::out() << otm::width(5) << "#i" << otm::width(5) << "p"
               << otm::width(11) << "n" << otm::width(11) << "cap"
               << otm::width(12) << "t_ins" << otm::width(12) << "t_find_-"
               << otm::width(12) << "t_find_+" << otm::width(12) << "errors"
               << "    " << ins_config::name() << std::endl;

    ttm::start_threads<test_in_stages>(p, n, cap, it);
    return 0;
}
