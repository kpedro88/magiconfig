"""Run the example commands shown in README.md and compare their output with the README.

Commands are lines starting with "> python" inside fenced code blocks; the expected output is the following lines,
up to the next command or the end of the block. Commands run in README order, since some use files written by earlier ones.
Help output in the README is from Python 3.9, so it is only compared there.
"""
import os
import shlex
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def readme_commands():
    with open(os.path.join(REPO, "README.md")) as infile:
        lines = infile.read().split("\n")
    commands = []
    in_block = False
    expected = None
    for line in lines:
        if line.startswith("```"):
            in_block = not in_block
            expected = None
        elif in_block and line.startswith("> python "):
            expected = []
            commands.append((line[2:], expected))
        elif in_block and expected is not None:
            expected.append(line)
    return commands


def test_readme_examples():
    commands = readme_commands()
    assert len(commands) > 15
    env = dict(os.environ, PYTHONPATH=REPO, COLUMNS="80", NO_COLOR="1")
    for command, expected in commands:
        args = shlex.split(command)
        args[0] = sys.executable
        result = subprocess.run(args, cwd=REPO, capture_output=True, text=True, env=env)
        assert result.returncode == 0, (command, result.stderr)
        is_help = "-h" in args or "--help" in args
        if is_help and sys.version_info[:2] != (3, 9):
            continue
        assert result.stdout == "\n".join(expected) + "\n", command
