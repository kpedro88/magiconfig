import argparse
from collections import OrderedDict, defaultdict

import pytest

import magiconfig
from magiconfig import MagiConfig, DictAction
from conftest import error_raising


def test_command_line():
    parser = error_raising(magiconfig.ArgumentParser(prog="PROG"))
    parser.add_argument("--params", action=DictAction, default={}, value_type=int)
    args = parser.parse_args(["--params", "a=1", "b=2", "--params", "a=3"])
    assert args.params == {"a": 3, "b": 2}
    assert parser.parse_args([]).params == {}
    with pytest.raises(argparse.ArgumentError, match="expected KEY=VALUE"):
        parser.parse_args(["--params", "a"])
    with pytest.raises(argparse.ArgumentError, match="invalid entry"):
        parser.parse_args(["--params", "a=x"])
    assert "--params [KEY=VALUE ...]" in parser.format_help()


def test_types_and_separator():
    parser = error_raising(argparse.ArgumentParser())
    parser.add_argument("--od", action=DictAction, dict_type=OrderedDict, key_type=int, sep=":")
    args = parser.parse_args(["--od", "2:b", "1:a"])
    assert type(args.od) is OrderedDict and list(args.od.items()) == [(2, "b"), (1, "a")]
    parser.add_argument("--dd", action=DictAction, dict_type=lambda: defaultdict(list))
    assert type(parser.parse_args(["--dd", "x=1"]).dd) is defaultdict


def test_default_not_mutated():
    default = {"a": "0"}
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", action=DictAction, default=default)
    assert parser.parse_args(["--params", "b=1"]).params == {"a": "0", "b": "1"}
    assert default == {"a": "0"}


def test_from_config():
    parser = error_raising(magiconfig.ArgumentParser(basic=True))
    parser.add_argument("--params", action=DictAction, value_type=float, dict_type=OrderedDict)
    args = parser._config_parsers["config"].parse(["--params", "c=3"], MagiConfig(params={"a": 1, "b": "2"}), False)[0]
    assert args.params == OrderedDict([("a", 1.0), ("b", 2.0), ("c", 3.0)])
    assert type(args.params) is OrderedDict


class ParamAction(DictAction):
    """Tokens alternate between keys and values."""
    def parse_params(self, values):
        return zip(values[::2], values[1::2])


def test_subclass():
    parser = argparse.ArgumentParser()
    parser.add_argument("--p", action=ParamAction, value_type=int)
    assert parser.parse_args(["--p", "a", "1", "b", "2"]).p == {"a": 1, "b": 2}
