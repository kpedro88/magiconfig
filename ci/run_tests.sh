#!/bin/sh
# Run the full test suite: generate the upstream argparse tests for the current Python version, then run pytest.
# Extra arguments are passed to pytest.
set -e
cd "$(dirname "$0")/.."
python tests/setup_test_argparse.py
python -m pytest tests "$@"
