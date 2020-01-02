import platform
from six.moves import urllib
req = urllib.request.urlopen('https://github.com/python/cpython/raw/v'+platform.python_version()+'/Lib/test/test_argparse.py')
with open('tests/test_argparse.py','b+w') as modfile:
	modfile.write(req.read())
with open('tests/test_argparse.py','r') as infile, open('tests/test_argparse_magiconfig.py','w') as outfile:
    outfile.write("import magiconfig\n")
    for line in infile:
        # (from ConfigArgParse)
        outfile.write(line.replace('argparse.ArgumentParser', 'magiconfig.ArgumentParser'))
