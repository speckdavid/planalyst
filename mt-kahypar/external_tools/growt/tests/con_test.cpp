/*******************************************************************************
 * tests/con_test.cpp
 *
 * basic contention test for more information see below
 *
 * Part of Project growt - https://github.com/TooBiased/growt.git
 *
 * Copyright (C) 2015-2016 Tobias Maier <t.maier@kit.edu>
 *
 * All rights reserved. Published under the BSD-2 license in the LICENSE file.
 ******************************************************************************/


#include <random>


#include "utils/command_line_parser.hpp"
#include "utils/default_hash.hpp"
#include "utils/output.hpp"
#include "utils/pin_thread.hpp"
#include "utils/thread_coordination.hpp"
#include "utils/zipf_keygen.hpp"

#include "data-structures/returnelement.hpp"

#include "example/update_fcts.hpp"

#include "tests/selection.hpp"

/*
 * This Test is meant to test the tables performance on uniform random inputs.
 * 0. Creating n random keys with zipf distribution
 * 1. Inserting n elements [1..n] (key, key)
 * 2. Looking for n elements - using different keys (likely not finding any)
 * 3. Looking for the n inserted elements (hopefully finding all)
 *    (correctness test using the index)
 */

namespace otm = utils_tm::out_tm;
namespace ttm = utils_tm::thread_tm;

using con_config = table_config<size_t, size_t, utils_tm::hash_tm::default_hash,
                                allocator_type>;
using table_type = typename con_config::table_type;

alignas(64) static table_type hash_table = table_type(0);
alignas(64) static uint64_t* keys;
alignas(64) static std::atomic_size_t current_block;
alignas(64) static std::atomic_size_t errors;
alignas(64) static utils_tm::zipf_generator zipf_gen;


int generate_random(size_t n)
{
    ttm::execute_blockwise_parallel(current_block, n, [](size_t s, size_t e) {
        std::mt19937_64 re(s * 10293903128401092ull);
        zipf_gen.generate(re, &keys[s], e - s);
    });

    return 0;
}

template <class Hash> int fill(Hash& hash, size_t n)
{
    auto err = 0u;

    ttm::execute_parallel(current_block, n, [&hash, &err](size_t i) {
        auto temp = hash.insert(i + 1, i + 1);
        if (!temp.second) ++err;
    });

    errors.fetch_add(err, std::memory_order_relaxed);
    return 0;
}


template <class Hash> int find_contended(Hash& hash, size_t n)
{
    auto err = 0u;

    ttm::execute_parallel(current_block, n, [&hash, &err](size_t i) {
        auto key = keys[i];

        auto it = hash.find(key);

        if (it == hash.end() || (*it).second != key) { ++err; }
    });

    errors.fetch_add(err, std::memory_order_relaxed);


    return 0;
}

template <class Hash> int update_contended(Hash& hash, size_t n)
{
    auto err = 0u;

    ttm::execute_parallel(current_block, n, [&hash, &err](size_t i) {
        auto key  = keys[i];
        auto temp = hash.update(key, growt::example::Overwrite(), i + 1);

        if (!temp.second) ++err;
    });

    errors.fetch_add(err, std::memory_order_relaxed);

    return 0;
}


template <class Hash> int val_update(Hash& hash, size_t n)
{
    auto err = 0u;

    ttm::execute_parallel(current_block, n, [&hash, &err, n](size_t i) {
        auto it = hash.find(i + 1);
        if (it == hash.end()) { ++err; }
        else
        {
            auto temp = (*it).second;
            if (temp != i + 1)
            {
                if (temp < 2 || temp > n + 1 || keys[temp - 1] != i + 1) ++err;
            }
        }
    });

    // std::cout << " " << err << std::flush;
    errors.fetch_add(err, std::memory_order_relaxed);
    return 0;
}

template <class ThreadType> struct test_in_stages
{

    static int
    execute(ThreadType t, size_t n, size_t cap, size_t it, double con)
    {

        utils_tm::pin_to_core(t.id);

        using handle_type = typename table_type::handle_type;

        if (ThreadType::is_main) { keys = new uint64_t[n]; }

        // STAGE0 Create Random Keys
        {
            if (ThreadType::is_main) current_block.store(0);
            t.synchronized(generate_random, n);
        }

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
                  << otm::width(11) << n << otm::width(11) << cap
                  << otm::width(7) << con << std::flush;

            // Needed for synchronization (main thread has finished set_up_hash)
            t.synchronize();

            handle_type hash = hash_table.get_handle();

            // STAGE2 n Insertions [2 .. n+1]
            {
                if (ThreadType::is_main) current_block.store(0);

                auto duration = t.synchronized(fill<handle_type>, hash, n);

                t.out << otm::width(12) << duration.second / 1000000.
                      << std::flush;
            }

            // STAGE3 n Cont Random Finds Successful
            {
                if (ThreadType::is_main) current_block.store(0);

                auto duration =
                    t.synchronized(find_contended<handle_type>, hash, n);

                t.out << otm::width(12) << duration.second / 1000000.
                      << std::flush;
            }

            // STAGE4 n Cont Random Updates
            {
                if (ThreadType::is_main) current_block.store(0);

                auto duration =
                    t.synchronized(update_contended<handle_type>, hash, n);

                t.out << otm::width(12) << duration.second / 1000000.
                      << std::flush;
            }

            // STAGE5 Validation of Hash Table Contents
            {
                if (ThreadType::is_main) current_block.store(0);

                auto duration =
                    t.synchronized(val_update<handle_type>, hash, n);

                t.out << otm::width(12) << duration.second / 1000000.
                      << otm::width(11) << errors.load();
            }

            t.out << std::endl;
            if (ThreadType::is_main) errors.store(0);
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
    double                        con = c.double_arg("-con", 1.0);
    if (!c.report()) return 1;

    zipf_gen.initialize(n, con);

    otm::out() << otm::width(5) << "#i" << otm::width(5) << "p"
               << otm::width(11) << "n" << otm::width(11) << "cap"
               << otm::width(7) << "con" << otm::width(12) << "t_ins_or"
               << otm::width(12) << "t_find_c" << otm::width(12) << "t_updt_c"
               << otm::width(12) << "t_val_up" << otm::width(11) << "errors"
               << "    " << con_config::name() << std::endl;

    ttm::start_threads<test_in_stages>(p, n, cap, it, con);

    return 0;
}
