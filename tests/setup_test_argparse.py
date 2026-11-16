# Generate tests/test_argparse_magiconfig.py: the upstream CPython argparse tests for the running Python version,
# modified to use magiconfig.ArgumentParser in place of argparse.ArgumentParser.
import io
import os
import platform
import tokenize
import urllib.request

url = f"https://github.com/python/cpython/raw/v{platform.python_version()}/Lib/test/test_argparse.py"
source = urllib.request.urlopen(url).read().decode("utf-8")

# replace argparse.ArgumentParser only in code, not in string literals
# (some tests run scripts from strings in subprocesses, where magiconfig is not importable)
lines = source.splitlines(keepends=True)
tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
spans = [
    (first.start, last.end) for first, dot, last in zip(tokens, tokens[1:], tokens[2:])
    if (first.type, first.string, dot.string, last.type, last.string) == (tokenize.NAME, "argparse", ".", tokenize.NAME, "ArgumentParser")
]
for (row, start), (_, end) in reversed(spans):
    lines[row - 1] = lines[row - 1][:start] + "magiconfig.ArgumentParser" + lines[row - 1][end:]

outname = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_argparse_magiconfig.py")
with open(outname, "w") as outfile:
    outfile.write("import magiconfig\n")
    outfile.write("".join(lines))
