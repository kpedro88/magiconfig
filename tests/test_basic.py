"""Single config: v2 feature parity (ported from tests/test_magiconfig.py) and drop-in behavior."""
import argparse
from collections import OrderedDict

import pytest

import magiconfig
from magiconfig import MagiConfig, MagiConfigError, ASK
from conftest import config_path, error_raising

EXPECTED = MagiConfig(bar=2.0, foo='2', ipsum=False)


def add_args(parser):
    parser.add_argument("-f", "--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b", "--bar", dest="bar", type=float, required=True, help="bar arg")
    parser.add_argument("-i", "--ipsum", dest="ipsum", action="store_true", help="ipsum arg")
    return parser


def make_parser(*config_args, **config_kwargs):
    """Parser with a single config arg (default: basic mode) as the default source."""
    if not config_args and not config_kwargs:
        parser = magiconfig.ArgumentParser(basic=True, prog="PROG")
    else:
        parser = magiconfig.ArgumentParser(prog="PROG")
        action = parser.add_argument(*(config_args or ("-C", "--config")), config=True, prefix=False, **config_kwargs)
        parser.set_default_source(action.dest)
    return add_args(error_raising(parser))


def test_dropin():
    args = ["-b", "2"]
    new_args = add_args(magiconfig.ArgumentParser()).parse_args(args)
    old_args = add_args(argparse.ArgumentParser()).parse_args(args)
    assert new_args == old_args
    assert type(new_args) is argparse.Namespace
    assert add_args(magiconfig.ArgumentParser(prog="PROG")).format_help() == add_args(argparse.ArgumentParser(prog="PROG")).format_help()


def test_config_args():
    parser = make_parser("-c", "--config")
    assert parser.parse_args(["-c", config_path("config1.py")]) == EXPECTED


def test_config_obj():
    parser = make_parser(obj="cfg")
    assert parser.parse_args(["-C", config_path("config2.py")]) == EXPECTED


def test_config_required():
    parser = make_parser(required=True)
    with pytest.raises(argparse.ArgumentError):
        parser.parse_args(["-b", "2"])


def test_no_config():
    parser = make_parser()
    assert parser.parse_args(["-b", "2"]) == MagiConfig(bar=2.0, foo='lorem', ipsum=False)


def test_conflict_arg():
    parser = make_parser()
    with pytest.raises(argparse.ArgumentError):
        parser.add_argument("-C", dest="C", type=str, default="conflict", help="conflicting arg")
    with pytest.raises(argparse.ArgumentError):
        parser.add_argument("-C", dest="C", type=str, default="conflict", help="conflicting arg", source="config")


def test_config_strict():
    parser = make_parser(strict=True)
    with pytest.raises(MagiConfigError):
        parser.parse_args(["-C", config_path("config3.py")])


def test_config_strict_arg():
    parser = make_parser(strict=ASK)
    assert parser.parse_args(["-C", config_path("config3.py")]) == EXPECTED
    with pytest.raises(MagiConfigError):
        parser.parse_args(["-C", config_path("config3.py"), "--strict"])
    # toggle off when strict by default
    parser = make_parser(strict=True, custom=dict(strict=True))
    assert parser.parse_args(["-C", config_path("config3.py"), "--no-strict"]) == EXPECTED


def test_required_arg():
    parser = make_parser()
    assert parser.parse_args(["-C", config_path("config1.py")]) == EXPECTED


def test_override():
    parser = make_parser()
    args = parser.parse_args(["-C", config_path("config1.py"), "-f", "blah"])
    assert args == MagiConfig(bar=2.0, foo='blah', ipsum=False)
    # order on the command line does not matter
    args = parser.parse_args(["-f", "blah", "-C", config_path("config1.py")])
    assert args == MagiConfig(bar=2.0, foo='blah', ipsum=False)


def test_inconsistent_type():
    parser = make_parser()
    parser.add_argument("-F", "--foo-foo", dest="foo", type=float, default=1.0, help="foo arg 2")
    args = parser.parse_args(["-C", config_path("config1.py")])
    assert args == MagiConfig(bar=2.0, foo=2, ipsum=False)


def test_bad_type():
    parser = make_parser()
    config = MagiConfig(bar="notafloat")
    parser.add_argument("-X", config=True, source="config")
    with pytest.raises(argparse.ArgumentError, match="invalid float value"):
        parser._config_parsers["config"].parse([], config, False)


def test_groups():
    # argument groups are only supported in the top-level parser, for its own (non-config) arguments
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("-C", "--config", config=True)
    parser.add_argument("-f", "--foo", dest="foo", type=str, default="lorem", help="foo arg", source="config")
    group1 = parser.add_argument_group("group1")
    group1.add_argument("-b", "--bar", dest="bar", type=float, required=True, help="bar arg")
    args = parser.parse_args(["-C", config_path("config1.py"), "-b", "3"])
    # mixed mode: plain Namespace containing the config section
    assert type(args) is argparse.Namespace
    assert args == argparse.Namespace(config=MagiConfig(foo='2'), bar=3.0)
    assert "group1:\n  -b" in parser.format_help()
    with pytest.raises(MagiConfigError):
        group1.add_argument("-x", source="config")
    with pytest.raises(MagiConfigError):
        parser._config_parsers["config"].args.add_argument_group("group2")


def test_mutex_groups():
    parser = magiconfig.ArgumentParser(basic=True, prog="PROG")
    error_raising(parser)
    parser.add_argument("-f", "--foo", dest="foo", type=str, default="lorem", help="foo arg")
    group = parser.add_mutually_exclusive_group(source="config")
    group.add_argument("-b", "--bar", dest="bar", type=float, help="bar arg")
    group.add_argument("-i", "--ipsum", dest="ipsum", action="store_true", help="ipsum arg")
    # mutual exclusion is only enforced on the command line
    assert parser.parse_args(["-C", config_path("config1.py")]) == EXPECTED
    with pytest.raises(argparse.ArgumentError, match="not allowed with"):
        parser.parse_args(["-b", "1", "-i"])
    with pytest.raises(MagiConfigError):
        group.add_argument("-x", transient=True)
    assert parser.format_usage() == "usage: PROG [-h] [-C CONFIG] [-f FOO] [-b BAR | -i]\n"


def test_subparsers():
    parser = magiconfig.ArgumentParser()
    subparsers = parser.add_subparsers()
    parser_one = subparsers.add_parser("one")
    parser_one.add_argument("-C", "--config", config=True, prefix=False, obj="config.one")
    parser_one.set_default_source("config")
    parser_one.add_argument("-f", "--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser_two = subparsers.add_parser("two")
    parser_two.add_argument("-C", "--config", config=True, prefix=False, obj="config.two")
    parser_two.set_default_source("config")
    parser_two.add_argument("-b", "--bar", dest="bar", type=float, required=True, help="bar arg")
    args_one = parser.parse_args(["one", "-C", config_path("config_sub.py")])
    assert isinstance(args_one, MagiConfig)
    assert args_one == MagiConfig(foo='2')
    args_two = parser.parse_args(["two", "-C", config_path("config_sub.py")])
    assert args_two == MagiConfig(bar=2.0)
    assert magiconfig.imported(args_two) == [(config_path("config_sub.py"), "config.two")]


def test_extra_dests():
    parser = make_parser(strict=True)
    parser.add_argument("extra", config_only=True)
    args = parser.parse_args(["-C", config_path("config3.py")])
    assert args == MagiConfig(bar=2.0, foo='2', ipsum=False, extra="blah")


@pytest.mark.parametrize("namespace", [None, argparse.Namespace(), MagiConfig()])
def test_dot_dests(namespace):
    parser = make_parser(strict=True)
    parser.remove_argument("-f")
    parser.remove_argument("-b")
    parser.remove_argument("-i")
    parser.add_argument("-f", "--foo", dest="one.foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b", "--bar", dest="two.bar", type=float, required=True, help="bar arg")
    args = parser.parse_args(["-C", config_path("config_sub.py")], namespace=namespace)
    expected = MagiConfig()
    expected.one = MagiConfig(foo='2')
    expected.two = MagiConfig(bar=2.0)
    assert args == expected
    assert isinstance(args, MagiConfig)


def test_obj_arg():
    parser = make_parser(obj=ASK, custom=dict(obj=dict(default="config.one")))
    args = parser.parse_args(["-C", config_path("config_sub.py"), "--obj", "config.two"])
    assert args == MagiConfig(bar=2.0, foo="lorem", ipsum=False)
    args = parser.parse_args(["-C", config_path("config_sub.py"), "-b", "1"])
    assert args == MagiConfig(bar=1.0, foo="2", ipsum=False)


def test_obj_arg_nodefault():
    parser = make_parser(obj=ASK, custom=dict(obj=dict(default=None, required=True)))
    with pytest.raises(argparse.ArgumentError):
        parser.parse_args(["-C", config_path("config_sub.py")])


def test_config_args_pos():
    parser = make_parser("poscon")
    assert parser.parse_args([config_path("config1.py")]) == EXPECTED
    assert parser.parse_args([config_path("config1.py"), "-f", "3"]) == MagiConfig(bar=2.0, foo='3', ipsum=False)
    # a positional config arg must come before any option flags
    with pytest.raises(MagiConfigError, match="Config file not found: 3"):
        parser.parse_args(["-f", "3", config_path("config1.py")])
    assert parser.format_usage() == "usage: PROG [-h] [-f FOO] -b BAR [-i] poscon\n"


def test_positional_in_section():
    parser = make_parser()
    with pytest.raises(MagiConfigError):
        parser.add_argument("pos", source="config")


USAGE = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n"


def expected_help(remove=(), formatter_class=argparse.HelpFormatter, config_only=()):
    """Expected help for make_parser(): an equivalent plain argparse parser with a "config" group,
    plus an indented config-only subsection given as (name, help) pairs."""
    plain = argparse.ArgumentParser(prog="PROG", formatter_class=formatter_class)
    group = plain.add_argument_group("config")
    group.add_argument("-C", "--config", help=magiconfig.CONFIG_DEFAULT_HELP)
    add_args(group)
    for flag in remove:
        plain._handle_conflict_resolve(None, [(flag, plain._option_string_actions[flag])])
    text = plain.format_help()
    if config_only:
        help_line = next(line for line in text.split("\n") if line.startswith("  -h"))
        column = help_line.index("show")
        text += "\n  config-only arguments:\n"
        for name, help in config_only:
            text += (f"    {name}".ljust(column) + help).rstrip() + "\n"
    return text


def test_config_usage():
    parser = make_parser()
    assert parser.format_usage() == USAGE


def test_config_help():
    parser = make_parser()
    assert parser.format_help() == expected_help()


def test_help_with_missing_required(capsys):
    parser = magiconfig.ArgumentParser(basic=True, prog="PROG")
    add_args(parser)
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["-h"])
    assert exc.value.code == 0
    assert capsys.readouterr().out == parser.format_help()
    # required flags are restored afterwards
    assert parser._nested_option_strings["-b"][1].required


def test_version_with_missing_required(capsys):
    parser = magiconfig.ArgumentParser(basic=True, prog="PROG")
    add_args(parser)
    parser.add_argument("--version", action="version", version="1.0")
    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])
    assert capsys.readouterr().out == "1.0\n"


def test_config_parse_twice():
    parser = make_parser()
    parser.parse_args(["-C", config_path("config1.py")])
    assert parser.parse_args(["-C", config_path("config1.py")]) == EXPECTED
    assert parser.format_usage() == USAGE


def test_remove_arg():
    parser = make_parser()
    parser.remove_argument('-b', keep=True)
    assert parser.format_usage() == "usage: PROG [-h] [-C CONFIG] [-f FOO] --bar BAR [-i]\n"


def test_remove_action():
    parser = make_parser()
    parser.remove_argument('-b')
    assert parser.format_help() == expected_help(remove=["-b", "--bar"])


def test_remove_root_arg():
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("-x")
    parser.add_argument("pos")
    parser.remove_argument("-x")
    parser.remove_argument("pos")
    assert parser.format_usage() == "usage: PROG [-h]\n"


def test_remove_config_arg():
    parser = make_parser()
    parser.remove_argument('-C')
    assert parser.format_usage() == "usage: PROG [-h]\n"
    assert parser._nested_option_strings == {}
    with pytest.raises(argparse.ArgumentError):
        parser.parse_args(["-C", config_path("config1.py")])


def test_remove_unknown_arg():
    parser = make_parser()
    with pytest.raises(argparse.ArgumentError):
        parser.remove_argument('-x')


def test_config_only_required():
    parser = make_parser(strict=True)
    parser.add_argument("extra", config_only=True, required=True)
    with pytest.raises(MagiConfigError, match="missing required attributes: extra"):
        parser.parse_args(["-C", config_path("config1.py")])


def test_config_only_remove():
    parser = make_parser(strict=True)
    parser.add_argument("extra", config_only=True)
    parser.remove_argument("extra")
    with pytest.raises(MagiConfigError):
        parser.parse_args(["-C", config_path("config3.py")])


def test_config_only_help():
    parser = magiconfig.ArgumentParser(basic=True, prog="PROG", formatter_class=magiconfig.ArgumentDefaultsHelpFormatter)
    add_args(error_raising(parser))
    parser.add_argument("arg1", config_only=True)
    parser.add_argument("arg2", config_only=True, required=True)
    parser.add_argument("arg3", config_only=True, default="test")
    assert parser.format_help() == expected_help(
        formatter_class=magiconfig.ArgumentDefaultsHelpFormatter,
        config_only=[("arg1", ""), ("arg2", "(required)"), ("arg3", "(default: test)")],
    )
    # without default formatting, the default is not shown
    parser = make_parser()
    parser.add_argument("arg3", config_only=True, default="test")
    assert parser.format_help().endswith("config-only arguments:\n    arg3\n")
    parser = magiconfig.ArgumentParser(prog="PROG")
    parser.add_argument("-C", "--config", config=True, config_only_help=False)
    parser.add_argument("arg3", config_only=True, default="test", source="config")
    assert "config-only" not in parser.format_help()


def test_config_only_top_level():
    parser = magiconfig.ArgumentParser()
    with pytest.raises(MagiConfigError):
        parser.add_argument("extra", config_only=True)


def test_config_only_already_used():
    parser = make_parser()
    with pytest.raises(argparse.ArgumentError):
        parser.add_argument("bar", config_only=True)


def test_dest_already_config_only():
    parser = make_parser()
    parser.add_argument("arg1", config_only=True)
    with pytest.raises(argparse.ArgumentError):
        parser.add_argument("-a", "--arg", dest="arg1", type=str, default="", help="arg1")


def test_remove_action_then_config_only():
    parser = make_parser()
    parser.remove_argument('-b')
    parser.add_argument("bar", config_only=True)


def test_default_config_only():
    parser = make_parser()
    parser.remove_argument("-i")
    parser.add_argument("ipsum", config_only=True, default=True)
    assert parser.parse_args(["-C", config_path("config1.py")]) == EXPECTED
    # config-only defaults populate the namespace
    assert parser.parse_args(["-b", "1"]) == MagiConfig(bar=1.0, foo='lorem', ipsum=True)


def test_config_only_type_choices():
    parser = make_parser()
    parser.add_argument("names", config_only=True, type=str, choices=["Bob", "Carol"])
    with pytest.raises(argparse.ArgumentError, match="invalid choice"):
        parser.parse_args(["-C", config_path("config4b.py")])


def test_nargs_config():
    parser = make_parser()
    parser.add_argument("-n", "--names", dest="names", type=str, default=[], nargs='+', help="names arg")
    args = parser.parse_args(["-C", config_path("config4.py")])
    assert args == MagiConfig(bar=2.0, foo='2', ipsum=False, names=["Alice", "Bob"])


def test_nargs_config_none():
    parser = make_parser()
    parser.add_argument("-n", "--names", dest="names", default=[], nargs='+', help="names arg")
    args = parser.parse_args(["-C", config_path("config4c.py")])
    assert args == MagiConfig(bar=2.0, foo='2', ipsum=False, names=OrderedDict([("Alice", True)]))


@pytest.mark.parametrize("config,nargs,choices,should_fail", [
    ("config4.py", '+', ["Alice", "Carol"], True),
    ("config4b.py", '+', ["Alice", "Carol"], False),
    ("config4b.py", None, ["Alice", "Carol"], False),
    ("config4b.py", None, ["Bob", "Carol"], True),
])
def test_choices_config(config, nargs, choices, should_fail):
    parser = make_parser()
    parser.add_argument("-n", "--names", dest="names", type=str, default=[], nargs=nargs, choices=choices, help="names arg")
    if should_fail:
        with pytest.raises(argparse.ArgumentError):
            parser.parse_args(["-C", config_path(config)])
    else:
        parser.parse_args(["-C", config_path(config)])


def test_config_write_read(tmp_path):
    parser1 = make_parser()
    args1 = parser1.parse_args(["-b", "2"])
    parser1.write_config(args1, str(tmp_path / "out.py"))
    parser2 = make_parser()
    args2 = parser2.parse_args(["-C", str(tmp_path / "out.py")])
    assert args1 == args2


@pytest.mark.parametrize("dest,value", [
    ("dict", OrderedDict([(1, 2)])),
    ("subconfig.dict", OrderedDict([(1, 2)])),
    ("subconfig.dicts", [OrderedDict([(1, 2)]), OrderedDict([(3, 4)])]),
])
def test_config_write_read_OrderedDict(tmp_path, dest, value):
    parser = magiconfig.ArgumentParser(basic=True)
    parser.add_argument("-d", "--dict", dest=dest, default=None, help="dict arg")
    config_in = MagiConfig()
    setattr(config_in, dest, value)
    parser.write_config(config_in, str(tmp_path / "out.py"))
    assert parser.parse_args(["-C", str(tmp_path / "out.py")]) == config_in


def test_write_mixed_namespace(tmp_path):
    parser = magiconfig.ArgumentParser()
    parser.add_argument("-C", config=True)
    parser.add_argument("-x")
    args = parser.parse_args([])
    with pytest.raises(MagiConfigError, match="plain argparse namespace"):
        parser.write_config(args, str(tmp_path / "out.py"))


def test_config_default_type():
    parser = make_parser()
    parser.add_argument("--extra", dest="extra", type=str, default=None, help="extra arg")
    args = parser.parse_args(["-C", config_path("config5.py")])
    assert args.extra is None


def test_disable():
    parser = make_parser()
    assert parser.add_argument("--hidden", default=5, disable=True) is None
    args = parser.parse_args(["-b", "1"])
    assert args.hidden == 5
    assert "hidden" not in parser.format_help()
    with pytest.raises(argparse.ArgumentError):
        parser.parse_args(["-b", "1", "--hidden", "6"])
    # still readable from configs
    args = parser._config_parsers["config"].parse([], MagiConfig(bar=1, hidden=7), False)[0]
    assert args.hidden == 7
    # top level
    parser = magiconfig.ArgumentParser()
    parser.add_argument("--hidden", default=5, disable=True)
    assert parser.parse_args([]) == argparse.Namespace(hidden=5)


def test_transient(tmp_path):
    parser = make_parser()
    parser.add_argument("-v", "--verbose", action="store_true", transient=True)
    args = parser.parse_args(["-C", config_path("config1.py"), "-v"])
    assert args == MagiConfig(bar=2.0, foo='2', ipsum=False, verbose=True)
    assert args._transients == {"verbose"}
    # never written
    path = tmp_path / "out.py"
    parser.write_config(args, str(path))
    assert "verbose" not in path.read_text()
    # never read from configs: ignored, or rejected in strict mode
    config = tmp_path / "in.py"
    config.write_text("from magiconfig import MagiConfig\nconfig = MagiConfig(bar=1.0, verbose=True)\n")
    assert parser.parse_args(["-C", str(config)]).verbose is False
    parser = make_parser(strict=True)
    parser.add_argument("-v", "--verbose", action="store_true", transient=True)
    with pytest.raises(MagiConfigError, match="unknown attributes: verbose"):
        parser.parse_args(["-C", str(config)])


def test_transient_config_only():
    parser = make_parser()
    with pytest.raises(MagiConfigError):
        parser.add_argument("x", config_only=True, transient=True)


def test_imported_single():
    parser = make_parser()
    args = parser.parse_args(["-C", config_path("config1.py")])
    assert magiconfig.imported(args) == [(config_path("config1.py"), "config")]
    assert magiconfig.imported(parser.parse_args(["-b", "1"])) == []


def test_exit_on_error():
    parser = magiconfig.ArgumentParser(basic=True, exit_on_error=False)
    add_args(parser)
    with pytest.raises(argparse.ArgumentError):
        parser.parse_known_args(["-b", "x"])


def test_fromfile(tmp_path):
    argfile = tmp_path / "args.txt"
    argfile.write_text(f"-C\n{config_path('config1.py')}\n-f\nfromfile\n")
    parser = magiconfig.ArgumentParser(basic=True, fromfile_prefix_chars="@")
    add_args(parser)
    assert parser.parse_args([f"@{argfile}"]) == MagiConfig(bar=2.0, foo='fromfile', ipsum=False)


def test_abbrev():
    parser = make_parser()
    assert parser.parse_args(["--conf", config_path("config1.py"), "--fo", "x"]) == MagiConfig(bar=2.0, foo='x', ipsum=False)
    parser = magiconfig.ArgumentParser(basic=True, allow_abbrev=False)
    error_raising(add_args(parser))
    with pytest.raises(argparse.ArgumentError):
        parser.parse_args(["--conf", config_path("config1.py")])


def test_intermixed():
    parser = make_parser()
    with pytest.raises(MagiConfigError):
        parser.parse_intermixed_args([])
