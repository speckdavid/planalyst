#! /usr/bin/env python3
import logging
import os
import re
import shutil
import sys
import utils

from collections import OrderedDict
from subprocess import Popen, PIPE


logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s ::: %(message)s",
)
logger = logging.getLogger(__name__)


def run_madagascar(domain, instance, horizon, no_invariant_synthesis, dump_output):
    options = ["-P", "0", "-F", str(horizon), "-S", "1", "-T", str(horizon), "-O", "-3"]
    if no_invariant_synthesis:
        options += ["-N"]
    # Max memory allowed for madagascar and the cnf file: 6000MB
    options += ["-m", "6000"]
    binary_path = shutil.which("Mp") if shutil.which("Mp") is not None else "./Mp"
    command = [binary_path, domain, instance] + options
    process = Popen(command, stdout=PIPE, stdin=PIPE, stderr=PIPE, text=True)

    time = utils.get_elapsed_time()
    output, error = process.communicate()
    logging.info(f"Madagascar time: {utils.get_elapsed_time() - time:.2f}s")

    logger.info(f"Madagascar return code: {process.returncode}")
    if process.returncode != 0:
        print(error)
        exit(process.returncode)

    cnf_name = get_cnf_name(output)

    if dump_output:
        print(output)

    return cnf_name


def get_plan_count(output):
    lines = output.splitlines()
    for line in reversed(lines):
        # NOTE: this assumes that only the solution line start with 's. This
        # seems to be the case in all tested examples.
        if line.startswith("s"):
            tokens = line.split()
            assert len(tokens) == 2
            return int(tokens[1])
    return -1


def run_d4(cnf_file, method, dump_output):
    options = ["-m", method]
    binary_path = shutil.which("d4") if shutil.which("d4") is not None else "./d4"
    command = [binary_path, "-i", cnf_file] + options
    process = Popen(command, stdout=PIPE, stdin=PIPE, stderr=PIPE, text=True)

    time = utils.get_elapsed_time()
    output, error = process.communicate()
    logging.info(f"D4 time: {utils.get_elapsed_time() - time:.2f}s")

    logger.info(f"D4 return code: {process.returncode}")
    if process.returncode != 0:
        print(error)
        exit(process.returncode)

    number_plans = get_plan_count(output)
    if number_plans == -1:
        logger.error("D4 did not return a valid solution.")
        sys.exit(-1)

    logger.info(f"Number of plans: {number_plans}")

    if dump_output:
        print(output)


def write_plans(plans_by_length):
    plan_id = 1
    for length in plans_by_length:
        for plan in plans_by_length[length]:
            utils.write_lines_to_file(f"sas_plan.{plan_id}", plan)
            plan_id += 1


def run_ddnnife(cnf_file, write_plans_to_disk, dump_output):
    binary_path = (
        shutil.which("ddnnife") if shutil.which("ddnnife") is not None else "./ddnnife"
    )
    command = [binary_path, cnf_file, "stream"]
    process = Popen(command, stdout=PIPE, stdin=PIPE, stderr=PIPE, text=True)
    time = utils.get_elapsed_time()
    output, error = process.communicate(input="enum")
    logging.info(f"Ddnnife time: {utils.get_elapsed_time() - time:.2f}s")

    if dump_output:
        print(output)

    logger.info(f"Ddnnife return code: {process.returncode}")

    if process.returncode != 0:
        if "`Option::unwrap()` on a `None` value" in error:
            logger.info("Unsolvable?")
            logger.info("Number of plans: 0")
        else:
            print(error)
            exit(process.returncode)
    else:
        logger.info(f"Number of plans: {output.count(';') + 1}")

        logging.info("Constructing plans...")
        time = utils.get_elapsed_time()
        action_table = utils.get_action_table(cnf_file)
        plans_by_length = OrderedDict()

        for plan_as_sat in output.split(";"):
            cur_plan = []
            for lit in plan_as_sat.split(" "):
                lit = int(lit)
                if lit in action_table:
                    cur_plan.append(action_table[lit])
                    assert [a.time for a in cur_plan] == list(range(len(cur_plan)))
            plan_length = len(cur_plan)
            if plan_length not in plans_by_length:
                plans_by_length[plan_length] = []
            plans_by_length[plan_length].append([a.name for a in cur_plan])

        logging.info(f"Plan construction time: {utils.get_elapsed_time() - time:.2f}s")
        logging.info(f"Number of diverse costs: {len(plans_by_length)}")

        if write_plans_to_disk:
            time = utils.get_elapsed_time()
            logging.info("Writing plans...")
            write_plans(plans_by_length)
            logging.info(f"Plan writting time: {utils.get_elapsed_time() - time:.2f}s")


def run_interactive_ddnnife(cnf_file):
    binary_path = (
        shutil.which("ddnnife") if shutil.which("ddnnife") is not None else "./ddnnife"
    )
    command = [binary_path, cnf_file, "stream"]
    process = Popen(command, stdout=PIPE, stdin=PIPE, stderr=PIPE, text=True)

    print("Interactive mode: Type your queries and press Enter (type 'exit' to quit).")

    while True:
        user_input = input("> ")

        if user_input.strip().lower() == "exit":
            print("Exiting interactive mode.")
            break

        # Send user input to the process
        process.stdin.write(user_input + "\n")
        process.stdin.flush()

        # Read and print the process output
        # Always only one line
        output = process.stdout.readline()
        print(output.replace("\n", ""))

    # Close the process
    process.stdin.close()
    process.stdout.close()
    process.stderr.close()
    process.terminate()
    process.wait()


def get_cnf_name(output):
    lines = output.splitlines()
    for line in reversed(lines):
        match = re.search(r"\S+\.cnf", line)
        if match:
            cnf_filename = match.group()  # Store the latest match
            return cnf_filename


def remove_cnf_files():
    current_directory = os.getcwd()

    for file_name in os.listdir(current_directory):
        file_path = os.path.join(current_directory, file_name)
        if os.path.isfile(file_path) and file_name.endswith(".cnf"):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing {file_path}: {e}")


if __name__ == "__main__":
    args = utils.parse_arguments()

    domain_file = args.domain
    instance_file = args.instance
    if not os.path.isfile(domain_file):
        sys.stderr.write("Error: Domain file does not exist.\n")
        sys.exit()
    if not os.path.isfile(instance_file):
        sys.stderr.write("Error: Instance file does not exist.\n")
        sys.exit()

    utils.check_necessary_files()

    logger.info("Running Madagascar...")
    cnf_file_name = run_madagascar(
        args.domain,
        args.instance,
        args.horizon,
        args.no_invariant_synthesis,
        args.dump_output,
    )

    if "enumeration" in args.method:
        logger.info("Running ddnnife...")
        not_write_to_disk = "no-write" in args.method
        # We never dump the output because it would be all satisying assignments
        run_ddnnife(cnf_file_name, not not_write_to_disk, False)
    elif "interact" in args.method:
        logger.info("Running interactive ddnnife...")
        logger.info(
            "Note: In interactive mode, we are currently not transforming literals to their planning semantics. "
            f"The mapping for actions and state variables per time step can be seen in the comments at the end of the CNF file {cnf_file_name}."
        )
        run_interactive_ddnnife(cnf_file_name)
    else:
        logger.info("Running d4...")
        run_d4(cnf_file_name, args.method, args.dump_output)

    if args.cleanup:
        logger.info("Cleaning up: all CNF files will be removed.")
        remove_cnf_files()

    logging.info(f"Planalyst time: {utils.get_elapsed_time():.2f}s")
    logger.info("Done!")
