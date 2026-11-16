"""Config printer: python -m magiconfig / magiconfig.main()."""
import os
import subprocess
import sys

import magiconfig
from magiconfig import MagiConfig
from conftest import EXAMPLES_DIR

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG4 = os.path.join(EXAMPLES_DIR, "config4.py")


def run_module(*args):
    result = subprocess.run(
        [sys.executable, "-m", "magiconfig", *args], capture_output=True, text=True,
        env=dict(os.environ, PYTHONPATH=REPO),
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_print_all(capsys):
    magiconfig.main([CONFIG4])
    output = capsys.readouterr().out
    assert run_module(CONFIG4) == output
    assert output.startswith("from magiconfig import MagiConfig\n\ncommon = MagiConfig()\ncommon.bar = 3.0\ncommon.foo = 'foo'\n\nconfig = MagiConfig()\n")
    # the loop variable is an alias of config.c
    assert output.endswith("config.c.input = 'c'\n\ncfg = config.c\n")


def test_print_obj(capsys):
    magiconfig.main([CONFIG4, "-o", "config.a", "common"])
    output = capsys.readouterr().out
    assert output == "\n".join([
        "from magiconfig import MagiConfig",
        "",
        "config = MagiConfig()",
        "config.a = MagiConfig()",
        "config.a.bar = 3.0",
        "config.a.foo = 'foo'",
        "config.a.input = 'a'",
        "",
        "common = MagiConfig()",
        "common.bar = 3.0",
        "common.foo = 'foo'",
    ]) + "\n"
    assert run_module(CONFIG4, "-o", "config.a", "common") == output


def test_write_reimport(tmp_path):
    out = tmp_path / "out.py"
    magiconfig.main([CONFIG4, "--write", str(out)])
    original = magiconfig.import_config(CONFIG4)
    written = magiconfig.import_config(str(out))
    for name in ("common", "config", "cfg"):
        assert getattr(written, name) == getattr(original, name)
    assert written.cfg is written.config.c
    assert isinstance(written.config, MagiConfig)


def test_imported_configs(tmp_path, capsys):
    base = tmp_path / "base.py"
    base.write_text("from magiconfig import MagiConfig\nbase = MagiConfig(x=1)\n_private = MagiConfig(y=2)\n")
    child = tmp_path / "child.py"
    child.write_text(f"from magiconfig import MagiConfig, import_config\nbase = import_config({str(base)!r}, 'base')\nchild = MagiConfig(z=[i for i in range(3)])\nnot_a_config = 5\n")
    magiconfig.main([str(child)])
    assert capsys.readouterr().out == "from magiconfig import MagiConfig\n\nbase = MagiConfig()\nbase.x = 1\n\nchild = MagiConfig()\nchild.z = [0, 1, 2]\n"
