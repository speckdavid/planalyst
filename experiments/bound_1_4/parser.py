from lab.parser import Parser


def add_coverage(content, props):
    props["coverage"] = 0

    # Coverage for symk and kstar
    if "Total time:" in content:
        assert "Number of plans:" in content
        props["coverage"] = 1

    if "Planalyst time" in content:
        assert "Number of plans:" in content
        props["coverage"] = 1


class CustomParser(Parser):
    def __init__(self):
        Parser.__init__(self)


def get_parser():
    parser = CustomParser()
    parser.add_pattern("num_plans", r"Number of plans: (.+)", type=int)
    parser.add_pattern("total_time", r"Total time: (.+)s", type=float)
    parser.add_pattern("total_time", r"Planalyst time: (.+)s", type=float)
    parser.add_function(add_coverage)
    return parser
