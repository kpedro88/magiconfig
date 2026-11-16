import copy
import json
import pickle
from collections import OrderedDict

import pytest

import magiconfig
from magiconfig import MagiConfig, MagiConfigError


def read_back(path, obj="config"):
    return magiconfig.import_config(str(path), obj)


def test_dotted_getattr_setattr():
    x = MagiConfig()
    setattr(x, "y.z", "test")
    assert repr(x) == "MagiConfig(y=MagiConfig(z='test'))"
    assert getattr(x, "y.z") == "test"
    setattr(x, "a.b.c", 1)
    assert x.a.b.c == 1
    assert getattr(x, "a.b.c") == 1
    assert not hasattr(x, "a.b.d")
    with pytest.raises(AttributeError):
        x.missing


def test_join():
    config_one = MagiConfig(foo='2', bar=2.0)
    config_two = MagiConfig(foo='3')
    config_three = MagiConfig(bar=3.0, ipsum=True)
    config_one.join(config_two, prefer_other=True)
    config_one.join(config_three)
    assert config_one == MagiConfig(foo='3', bar=2.0, ipsum=True)


def test_hidden_slots():
    x = MagiConfig(a=1, b=2)
    x._transients.add("b")
    x._sources["a"] = MagiConfig(c=3)
    x._imported.append(("file.py", "config"))
    assert vars(x) == {"a": 1, "b": 2}
    assert x == MagiConfig(a=1, b=2)
    assert repr(x) == "MagiConfig(a=1, b=2)"
    assert x.vars() == {"a": 1}
    assert x.vars(transient=True) == {"a": 1, "b": 2}
    for y in (copy.deepcopy(x), pickle.loads(pickle.dumps(x))):
        assert y == x
        assert y._transients == {"b"}
        assert y._sources == {"a": MagiConfig(c=3)}
        assert magiconfig.imported(y) == [("file.py", "config")]


def test_join_propagates_hidden():
    x = MagiConfig(a=1, b=2)
    x._transients.add("a")
    y = MagiConfig(a=3, c=4)
    y._transients.add("c")
    y._sources["c"] = MagiConfig(d=5)
    y._imported.append(("y.py", "config"))
    x.join(y, prefer_other=True)
    assert x == MagiConfig(a=3, b=2, c=4)
    assert x._transients == {"c"}
    assert x._sources == {"c": MagiConfig(d=5)}
    assert magiconfig.imported(x) == [("y.py", "config")]


def test_write_read(tmp_path):
    config = MagiConfig(foo='foo', bar=3.0, sub=MagiConfig(x=[1, 2], y=MagiConfig(z=None)))
    path = tmp_path / "out.py"
    config.write(str(path), "config")
    assert path.read_text() == "\n".join([
        "from magiconfig import MagiConfig",
        "",
        "config = MagiConfig()",
        "config.bar = 3.0",
        "config.foo = 'foo'",
        "config.sub = MagiConfig()",
        "config.sub.x = [1, 2]",
        "config.sub.y = MagiConfig()",
        "config.sub.y.z = None",
    ])
    assert read_back(path) == config


def test_write_transients(tmp_path):
    config = MagiConfig(a=1, b=2, sub=MagiConfig(c=3, d=4))
    config._transients.add("b")
    config.sub._transients.add("d")
    path = tmp_path / "out.py"
    config.write(str(path))
    assert read_back(path) == MagiConfig(a=1, sub=MagiConfig(c=3))


@pytest.mark.parametrize("value", [
    OrderedDict([(1, 2)]),
    MagiConfig(dict=OrderedDict([(1, 2)])),
    [OrderedDict([(1, 2)]), OrderedDict([(3, 4)])],
])
def test_write_read_OrderedDict(tmp_path, value):
    config = MagiConfig(value=value)
    path = tmp_path / "out.py"
    config.write(str(path))
    assert read_back(path) == config


def test_write_OrderedDict_custom(tmp_path):
    def reprOD(obj):
        lines = ["OrderedDict(["]
        for key, val in obj.items():
            lines.append(f'    ({key!r}, {json.dumps(val, sort_keys=True)}),')
        lines.append("])")
        return '\n'.join(lines)
    config = MagiConfig(dict=OrderedDict([(1, 2)]))
    path = tmp_path / "out.py"
    config.write(str(path), "config", class_reprs={OrderedDict: reprOD})
    expected = 'from magiconfig import MagiConfig\nfrom collections import OrderedDict\n\nconfig = MagiConfig()\nconfig.dict = OrderedDict([\n    (1, 2),\n])'
    assert path.read_text() == expected


def test_write_selfref_strict(tmp_path):
    config = MagiConfig(d={})
    config.d[1] = config.d
    # repr for a self-referential object includes "...", will not eval to original
    with pytest.raises(MagiConfigError):
        config.write(str(tmp_path / "out.py"), "config", strict=True)


def test_write_selfref(tmp_path):
    # without strict, the self-referential case is written (incorrectly, but without infinite recursion)
    config = MagiConfig(d={})
    config.d[1] = config.d
    path = tmp_path / "out.py"
    config.write(str(path))
    assert "config.d = {1: {...}}" in path.read_text()


def test_write_sources(tmp_path):
    class Built:
        def __repr__(self):
            return "<unwritable>"
    config = MagiConfig(obj=Built(), x=1)
    config._sources["obj"] = MagiConfig(a=1, b=MagiConfig(c=2))
    path = tmp_path / "out.py"
    config.write(str(path))
    text = path.read_text()
    assert "<unwritable>" not in text
    assert read_back(path) == MagiConfig(obj=MagiConfig(a=1, b=MagiConfig(c=2)), x=1)


def test_write_imported_comments(tmp_path):
    config = MagiConfig(a=1, sub=MagiConfig(b=2))
    config._imported.extend([("first.py", "config"), (None, "config"), ("second.py", "cfg")])
    config.sub._imported.append(("sub.py", "config"))
    path = tmp_path / "out.py"
    config.write(str(path))
    lines = path.read_text().split("\n")
    assert lines[2:6] == [
        "# imported from: first.py (obj: config)",
        "# imported from: second.py (obj: cfg)",
        "config = MagiConfig()",
        "config.a = 1",
    ]
    assert lines[6:8] == ["# imported from: sub.py (obj: config)", "config.sub = MagiConfig()"]
    assert read_back(path) == config


class LocalClass:
    pass


def test_write_class_values(tmp_path):
    from collections import OrderedDict as OD
    module_path = tmp_path / "classes.py"
    module_path.write_text("class FromFile:\n    pass\n")
    FromFile = magiconfig.import_config(str(module_path), "FromFile")
    config = MagiConfig(a=OD, b=FromFile, c=int, d=LocalClass)
    path = tmp_path / "out.py"
    config.write(str(path))
    text = path.read_text()
    assert "from collections import OrderedDict" in text
    assert f"FromFile = import_config({str(module_path)!r}, 'FromFile')" in text
    assert text.index("from magiconfig import import_config") < text.index("FromFile = import_config")
    result = read_back(path)
    assert result.a is OD and result.b is FromFile and result.c is int and result.d is LocalClass


def test_write_main_class():
    # classes from __main__ are written by name
    cls = type("MainClass", (), {"__module__": "__main__"})
    assert magiconfig._class_expr(cls) == (set(), "'MainClass'")


def test_import_config_errors(tmp_path):
    with pytest.raises(MagiConfigError, match="not found"):
        magiconfig.import_config(str(tmp_path / "missing.py"), "config")
    path = tmp_path / "cfg.py"
    path.write_text("from magiconfig import MagiConfig\nconfig = MagiConfig(a=1)\n")
    with pytest.raises(MagiConfigError, match="Object other not found"):
        magiconfig.import_config(str(path), "other")
    module = magiconfig.import_config(str(path))
    assert module.config == MagiConfig(a=1)
    assert magiconfig.import_config(str(path), ["config", "config.a"]) == [MagiConfig(a=1), 1]
