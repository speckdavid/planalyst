import json
import statistics

# Ignore this config because we do not report it in the paper
IGNORE_CONFIGS = ["planalyst-count"]

BOUND_AND_JSON_FILES = [
    (1.0, "bound_1_0/data/experiments-eval/properties"),
    (1.1, "bound_1_1/data/experiments-eval/properties"),
    (1.2, "bound_1_2/data/experiments-eval/properties"),
    (1.3, "bound_1_3/data/experiments-eval/properties"),
    (1.4, "bound_1_4/data/experiments-eval/properties"),
    (1.5, "bound_1_5/data/experiments-eval/properties"),
]


def get_raw_data(json_file):
    # Read the JSON file
    try:
        with open(json_file, "r") as file:
            raw_data = json.load(file)
    except FileNotFoundError:
        print(f"Error: The file {json_file} was not found.")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from the file {json_file}.")
        exit(1)
    return raw_data


def get_data(raw_data):

    data = {}
    for key in raw_data:
        entry = raw_data[key]
        if "num_plans" not in entry:
            continue

        if entry["algorithm"] in IGNORE_CONFIGS:
            continue

        domain = entry["domain"]
        problem = entry["problem"]
        value = entry["num_plans"]

        my_key = f"{domain}:{problem}"
        assert value not in data or data[my_key] == value
        data[my_key] = value

    return data


def merge(data_lower_bound, data_higher_bound):
    data = data_higher_bound.copy()

    if data_lower_bound:
        questionable_keys = set(data_higher_bound.keys()) - set(data_lower_bound.keys())
        assert not questionable_keys, f"Missing keys in dict2: {questionable_keys}"

    for key in data_lower_bound:
        if key not in data_higher_bound:
            data[key] = data_lower_bound[key]
        assert data[key] >= data_lower_bound[key]
        data[key] = max(data[key], data_lower_bound[key])
    return data


def format_e(n):
    return "{:.2e}".format(n)


def print_stats(bound, data):
    values = data.values()
    assert None not in values
    print(f"Number of Plans with bound {bound}:")
    print(f"Min: {format_e(min(values))}")
    print(f"Max: {format_e(max(values))}")
    print(f"Average: {format_e(statistics.mean(values))}")
    print(f"Median: {format_e(statistics.median(values))}")
    print(
        f"{format_e(min(values))} & {format_e(max(values))} & {format_e(statistics.mean(values))} & {format_e(statistics.median(values))}"
    )


def print_instance_state(bound, data):
    values = data.values()
    min_instances = []
    max_instances = []
    min_value = min(values)
    max_value = max(values)
    for key in data:
        value = data[key]
        if value == min_value:
            min_instances.append(key)
        if value == max_value:
            max_instances.append(key)
    # print(f"Min instances with bound {bound}: {min_instances}")
    print(f"Max instances with bound {bound}: {max_instances}")


def main():
    # Parse the arguments
    data = {}
    bounds = []
    for bound, json_file in BOUND_AND_JSON_FILES:
        bound_raw_data = get_raw_data(json_file)
        bound_data = get_data(bound_raw_data)
        # print_stats(bound, bound_data)
        # print()
        data = merge(data, bound_data)

        bounds.append(bound)
        print_stats(bounds, data)
        print()
        # print_instance_state(bound, bound_data)
        # print()
        # print_instance_state(bounds, data)
        print()
        print("-" * 120)
        print()


if __name__ == "__main__":
    main()
