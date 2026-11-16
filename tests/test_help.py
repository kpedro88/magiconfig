"""Help and usage: sections, nesting, config-only subsections, descriptions, short vs full usage, help_depth."""
import argparse

import magiconfig
from magiconfig import ConfigObject
from conftest import help_heading


class Sub(ConfigObject):
    _description = "a sub object"
    _arguments = dict(x=dict(type=int, default=1, help="x arg"))


class Foo(ConfigObject):
    _description = "the foo object"
    _arguments = dict(
        a=dict(type=int, default=1, help="a arg"),
        sub=dict(type=Sub, help="sub config"),
    )


def make_parser(**kwargs):
    parser = magiconfig.ArgumentParser(prog="PROG", description="desc", **kwargs)
    parser.add_argument("--top", help="top arg")
    parser.add_argument("-A", config=True, description="section A", obj=magiconfig.ASK)
    parser.add_argument("--foo", source="A", help="foo arg")
    parser.add_argument("y", config_only=True, source="A", required=True)
    parser.add_argument("-D", config=True, source="A")
    parser.add_argument("--d", source="D", help="d arg")
    parser.add_argument("--F", type=Foo, help="foo config")
    return parser


USAGE = "usage: PROG [-h] [--top TOP] [-A A] [--A.obj OBJ] [--F F]\n"
HEADER = [
    USAGE,
    "desc",
    "",
    help_heading(),
    "  -h, --help     show this help message and exit",
    "  --top TOP      top arg",
]


def test_help_full_depth():
    assert make_parser().format_help() == "\n".join(HEADER + [
        "",
        "A:",
        "  section A",
        "",
        "  -A A           name of config file to import",
        "  --A.obj OBJ    name of object to import from config file",
        "  --foo FOO      foo arg",
        "",
        "  config-only arguments:",
        "    y            (required)",
        "",
        "  A.D:",
        "    -D D         name of config file to import",
        "    --d D        d arg",
        "",
        "F:",
        "  the foo object",
        "",
        "  --F F          foo config",
        "  --F.a A        a arg",
        "",
        "  F.sub:",
        "    a sub object",
        "",
        "    --F.sub SUB  sub config",
        "    --F.sub.x X  x arg",
    ]) + "\n"


def test_help_depth_0():
    assert make_parser(help_depth=0).format_help() == "\n".join([
        USAGE,
        "desc",
        "",
        help_heading(),
        "  -h, --help   show this help message and exit",
        "  --top TOP    top arg",
        "  -A A         name of config file to import",
        "  --A.obj OBJ  name of object to import from config file",
        "  --F F        foo config",
    ]) + "\n"


def test_help_depth_1():
    assert make_parser(help_depth=1).format_help() == "\n".join([
        USAGE,
        "desc",
        "",
        help_heading(),
        "  -h, --help   show this help message and exit",
        "  --top TOP    top arg",
        "",
        "A:",
        "  section A",
        "",
        "  -A A         name of config file to import",
        "  --A.obj OBJ  name of object to import from config file",
        "  --foo FOO    foo arg",
        "  -D D         name of config file to import",
        "",
        "  config-only arguments:",
        "    y          (required)",
        "",
        "F:",
        "  the foo object",
        "",
        "  --F F        foo config",
        "  --F.a A      a arg",
        "  --F.sub SUB  sub config",
    ]) + "\n"


def test_usage_short_vs_full():
    # short usage: top-level config args and their enabled base args only
    assert make_parser().format_usage() == USAGE
    # full usage: at most one config=True section and no ConfigObjects
    parser = magiconfig.ArgumentParser(prog="PROG")
    parser.add_argument("pos")
    parser.add_argument("-A", config=True, strict=magiconfig.ASK)
    parser.add_argument("--foo", source="A")
    assert parser.format_usage() == "usage: PROG [-h] [-A A] [--A.strict | --no-A.strict] [--foo FOO] pos\n"
    parser = magiconfig.ArgumentParser(prog="PROG")
    parser.add_argument("--F", type=Sub)
    assert parser.format_usage() == "usage: PROG [-h] [--F F]\n"
    # user-provided usage
    parser = magiconfig.ArgumentParser(prog="PROG", usage="%(prog)s [stuff]")
    parser.add_argument("-A", config=True)
    assert parser.format_usage() == "usage: PROG [stuff]\n"


def test_help_epilog_groups():
    parser = magiconfig.ArgumentParser(prog="PROG", epilog="the end")
    group = parser.add_argument_group("group1", "group description")
    group.add_argument("--g", help="g arg")
    parser.add_argument("pos", help="pos arg")
    parser.add_argument("-A", config=True, help="config A")
    parser.add_argument("--foo", source="A", help="foo arg")
    assert parser.format_help() == "\n".join([
        "usage: PROG [-h] [--g G] [-A A] [--foo FOO] pos",
        "",
        "positional arguments:",
        "  pos         pos arg",
        "",
        help_heading(),
        "  -h, --help  show this help message and exit",
        "",
        "group1:",
        "  group description",
        "",
        "  --g G       g arg",
        "",
        "A:",
        "  -A A        config A",
        "  --foo FOO   foo arg",
        "",
        "the end",
    ]) + "\n"


def test_help_class_default():
    parser = magiconfig.ArgumentParser(prog="PROG", formatter_class=magiconfig.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-A", config=True)
    parser.add_argument("--cls", default=int, help="a class", source="A")
    assert "a class (default: int)" in parser.format_help()


def test_formatter_not_patched_globally():
    # the config-only help placeholder is handled only by magiconfig formatters
    make_parser(formatter_class=magiconfig.ArgumentDefaultsHelpFormatter).format_help()
    assert not issubclass(argparse.ArgumentDefaultsHelpFormatter, magiconfig._MagiFormatterMixin)
    assert "_format_action" not in vars(argparse.ArgumentDefaultsHelpFormatter)
