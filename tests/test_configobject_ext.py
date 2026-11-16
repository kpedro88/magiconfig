"""Typed ConfigObject args (action="specify_type", src) and containers (container=list/dict)."""
import argparse
import os
import subprocess
import sys
import textwrap

import pytest

import magiconfig
from magiconfig import MagiConfig, MagiConfigError, ConfigObject, ASK
from conftest import error_raising, make_config

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ResNet(ConfigObject):
    _description = "residual network"
    _arguments = dict(depth=dict(type=int, default=50, help="depth"))


class VGG(ConfigObject):
    _arguments = dict(
        depth=dict(type=int, default=16, help="depth"),
        bn=dict(action="store_true", help="batch norm"),
    )


class Unrelated(ConfigObject):
    _arguments = dict(name=dict(default="u"))


class NotAConfigObject:
    pass


class Net(ConfigObject):
    _arguments = dict(
        backbone=dict(action="specify_type", default=ResNet, help="backbone class and config"),
        width=dict(type=int, default=1),
    )


def make_parser(**kwargs):
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    kwargs.setdefault("default", ResNet)
    parser.add_argument("-M", "--model", action="specify_type", help="model class and config file", **kwargs)
    return parser


# typed args

def test_typed_class_only():
    parser = make_parser()
    args = parser.parse_args([])
    assert type(args.model) is ResNet and args.model == ResNet(depth=50)
    args = parser.parse_args(["--model", "VGG", "--model.bn"])
    assert args.model == VGG(depth=16, bn=True)
    assert args._sources["model"] == (VGG, MagiConfig(depth=16, bn=True))


def test_typed_config_files(tmp_path):
    parser = make_parser()
    vgg1 = make_config(tmp_path / "vgg1.py", depth=11)
    vgg2 = make_config(tmp_path / "vgg2.py", bn=True)
    assert parser.parse_args(["--model", "VGG", vgg1, "--model.depth", "13"]).model == VGG(depth=13, bn=False)
    assert parser.parse_args(["--model", "VGG", vgg1, vgg2]).model == VGG(depth=11, bn=True)
    with pytest.raises(argparse.ArgumentError, match="expected at least one argument"):
        parser.parse_args(["--model"])


def test_typed_metavar_help():
    parser = make_parser(choices=[ResNet, VGG], obj=ASK)
    help_text = parser.format_help()
    assert "--model TYPE [CONFIG ...]" in help_text
    assert "residual network" in help_text and "--model.depth DEPTH" in help_text
    parser.parse_args(["--model", "VGG"])
    help_text = parser.format_help()
    assert "--model.bn" in help_text and "residual network" not in help_text
    assert parser.format_usage() == "usage: PROG [-h] [-M TYPE [CONFIG ...]] [--model.obj OBJ]\n"
    parser = magiconfig.ArgumentParser(prog="PROG", formatter_class=magiconfig.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--model", action="specify_type", default=ResNet, help="model")
    assert "model (default: ResNet)" in parser.format_help()


def test_typed_parent_config(tmp_path):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("--net", type=Net)
    vgg = make_config(tmp_path / "vgg.py", depth=19)
    for value, expected in [
        (VGG, VGG(depth=16, bn=False)),
        ("VGG", VGG(depth=16, bn=False)),
        ((VGG, vgg), VGG(depth=19, bn=False)),
        ((VGG, MagiConfig(bn=True)), VGG(depth=16, bn=True)),
        (MagiConfig(depth=3), ResNet(depth=3)),
    ]:
        assert parser._config_parsers["net"].parse([], MagiConfig(backbone=value), False)[0].backbone == expected, value
        # also through a written parent config file
        parent = make_config(tmp_path / f"net_{len(os.listdir(tmp_path))}.py", backbone=value)
        assert parser.parse_args(["--net", parent]).net.backbone == expected, value
    # nested typed flags
    args = parser.parse_args(["--net.backbone", "VGG", vgg, "--net.backbone.depth", "8", "--net.width", "2"])
    assert args.net == Net(backbone=VGG(depth=8, bn=False), width=2)


def test_typed_precedence(tmp_path):
    parser = error_raising(magiconfig.ArgumentParser())
    parser.add_argument("-N", "--net", type=Net)
    vgg = make_config(tmp_path / "vgg.py", depth=19)
    resnet = make_config(tmp_path / "resnet.py", depth=101)
    net = make_config(tmp_path / "net.py", backbone=(VGG, vgg))
    # parent config
    assert parser.parse_args(["-N", net]).net.backbone == VGG(depth=19, bn=False)
    # command line replaces the parent config's class and file
    assert parser.parse_args(["-N", net, "--net.backbone", "ResNet"]).net.backbone == ResNet(depth=50)
    assert parser.parse_args(["-N", net, "--net.backbone", "ResNet", resnet]).net.backbone == ResNet(depth=101)
    # sub-flags override in every case
    assert parser.parse_args(["-N", net, "--net.backbone.depth", "1"]).net.backbone == VGG(depth=1, bn=False)
    # default
    assert parser.parse_args([]).net.backbone == ResNet(depth=50)


def test_typed_unrelated_classes():
    parser = make_parser()
    assert parser.parse_args(["--model", "Unrelated"]).model == Unrelated(name="u")


def test_typed_choices(tmp_path):
    parser = make_parser(choices=[ResNet, VGG])
    with pytest.raises(argparse.ArgumentError, match=r"argument -M/--model: invalid choice: 'Unrelated' \(choose from ResNet, VGG\)"):
        parser.parse_args(["--model", "Unrelated"])
    with pytest.raises(argparse.ArgumentError, match="invalid choice: 'Unrelated'"):
        parser._config_parsers["model"].parse([], Unrelated, False)
    # choices by name
    parser = make_parser(choices=["ResNet"])
    assert parser.parse_args(["--model", "ResNet"]).model == ResNet(depth=50)
    with pytest.raises(argparse.ArgumentError, match="invalid choice"):
        parser.parse_args(["--model", "VGG"])
    # config_choices
    allowed = make_config(tmp_path / "allowed.py", depth=1)
    parser = make_parser(config_choices=[allowed])
    assert parser.parse_args(["--model", "ResNet", allowed]).model == ResNet(depth=1)
    with pytest.raises(argparse.ArgumentError, match="invalid choice: 'other.py'"):
        parser.parse_args(["--model", "ResNet", "other.py"])


def test_typed_name_resolution(tmp_path, monkeypatch):
    parser = make_parser(src=ASK)
    # registry
    assert parser.parse_args(["--model", "VGG"]).model == VGG(depth=16, bn=False)
    with pytest.raises(MagiConfigError, match="unknown ConfigObject class Nope"):
        parser.parse_args(["--model", "Nope"])
    # src as a file
    models = tmp_path / "models.py"
    models.write_text(textwrap.dedent("""
        from magiconfig import ConfigObject
        class FileModel(ConfigObject):
            _arguments = dict(size=dict(type=int, default=2))
        class Dup(ConfigObject):
            _arguments = dict(a=dict(default=1))
    """))
    args = parser.parse_args(["--model", "FileModel", "--model.src", str(models), "--model.size", "3"])
    assert type(args.model).__name__ == "FileModel" and args.model.size == 3
    with pytest.raises(MagiConfigError, match=f"class Missing not found in {models}"):
        parser.parse_args(["--model", "Missing", "--model.src", str(models)])
    # src as a module
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "nets.py").write_text(textwrap.dedent("""
        from magiconfig import ConfigObject
        class Dup(ConfigObject):
            _arguments = dict(b=dict(default=2))
    """))
    monkeypatch.syspath_prepend(str(tmp_path))
    args = parser.parse_args(["--model", "Dup", "--model.src", "pkg.nets"])
    assert args.model.b == 2
    # ambiguous registry name
    with pytest.raises(MagiConfigError, match="ambiguous"):
        parser.parse_args(["--model", "Dup"])
    # src default
    parser = make_parser(src="pkg.nets")
    assert parser.parse_args(["--model", "Dup"]).model.b == 2


def test_typed_errors():
    parser = magiconfig.ArgumentParser()
    with pytest.raises(MagiConfigError, match="cannot be combined with type"):
        parser.add_argument("--m", action="specify_type", type=ResNet)
    with pytest.raises(MagiConfigError, match="src is only supported"):
        parser.add_argument("--p", type=ResNet, src=ASK)
    parser = make_parser()
    with pytest.raises(MagiConfigError, match="not a ConfigObject"):
        parser._config_parsers["model"].parse([], NotAConfigObject, False)


def test_typed_no_class():
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("--model", action="specify_type")
    assert parser.parse_args([]) == MagiConfig(model=None)
    assert parser.parse_args(["--model", "VGG"]).model == VGG(depth=16, bn=False)
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("--model", action="specify_type", required=True)
    with pytest.raises(argparse.ArgumentError, match="required"):
        parser.parse_args([])


def test_typed_write_read(tmp_path):
    # inside a section: written with the parent config
    parser = error_raising(magiconfig.ArgumentParser(basic=True))
    parser.add_argument("--net", type=Net)
    args = parser.parse_args(["--net.backbone", "VGG", "--net.backbone.depth", "3"])
    out = tmp_path / "out.py"
    parser.write_config(args, str(out))
    text = out.read_text()
    assert "from test_configobject_ext import VGG" in text
    assert "config.net.backbone = (VGG, MagiConfig(bn=False, depth=3))" in text
    assert parser.parse_args(["-C", str(out)]) == args
    # top level, separate
    parser = make_parser()
    args = parser.parse_args(["--model", "VGG", "--model.depth", "3"])
    parser.write_config(args, str(out), separate=True)
    text = (tmp_path / "out_model.py").read_text()
    assert text.startswith("# type: VGG (src: test_configobject_ext)\nfrom magiconfig import MagiConfig\n")
    assert parser.parse_args(["--model", "VGG", str(tmp_path / "out_model.py")]) == args


def test_typed_write_read_file_class(tmp_path):
    models = tmp_path / "models2.py"
    models.write_text("from magiconfig import ConfigObject\nclass M2(ConfigObject):\n    _arguments = dict(size=dict(type=int, default=2))\n")
    parser = error_raising(magiconfig.ArgumentParser(basic=True))
    parser.add_argument("--model", action="specify_type", src=ASK, choices=["M2"])
    args = parser.parse_args(["--model", "M2", "--model.src", str(models), "--model.size", "5"])
    out = tmp_path / "out.py"
    parser.write_config(args, str(out))
    assert f"M2 = import_config({str(models)!r}, 'M2')" in out.read_text()
    args2 = parser.parse_args(["-C", str(out)])
    assert args2 == args and type(args2.model) is type(args.model)


def test_typed_write_read_main(tmp_path):
    script = tmp_path / "script.py"
    script.write_text(textwrap.dedent(f"""
        import magiconfig
        class Local(magiconfig.ConfigObject):
            _arguments = dict(size=dict(type=int, default=2))
        parser = magiconfig.ArgumentParser(basic=True)
        parser.add_argument("--model", action="specify_type")
        args = parser.parse_args(["--model", "Local", "--model.size", "4"])
        parser.write_config(args, {str(tmp_path / 'out.py')!r})
        print(parser.parse_args(["-C", {str(tmp_path / 'out.py')!r}]) == args, args.model.size)
    """))
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=REPO))
    assert result.stdout == "True 4\n", result.stderr
    assert "config.model = ('Local', MagiConfig(size=4))" in (tmp_path / "out.py").read_text()


# containers

class Layer(ConfigObject):
    _arguments = dict(
        dim=dict(type=int, default=1, help="dimension"),
        act=dict(default="relu", help="activation"),
    )


class Conv(ConfigObject):
    _arguments = dict(kernel=dict(type=int, default=3), backbone=dict(action="specify_type", default=ResNet))


class Dense(ConfigObject):
    _arguments = dict(units=dict(type=int, default=8))


def list_parser(**kwargs):
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("--layers", type=Layer, container=list, help="layer configs", **kwargs)
    return parser


def typed_parser(container=dict, **kwargs):
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("--layers", action="specify_type", container=container, choices=[Conv, Dense], help="layers", **kwargs)
    return parser


def test_container_list_sources(tmp_path):
    parser = list_parser()
    assert parser.parse_args([]).layers == []
    l1 = make_config(tmp_path / "l1.py", dim=5)
    path = tmp_path / "layers.py"
    path.write_text(f"from magiconfig import MagiConfig\nconfig = [{l1!r}, MagiConfig(act='tanh')]\n")
    args = parser.parse_args(["--layers", str(path)])
    assert args.layers == [Layer(dim=5, act="relu"), Layer(dim=1, act="tanh")]
    # parent config value / default
    parser2 = list_parser(default=[MagiConfig(dim=2)])
    assert parser2.parse_args([]).layers == [Layer(dim=2, act="relu")]


def test_container_element_flags(tmp_path):
    parser = list_parser()
    path = tmp_path / "layers.py"
    path.write_text("from magiconfig import MagiConfig\nconfig = [MagiConfig(dim=5), MagiConfig(dim=6)]\n")
    l9 = make_config(tmp_path / "l9.py", dim=9)
    # replace an element
    args = parser.parse_args(["--layers", str(path), "--layers.1", l9])
    assert [layer.dim for layer in args.layers] == [5, 9]
    # bare element flag resets to the class defaults
    assert [layer.dim for layer in parser.parse_args(["--layers", str(path), "--layers.0"]).layers] == [1, 6]
    # append at len
    args = parser.parse_args(["--layers", str(path), "--layers.3", "--layers.2", "--layers.3.dim", "4"])
    assert [layer.dim for layer in args.layers] == [5, 6, 1, 4]
    # gap
    with pytest.raises(MagiConfigError, match="consecutive"):
        parser.parse_args(["--layers", str(path), "--layers.3"])
    # built from element flags only
    args = parser.parse_args(["--layers.0", "--layers.0.dim", "10", "--layers.1", "--layers.1.dim", "5"])
    assert args.layers == [Layer(dim=10, act="relu"), Layer(dim=5, act="relu")]
    # sub-flags alone never create an element
    with pytest.raises(argparse.ArgumentError, match="unrecognized arguments: --layers.0.dim"):
        parser.parse_args(["--layers.0.dim", "10"])
    with pytest.raises(argparse.ArgumentError, match="unrecognized arguments: --layers.5.dim"):
        parser.parse_args(["--layers", str(path), "--layers.5.dim", "10"])
    with pytest.raises(MagiConfigError, match="invalid list index"):
        parser.parse_args(["--layers.x"])


def test_container_precedence_order(tmp_path):
    parser = list_parser()
    path = tmp_path / "layers.py"
    path.write_text("from magiconfig import MagiConfig\nconfig = [MagiConfig(dim=5), MagiConfig(dim=6)]\n")
    l9 = make_config(tmp_path / "l9.py", dim=9, act="gelu")
    expected = [Layer(dim=5, act="relu"), Layer(dim=64, act="gelu")]
    assert parser.parse_args(["--layers.1.dim", "64", "--layers", str(path), "--layers.1", l9]).layers == expected
    assert parser.parse_args(["--layers", str(path), "--layers.1", l9, "--layers.1.dim", "64"]).layers == expected


def test_container_join(tmp_path):
    parser = list_parser()
    a = tmp_path / "a.py"
    a.write_text("from magiconfig import MagiConfig\nconfig = [MagiConfig(dim=1), MagiConfig(dim=2)]\n")
    b = tmp_path / "b.py"
    b.write_text("from magiconfig import MagiConfig\nconfig = [MagiConfig(dim=3)]\n")
    assert [layer.dim for layer in parser.parse_args(["--layers", str(a), str(b)]).layers] == [3, 2]
    parser = typed_parser()
    c = tmp_path / "c.py"
    c.write_text("from test_configobject_ext import Conv, Dense\nconfig = {'enc': Conv, 'dec': Dense}\n")
    d = tmp_path / "d.py"
    d.write_text("from test_configobject_ext import Dense\nconfig = {'enc': Dense}\n")
    assert parser.parse_args(["--layers", str(c), str(d)]).layers == {"enc": Dense(units=8), "dec": Dense(units=8)}


def test_container_typed_dict(tmp_path):
    parser = typed_parser()
    conv = make_config(tmp_path / "conv.py", kernel=5)
    args = parser.parse_args(["--layers.enc", "Conv", conv, "--layers.dec", "Dense", "--layers.dec.units", "64"])
    assert args.layers == {"enc": Conv(kernel=5, backbone=ResNet(depth=50)), "dec": Dense(units=64)}
    assert args._sources["layers"]["dec"] == (Dense, MagiConfig(units=64))
    # from a parent config value, mixed forms
    value = {"enc": (Conv, conv), "dec": Dense, "mid": (Conv, MagiConfig(kernel=7))}
    args = parser._config_parsers["layers"].parse(["--layers.new", "Dense"], value, False)[0]
    assert args == {"enc": Conv(kernel=5, backbone=ResNet(depth=50)), "dec": Dense(units=8), "mid": Conv(kernel=7, backbone=ResNet(depth=50)), "new": Dense(units=8)}
    # nested ConfigObjects (including typed args) inside elements
    args = parser.parse_args(["--layers.enc", "Conv", "--layers.enc.backbone", "VGG", "--layers.enc.backbone.depth", "4"])
    assert args.layers["enc"].backbone == VGG(depth=4, bn=False)
    # the class is the minimum
    with pytest.raises(argparse.ArgumentError, match="expected at least one argument"):
        parser.parse_args(["--layers.enc"])
    with pytest.raises(MagiConfigError, match="a class must be specified"):
        parser._config_parsers["layers"].parse([], {"enc": MagiConfig()}, False)


def test_container_typed_list():
    parser = typed_parser(container=list)
    args = parser.parse_args(["--layers.0", "Dense", "--layers.1", "Conv"])
    assert [type(layer) for layer in args.layers] == [Dense, Conv]


def test_container_base_args(tmp_path, monkeypatch):
    pkg = tmp_path / "pkg2"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "layers.py").write_text("from magiconfig import ConfigObject\nclass Conv(ConfigObject):\n    _arguments = dict(k=dict(default=1))\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    other = tmp_path / "other.py"
    other.write_text("from magiconfig import ConfigObject\nclass Conv(ConfigObject):\n    _arguments = dict(k=dict(default=2))\n")
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("--layers", action="specify_type", container=dict, src=ASK, obj=ASK)
    cfg = make_config(tmp_path / "cfg.py", obj="special", k=9)
    # shared src, per-element override
    args = parser.parse_args([
        "--layers.src", "pkg2.layers", "--layers.a", "Conv", "--layers.b", "Conv", "--layers.b.src", str(other),
        "--layers.c", "Conv", cfg, "--layers.c.obj", "special",
    ])
    assert args.layers["a"].k == 1 and args.layers["b"].k == 2 and args.layers["c"].k == 9
    assert "--layers.src SRC" in parser.format_help() and "--layers.a.src SRC" in parser.format_help()


def test_container_keys_and_kinds(tmp_path):
    parser = typed_parser()
    for key in ("src", "obj", "strict"):
        with pytest.raises(MagiConfigError, match="invalid key"):
            parser._config_parsers["layers"].parse([], {key: Dense}, False)
    with pytest.raises(MagiConfigError, match="invalid key"):
        parser._config_parsers["layers"].parse([], {"a.b": Dense}, False)
    with pytest.raises(MagiConfigError, match="expected a dict, got list"):
        parser._config_parsers["layers"].parse([], [Dense], False)
    with pytest.raises(MagiConfigError, match="container must be list or dict"):
        magiconfig.ArgumentParser().add_argument("--x", type=Layer, container=set)


def test_container_abbrev():
    parser = list_parser()
    parser.add_argument("--layersize", type=int)
    with pytest.raises(argparse.ArgumentError, match="unrecognized arguments"):
        parser.parse_args(["--layers.0", "--layers.0.di", "3"])
    # abbreviations elsewhere still work
    assert parser.parse_args(["--layersi", "3"]).layersize == 3


def test_container_help():
    parser = list_parser()
    help_text = parser.format_help()
    assert "layers.N:" in help_text and "--layers.N.dim DIM" in help_text
    parser.parse_args(["--layers.0"])
    help_text = parser.format_help()
    assert "layers.0:" in help_text and "--layers.0.dim DIM" in help_text and "layers.N" not in help_text
    help_text = typed_parser().format_help()
    assert "elements: --layers.KEY TYPE [CONFIG ...] (choose from Conv, Dense)" in help_text


def test_container_parse_twice():
    parser = list_parser()
    assert len(parser.parse_args(["--layers.0", "--layers.1", "--layers.2"]).layers) == 3
    assert len(parser.parse_args(["--layers.0"]).layers) == 1
    assert "--layers.2" not in parser._nested_option_strings


def test_container_write_read(tmp_path):
    for container in (list, dict):
        parser = error_raising(magiconfig.ArgumentParser(basic=True))
        parser.add_argument("--layers", action="specify_type", container=container, choices=[Conv, Dense])
        keys = ["0", "1"] if container is list else ["enc", "dec"]
        args = parser.parse_args([f"--layers.{keys[0]}", "Conv", f"--layers.{keys[0]}.kernel", "5", f"--layers.{keys[1]}", "Dense"])
        out = tmp_path / "out.py"
        parser.write_config(args, str(out))
        assert parser.parse_args(["-C", str(out)]) == args
        # separate
        parser = typed_parser(container=container)
        args = parser.parse_args([f"--layers.{keys[0]}", "Conv", f"--layers.{keys[1]}", "Dense", f"--layers.{keys[1]}.units", "2"])
        parser.write_config(args, str(out), separate=True)
        assert parser.parse_args(["--layers", str(tmp_path / "out_layers.py")]) == args
    parser = list_parser()
    args = parser.parse_args(["--layers.0", "--layers.0.dim", "3"])
    parser.write_config(args, str(out), separate=True)
    assert (tmp_path / "out_layers.py").read_text().endswith("config = [MagiConfig(act='relu', dim=3)]")
