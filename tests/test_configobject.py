"""ConfigObjects: standalone build, command-line building, custom, nesting, proxies, inheritance, docs, mutex."""
import argparse
import warnings

import pytest

import magiconfig
from magiconfig import MagiConfig, MagiConfigError, ConfigObject, ASK
from conftest import error_raising, make_config


class Inner(ConfigObject):
    _description = "innermost object"
    _arguments = dict(z=dict(type=int, default=0, help="z arg"))


class Middle(ConfigObject):
    _arguments = dict(
        y=dict(type=str, default="y", help="y arg"),
        inner=dict(type=Inner, help="inner config"),
    )


class Outer(ConfigObject):
    """Extra documentation."""
    _description = "outer object"
    _arguments = dict(
        x=dict(type=float, required=True, help="x arg"),
        mode=dict(choices=["a", "b"], default="a", help="mode arg"),
        middle=dict(type=Middle, help="middle config"),
        hidden=dict(type=int, default=3, disable=True, help="hidden arg"),
    )


class Point(ConfigObject):
    _arguments = dict(
        x=dict(type=int, default=0, help="x coordinate"),
        y=dict(type=int, default=0, help="y coordinate"),
    )


def test_build_from_config():
    point = Point.build(MagiConfig(x=1))
    assert type(point) is Point
    assert point == Point(x=1, y=0)
    assert repr(point) == "MagiConfig(x=1, y=0)"
    # types are applied
    assert Point.build(MagiConfig(x="2")).x == 2


def test_build_from_path(tmp_path):
    path = make_config(tmp_path / "p.py", obj="pt", x=4, y=5, extra=1)
    assert Point.build(path, obj="pt") == Point(x=4, y=5)
    with pytest.raises(MagiConfigError, match="unknown attributes: extra"):
        Point.build(path, obj="pt", strict=True)


def test_build_required_choices():
    with pytest.raises(argparse.ArgumentError, match="required"):
        Outer.build(MagiConfig())
    with pytest.raises(argparse.ArgumentError, match="invalid choice"):
        Outer.build(MagiConfig(x=1, mode="c"))
    outer = Outer.build(MagiConfig(x=1))
    assert outer.x == 1.0 and outer.mode == "a" and outer.hidden == 3
    assert outer.middle == Middle(y="y", inner=Inner(z=0))
    # disabled arguments can still be set by configs
    assert Outer.build(MagiConfig(x=1, hidden=4)).hidden == 4


def test_command_line():
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("--point", type=Point)
    args = parser.parse_args(["--point.x", "3"])
    assert args.point == Point(x=3, y=0)
    assert args._sources["point"] == MagiConfig(x=3, y=0)
    with pytest.raises(argparse.ArgumentError):
        parser.parse_args(["--x", "3"])


def test_command_line_no_prefix(tmp_path):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-P", "--point", type=Point, prefix=False)
    args = parser.parse_args(["--x", "3"])
    # merged: the source's fields are stored instead of the built object
    assert args == MagiConfig(x=3, y=0)
    path = make_config(tmp_path / "p.py", y=2)
    assert parser.parse_args(["-P", path, "--x", "3"]) == MagiConfig(x=3, y=2)


def test_config_file(tmp_path):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("--point", type=Point, obj=ASK)
    path = make_config(tmp_path / "p.py", obj="pt", x=4)
    assert parser.parse_args(["--point", path, "--point.obj", "pt", "--point.y", "1"]).point == Point(x=4, y=1)


def test_custom():
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        parser.add_argument("--outer", type=Outer, custom=dict(
            obj=True,
            x=dict(default=1.5, required=False, help="new help"),
            hidden=dict(help="now visible"),
            mode=dict(dest="other"),
            unknown=True,
        ))
    messages = [str(w.message) for w in caught]
    assert any("modification of dest is not allowed" in m for m in messages)
    assert any("unknown argument unknown" in m for m in messages)
    help_text = parser.format_help()
    assert "--outer.obj OBJ" in help_text
    assert "new help" in help_text
    assert "now visible" in help_text
    args = parser.parse_args(["--outer.hidden", "5"])
    assert args.outer.x == 1.5 and args.outer.hidden == 5 and args.outer.mode == "a"
    # the class definition is not modified
    assert Outer._arguments["x"] == dict(type=float, required=True, help="x arg")


def test_nested(tmp_path):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-O", "--outer", type=Outer)
    args = parser.parse_args(["--outer.x", "1", "--outer.middle.inner.z", "5"])
    assert args.outer.middle.inner == Inner(z=5)
    assert args.outer.middle.y == "y"

    inner_path = make_config(tmp_path / "inner.py", z=1)
    middle_path = make_config(tmp_path / "middle.py", y="from file", inner=inner_path)
    outer_path = make_config(tmp_path / "outer.py", x=2.0, middle=MagiConfig(y="inline", inner=MagiConfig(z=2)))
    outer_path2 = make_config(tmp_path / "outer2.py", x=2.0, middle=middle_path)

    # inline sub-configs
    args = parser.parse_args(["-O", outer_path])
    assert args.outer.middle == Middle(y="inline", inner=Inner(z=2))
    # sub-config paths
    args = parser.parse_args(["-O", outer_path2])
    assert args.outer.middle == Middle(y="from file", inner=Inner(z=1))
    assert magiconfig.imported(args._sources["outer"]._sources["middle"]._sources["inner"]) == [(inner_path, "config")]
    # command line > parent config
    args = parser.parse_args(["-O", outer_path, "--outer.middle", middle_path, "--outer.middle.inner.z", "9"])
    assert args.outer.middle == Middle(y="from file", inner=Inner(z=9))


def test_write_read(tmp_path):
    parser = error_raising(magiconfig.ArgumentParser(basic=True))
    parser.add_argument("--flag", type=int, default=0)
    parser.add_argument("--outer", type=Outer)
    args = parser.parse_args(["--outer.x", "1", "--outer.middle.inner.z", "5", "--flag", "2"])
    path = tmp_path / "out.py"
    parser.write_config(args, str(path))
    assert "outer.middle.inner.z = 5" in path.read_text()
    assert parser.parse_args(["-C", str(path)]) == args
    # separate
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("--outer", type=Outer)
    args = parser.parse_args(["--outer.x", "1"])
    parser.write_config(args, str(path), separate=True)
    assert parser.parse_args(["--outer", str(tmp_path / "out_outer.py")]) == args


class Existing:
    """A class that is not a ConfigObject."""
    def __init__(self, a, b=2):
        self.a = a
        self.b = b

    def __eq__(self, other):
        return vars(self) == vars(other)


class ExistingProxy(ConfigObject):
    _arguments = dict(
        a=dict(type=int, required=True, help="a arg"),
        b=dict(type=int, default=2, help="b arg"),
    )
    _principal = Existing


def test_proxy(tmp_path):
    parser = error_raising(magiconfig.ArgumentParser(basic=True))
    parser.add_argument("--ex", type=ExistingProxy)
    args = parser.parse_args(["--ex.a", "1"])
    assert type(args.ex) is Existing
    assert args.ex == Existing(1, 2)
    path = tmp_path / "out.py"
    parser.write_config(args, str(path))
    assert parser.parse_args(["-C", str(path)]) == args
    assert ExistingProxy.build(MagiConfig(a=3)) == Existing(3)


class Point3D(Point):
    _arguments = Point._arguments | dict(
        z=dict(type=int, default=0, help="z coordinate"),
        y=dict(type=int, default=10, help="y coordinate (new default)"),
    )


class Point1D(Point):
    _arguments = {k: v for k, v in Point._arguments.items() if k != "y"}


def test_inheritance():
    assert Point3D.build(MagiConfig()) == Point3D(x=0, y=10, z=0)
    assert Point1D.build(MagiConfig(y=3)) == Point1D(x=0)


def test_generated_doc():
    assert Outer.__doc__ == "\n\n".join([
        "outer object",
        "Extra documentation.",
        "\n".join([
            "Arguments:",
            "    x (float, required): x arg",
            "    mode (default: 'a'): mode arg",
            "    middle (Middle): middle config",
            "    hidden (int, default: 3): hidden arg",
        ]),
    ])
    assert Middle.__doc__.startswith("Arguments:\n    y (str, default: 'y'): y arg")


class Exclusive(ConfigObject):
    _arguments = dict(
        a=dict(action="store_true", help="a arg"),
        b=dict(action="store_true", help="b arg"),
        c=dict(type=int, default=0, help="c arg"),
    )
    _mutually_exclusive = [dict(arguments=["a", "b"], required=False)]


def test_mutex():
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("--ex", type=Exclusive)
    assert parser.parse_args(["--ex.a"]).ex == Exclusive(a=True, b=False, c=0)
    with pytest.raises(argparse.ArgumentError, match="not allowed with"):
        parser.parse_args(["--ex.a", "--ex.b"])
    # not enforced for config values
    assert Exclusive.build(MagiConfig(a=True, b=True)) == Exclusive(a=True, b=True, c=0)


def test_locked():
    parser = magiconfig.ArgumentParser()
    parser.add_argument("--point", type=Point)
    with pytest.raises(MagiConfigError, match="cannot be added"):
        parser.add_argument("--w", source="point")
    with pytest.raises(MagiConfigError, match="cannot be added"):
        parser.add_mutually_exclusive_group(source="point")


def test_nested_prefix_false():
    class Bad(ConfigObject):
        _arguments = dict(point=dict(type=Point, prefix=False))
    parser = magiconfig.ArgumentParser()
    with pytest.raises(MagiConfigError, match="prefix=False"):
        parser.add_argument("--bad", type=Bad)


def test_transient_member():
    class WithTransient(ConfigObject):
        _arguments = dict(a=dict(type=int, default=1), verbose=dict(action="store_true", transient=True))
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("--w", type=WithTransient)
    args = parser.parse_args(["--w.verbose"])
    # transients are passed to the constructor, but never written
    assert args.w == WithTransient(a=1, verbose=True)
    assert args._sources["w"].vars() == {"a": 1}
