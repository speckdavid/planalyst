import argparse
import errno
import logging
import os
import shutil

from collections import namedtuple
from pathlib import Path

logger = logging.getLogger(__name__)

Action = namedtuple("Action", "index time name")


def get_elapsed_time():
    """
    Return the CPU time taken by the python process and its child
    processes.
    """
    if os.name == "nt":
        # The child time components of os.times() are 0 on Windows.
        raise NotImplementedError("cannot use get_elapsed_time() on Windows")
    return sum(os.times()[:4])


def find_domain_filename(task_filename):
    """
    Find domain filename for the given task using automatic naming rules.
    """
    dirname, basename = os.path.split(task_filename)

    domain_basenames = [
        "domain.pddl",
        basename[:3] + "-domain.pddl",
        "domain_" + basename,
        "domain-" + basename,
    ]

    for domain_basename in domain_basenames:
        domain_filename = os.path.join(dirname, domain_basename)
        if os.path.exists(domain_filename):
            return domain_filename


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Count number of plans of a planning problem."
    )
    parser.add_argument(
        "-i", "--instance", required=True, help="The path to the PDDL instance file."
    )
    parser.add_argument(
        "-m",
        "--method",
        default="ddnnf-compiler",
        choices=[
            "ddnnf-compiler",
            "counting",
            "enumeration",
            "enumeration-no-write",
            "interact",
        ],
        help="The method to run: 'counting' for model counting, 'ddnnf-compiler' for decision DNNF compilation, "
        "'enumeration' for enumerating plans and writing them to disk, 'enumeration-no-write' for enumerating plans "
        "without writing to disk, and 'interact' for an interactive session with ddnife where you can query reasoning tasks "
        "such as 'count' for counting, 'core' for backbone variables, or 'random l 10' to get 10 random assignments.",
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="(Optional) The path to the PDDL domain file. If none is "
        "provided, the system will try to automatically deduce "
        "it from the instance filename.",
    )
    parser.add_argument(
        "--horizon", required=True, type=int, help="Horizon used by Madagascar."
    )
    parser.add_argument(
        "--dump-output",
        action="store_true",
        help="dump the output of tools.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean all CNF files in the folder after execution.",
    )
    parser.add_argument(
        "--no-invariant-synthesis",
        action="store_true",
        help="Don't use invariant synthesis in Madagascar.",
    )

    args = parser.parse_args()
    if args.domain is None:
        args.domain = find_domain_filename(args.instance)
        if args.domain is None:
            raise RuntimeError(
                f'Could not find domain filename that matches instance file "{args.domain}"'
            )

    return args


def get_action_table(cnf_file):
    action_table = {}

    try:
        with open(cnf_file, "r") as file:
            for line in file:
                # Check for lines that start with "c action"
                if line.startswith("c action"):
                    parts = line.split()
                    # Validate the expected format: "c action index time name"
                    if len(parts) != 5:
                        print(f"Warning: Skipping malformed line: {line.strip()}")
                        continue

                    index, time, name = parts[2:]
                    index = int(index)
                    time = int(time)

                    # Transform name to IPC format
                    name = (
                        name.replace(",", " ")
                        .replace("(", " ")
                        .replace(")", " ")
                        .strip()
                    )
                    name = f"({name})"

                    # Create an Action object and add it to the lookup table
                    action_table[index] = Action(index, time, name)

    except FileNotFoundError:
        print(f"Error: File {cnf_file} not found.")
    except IOError as e:
        print(f"Error: Could not read file {cnf_file}. {e}")

    return action_table


def write_lines_to_file(file_path, lines):
    try:
        with open(file_path, "w") as file:
            for line in lines:
                file.write(line + "\n")
        # print(f"Successfully wrote {len(lines)} lines to {file_path}.")
    except Exception as e:
        print(f"An error occurred: {e}")


def is_binary_available(binary_name):
    # Check if the binary exists in the current directory
    current_dir_binary = Path(binary_name)
    if current_dir_binary.is_file() and current_dir_binary.stat().st_mode & 0o111:
        return True

    # Check if the binary is in the PATH
    if shutil.which(binary_name):
        return True

    return False


def check_necessary_files():
    if not is_binary_available("Mp"):
        logger.error("ERROR: Madagascar (Mp) is not available!")
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), "Mp")

    if not is_binary_available("d4"):
        logger.error("ERROR: d4 is not available!")
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), "d4")

    if not is_binary_available("ddnnife"):
        logger.error("ERROR: ddnnife is not available!")
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), "ddnnife")
