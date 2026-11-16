import argparse
import os
import sys
import types

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_DIR = os.path.join(TESTS_DIR, "configs")
EXAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "examples")


def config_path(name):
    """Path to a fixture config file in tests/configs."""
    return os.path.join(CONFIGS_DIR, name)


def error_raising(parser):
    """Make parser.error() raise ArgumentError instead of exiting (from ConfigArgParse)."""
    def error_method(self, message):
        raise argparse.ArgumentError(None, message)
    parser.error = types.MethodType(error_method, parser)
    return parser


def help_heading():
    """Heading of the default optional-arguments section, which changed in Python 3.10."""
    return "options:" if sys.version_info >= (3, 10) else "optional arguments:"


@pytest.fixture(autouse=True)
def fixed_columns(monkeypatch):
    """Help output wraps to the terminal width, so fix it for reproducible help strings."""
    monkeypatch.setenv("COLUMNS", "80")
    # 3.14+ colorizes help depending on the environment
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("FORCE_COLOR", raising=False)


# The upstream argparse tests need the CPython "test" package, which some interpreter builds (e.g. uv-managed ones) omit.
# Skip them visibly in that case, unless MAGICONFIG_REQUIRE_ARGPARSE_TESTS=1 (as in CI), which turns it into an error.
collect_ignore = []
_argparse_tests_skipped = False
try:
    import test.support  # noqa: F401
except ImportError:
    if os.environ.get("MAGICONFIG_REQUIRE_ARGPARSE_TESTS") == "1":
        raise RuntimeError("CPython test package unavailable, but MAGICONFIG_REQUIRE_ARGPARSE_TESTS=1")
    collect_ignore.append("test_argparse_magiconfig.py")
    _argparse_tests_skipped = True


def pytest_report_header(config):
    if _argparse_tests_skipped:
        return "upstream argparse tests skipped: CPython test package unavailable"


def make_config(path, obj="config", **attrs):
    """Write a config file defining MagiConfig(**attrs) as `obj`; returns the path as a string."""
    from magiconfig import MagiConfig
    MagiConfig(**attrs).write(str(path), obj)
    return str(path)
