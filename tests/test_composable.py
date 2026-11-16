"""Multiple configs, sources, nargs joining, namespace types, separate writing, subparsers, parents."""
import argparse

import pytest

import magiconfig
from magiconfig import MagiConfig, MagiConfigError, ASK
from conftest import error_raising, make_config


@pytest.fixture
def configs(tmp_path):
    return dict(
        a=make_config(tmp_path / "a.py", foo=2, extra="x"),
        a2=make_config(tmp_path / "a2.py", foo=5, other=1),
        b=make_config(tmp_path / "b.py", bar="b"),
        multi=make_config(tmp_path / "multi.py", obj="c", one=MagiConfig(foo=7), two=MagiConfig(foo=8)),
    )


def make_parser(**kwargs):
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG", **kwargs))
    parser.add_argument("-A", config=True)
    parser.add_argument("--foo", type=int, default=0, source="A")
    parser.add_argument("-B", config=True)
    parser.add_argument("--bar", default="none", source="B")
    return parser


def test_multiple_configs(configs):
    parser = make_parser()
    args = parser.parse_args(["-A", configs["a"], "--foo", "1", "-B", configs["b"], "--bar", "a"])
    assert args == MagiConfig(A=MagiConfig(foo=1), B=MagiConfig(bar="a"))
    args = parser.parse_args(["-A", configs["a"], "-B", configs["b"]])
    assert args == MagiConfig(A=MagiConfig(foo=2), B=MagiConfig(bar="b"))
    assert parser.parse_args([]) == MagiConfig(A=MagiConfig(foo=0), B=MagiConfig(bar="none"))


def test_order_independence(configs):
    parser = make_parser()
    expected = parser.parse_args(["-A", configs["a"], "--foo", "1"])
    assert parser.parse_args(["--foo", "1", "-A", configs["a"]]) == expected
    assert parser.parse_args(["--bar", "z", "--foo", "1", "-A", configs["a"]]) == MagiConfig(A=MagiConfig(foo=1), B=MagiConfig(bar="z"))


def test_imported_multiple(configs):
    parser = make_parser()
    args = parser.parse_args(["-A", configs["a"], "-B", configs["b"]])
    assert magiconfig.imported(args.A) == [(configs["a"], "config")]
    assert magiconfig.imported(args.B) == [(configs["b"], "config")]
    assert magiconfig.imported(args) == []


def test_dotted_source(configs, tmp_path):
    parser = make_parser()
    parser.add_argument("-D", config=True, source="A")
    parser.add_argument("--baz", default=1, type=int, source="A.D")
    parser.add_argument("--qux", default=1, type=int, source="D")
    args = parser.parse_args(["-A", configs["a"]])
    assert args.A == MagiConfig(foo=2, D=MagiConfig(baz=1, qux=1))
    # parent config provides the nested config: as a path or inline
    d = make_config(tmp_path / "d.py", baz=3)
    parent = make_config(tmp_path / "parent.py", foo=4, D=d)
    args = parser.parse_args(["-A", parent])
    assert args.A == MagiConfig(foo=4, D=MagiConfig(baz=3, qux=1))
    assert magiconfig.imported(args.A.D) == [(d, "config")]
    parent = make_config(tmp_path / "parent2.py", foo=4, D=MagiConfig(baz=5))
    args = parser.parse_args(["-A", parent, "--qux", "2"])
    assert args.A == MagiConfig(foo=4, D=MagiConfig(baz=5, qux=2))
    assert magiconfig.imported(args.A.D) == [(None, "config")]
    # command line > parent config
    args = parser.parse_args(["-A", parent, "-D", d])
    assert args.A.D.baz == 3


def test_source_errors():
    parser = make_parser()
    with pytest.raises(MagiConfigError, match="Unknown source"):
        parser.add_argument("--x", source="C")
    parser.add_argument("-D", config=True, source="A")
    parser.add_argument("-E", "--D", config=True, source="B", dest="D")
    with pytest.raises(MagiConfigError, match="Ambiguous source"):
        parser.add_argument("--x", source="D")
    parser.add_argument("--x", source="B.D")


def test_default_source(configs):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-A", config=True)
    parser.add_argument("-B", config=True)
    parser.set_default_source("A")
    parser.add_argument("--foo", type=int)
    parser.set_default_source("B")
    parser.add_argument("--bar")
    parser.clear_default_source()
    parser.add_argument("--baz")
    args = parser.parse_args(["-A", configs["a"], "-B", configs["b"], "--baz", "1"])
    assert type(args) is argparse.Namespace
    assert args == argparse.Namespace(A=MagiConfig(foo=2), B=MagiConfig(bar="b"), baz="1")


def test_auto_source(configs):
    parser = error_raising(magiconfig.ArgumentParser(auto_source=True))
    parser.add_argument("-A", config=True)
    parser.add_argument("--foo", type=int)
    parser.add_argument("-B", config=True)
    parser.add_argument("--bar")
    args = parser.parse_args(["-A", configs["a"], "-B", configs["b"]])
    assert args == MagiConfig(A=MagiConfig(foo=2), B=MagiConfig(bar="b"))


def test_nargs_join(configs):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-A", config=True, nargs="+", obj=ASK)
    parser.add_argument("--foo", type=int, source="A")
    parser.add_argument("--other", type=int, source="A")
    args = parser.parse_args(["-A", configs["a"], configs["a2"]])
    assert args.A == MagiConfig(foo=5, other=1)
    assert magiconfig.imported(args.A) == [(configs["a"], "config"), (configs["a2"], "config")]
    args = parser.parse_args(["-A", configs["a2"], configs["a"]])
    assert args.A == MagiConfig(foo=2, other=1)
    # 1 or N objects
    args = parser.parse_args(["-A", configs["multi"], configs["multi"], "--A.obj", "c.one", "c.two"])
    assert args.A.foo == 8
    args = parser.parse_args(["-A", configs["multi"], "--A.obj", "c.one"])
    assert args.A.foo == 7
    with pytest.raises(MagiConfigError, match="argument -A: must specify either 1 or N"):
        parser.parse_args(["-A", configs["multi"], configs["multi"], configs["multi"], "--A.obj", "c.one", "c.two"])


def test_imported_prefix_false(configs, tmp_path):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-C", config=True, prefix=False, nargs="+")
    parser.add_argument("--foo", type=int, source="C")
    parser.add_argument("-B", config=True, prefix=False)
    parser.add_argument("--bar", source="B")
    args = parser.parse_args(["-C", configs["a"], configs["a2"], "-B", configs["b"]])
    assert args == MagiConfig(foo=5, bar="b")
    assert magiconfig.imported(args) == [(configs["a"], "config"), (configs["a2"], "config"), (configs["b"], "config")]
    path = tmp_path / "out.py"
    parser.write_config(args, str(path))
    text = path.read_text()
    assert f"# imported from: {configs['a']} (obj: config)\n# imported from: {configs['a2']} (obj: config)\n# imported from: {configs['b']} (obj: config)\nconfig = MagiConfig()" in text


def test_mutex_source():
    parser = make_parser()
    group = parser.add_mutually_exclusive_group(source="A")
    group.add_argument("--x", action="store_true")
    group.add_argument("--y", action="store_true")
    with pytest.raises(argparse.ArgumentError, match="not allowed with"):
        parser.parse_args(["--x", "--y"])
    assert parser.parse_args(["--x"]).A.x is True


def test_namespace_types(configs):
    # only config args (plus help) -> MagiConfig
    parser = make_parser()
    assert type(parser.parse_args([])) is MagiConfig
    # top-level args too -> mixed mode, plain Namespace
    parser.add_argument("--top", default=1)
    args = parser.parse_args(["-A", configs["a"]])
    assert type(args) is argparse.Namespace
    assert args == argparse.Namespace(A=MagiConfig(foo=2), B=MagiConfig(bar="none"), top=1)
    # a provided namespace is used
    ns = argparse.Namespace(existing=True)
    assert parser.parse_args([], namespace=ns) is ns
    assert ns.existing


def test_cross_section_conflicts():
    parser = make_parser()
    with pytest.raises(argparse.ArgumentError, match="conflicting option string: --foo"):
        parser.add_argument("--foo", source="B")
    with pytest.raises(argparse.ArgumentError, match="conflicting option string: --foo"):
        parser.add_argument("--foo")
    parser.add_argument("--top")
    with pytest.raises(argparse.ArgumentError, match="conflicting option string: --top"):
        parser.add_argument("--top", source="A")
    # conflict_handler='resolve' applies only to top-level arguments
    parser = make_parser(conflict_handler="resolve")
    with pytest.raises(argparse.ArgumentError):
        parser.add_argument("--foo")


def test_abbrev_across_sections(configs):
    parser = make_parser()
    parser.add_argument("--foobar", source="B")
    parser.add_argument("--top")
    assert parser.parse_args(["--fooba", "x", "--to", "1"]).B.foobar == "x"
    with pytest.raises(argparse.ArgumentError, match="ambiguous option: --fo could match --foo, --foobar"):
        parser.parse_args(["--fo", "1"])
    assert parser.parse_args(["--foo=3"]).A.foo == 3


def test_double_dash():
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-A", config=True)
    parser.add_argument("--foo", source="A")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args(["--foo", "1", "--", "--foo", "2"])
    assert args.A.foo == "1"
    assert args.rest == ["--foo", "2"]


def test_exit_on_error(capsys):
    parser = magiconfig.ArgumentParser(prog="PROG", exit_on_error=False)
    parser.add_argument("-A", config=True)
    parser.add_argument("--foo", type=int, source="A")
    with pytest.raises(argparse.ArgumentError, match="invalid int value"):
        parser.parse_args(["--foo", "x"])
    parser = magiconfig.ArgumentParser(prog="PROG")
    parser.add_argument("-A", config=True)
    parser.add_argument("--foo", type=int, source="A")
    with pytest.raises(SystemExit):
        parser.parse_args(["--foo", "x"])
    assert capsys.readouterr().err == "usage: PROG [-h] [-A A] [--foo FOO]\nPROG: error: argument --foo: invalid int value: 'x'\n"


def test_unrecognized(capsys):
    parser = make_parser()
    with pytest.raises(argparse.ArgumentError, match="unrecognized arguments: --A.nope"):
        parser.parse_args(["--A.nope", "1"])


def test_help_missing_required_nested(capsys):
    parser = magiconfig.ArgumentParser(prog="PROG")
    parser.add_argument("-A", config=True, required=True)
    parser.add_argument("--foo", required=True, source="A")
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0
    assert "-A A" in capsys.readouterr().out


def test_write_separate(configs, tmp_path):
    parser = make_parser()
    args = parser.parse_args(["-A", configs["a"], "--foo", "3", "-B", configs["b"]])
    out = tmp_path / "out.py"
    parser.write_config(args, str(out), separate=True)
    assert not out.exists()
    out_a = tmp_path / "out_A.py"
    out_b = tmp_path / "out_B.py"
    assert out_a.read_text() == f"from magiconfig import MagiConfig\n\n# imported from: {configs['a']} (obj: config)\nconfig = MagiConfig()\nconfig.foo = 3"
    args2 = parser.parse_args(["-A", str(out_a), "-B", str(out_b)])
    assert args2 == args


def test_write_separate_rest(configs, tmp_path):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-A", config=True)
    parser.add_argument("--foo", type=int, source="A")
    parser.add_argument("-C", config=True, prefix=False)
    parser.add_argument("--bar", source="C")
    args = parser.parse_args(["--foo", "1", "--bar", "2"])
    out = tmp_path / "out.py"
    parser.write_config(args, str(out), separate=True)
    assert magiconfig.import_config(str(tmp_path / "out_A.py"), "config") == MagiConfig(foo=1)
    assert magiconfig.import_config(str(out), "config") == MagiConfig(bar="2")


def test_subparsers_with_root_config(configs):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-A", config=True)
    parser.add_argument("--foo", type=int, source="A")
    subparsers = parser.add_subparsers(dest="mode")
    one = subparsers.add_parser("one")
    one.add_argument("-B", config=True)
    one.add_argument("--bar", source="B")
    subparsers.add_parser("two")
    args = parser.parse_args(["-A", configs["a"], "one", "-B", configs["b"]])
    assert args == MagiConfig(A=MagiConfig(foo=2), mode="one", B=MagiConfig(bar="b"))
    assert magiconfig.imported(args.B) == [(configs["b"], "config")]
    args = parser.parse_args(["two"])
    assert args == MagiConfig(A=MagiConfig(foo=None), mode="two")


def test_parents(configs):
    parent = magiconfig.ArgumentParser(add_help=False)
    parent.add_argument("--top", default=1)
    parent.add_argument("-A", config=True)
    parent.add_argument("--foo", type=int, source="A")
    parent.set_default_source("A")
    parent.add_argument("--other", type=int)
    group = parent.add_mutually_exclusive_group(source="A")
    group.add_argument("--x", action="store_true")
    group.add_argument("--y", action="store_true")
    plain = argparse.ArgumentParser(add_help=False)
    plain.add_argument("--plain", default="p")
    child = error_raising(magiconfig.ArgumentParser(parents=[parent, plain]))
    child.add_argument("--more", source="A")
    args = child.parse_args(["-A", configs["a"], "--other", "3", "--more", "m"])
    assert args == argparse.Namespace(top=1, plain="p", A=MagiConfig(foo=2, other=3, x=False, y=False, more="m"))
    with pytest.raises(argparse.ArgumentError, match="not allowed with"):
        child.parse_args(["--x", "--y"])
    # the parent is unchanged
    assert parent.parse_args(["-A", configs["a"]]).A == MagiConfig(foo=2, other=None, x=False, y=False)
