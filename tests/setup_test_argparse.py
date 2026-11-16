# Generate tests/test_argparse_magiconfig.py: the upstream CPython argparse tests for the running Python version,
# modified to use magiconfig.ArgumentParser in place of argparse.ArgumentParser.
import os
import platform
import urllib.request

url = f"https://github.com/python/cpython/raw/v{platform.python_version()}/Lib/test/test_argparse.py"
source = urllib.request.urlopen(url).read().decode("utf-8")
# (from ConfigArgParse)
source = source.replace("argparse.ArgumentParser", "magiconfig.ArgumentParser")
outname = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_argparse_magiconfig.py")
with open(outname, "w") as outfile:
    outfile.write("import magiconfig\n")
    outfile.write(source)
