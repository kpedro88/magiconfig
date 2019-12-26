from magiconfig import ArgumentParser
import six

def make_parser():
    parser = ArgumentParser()
    parser.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")
    return parser

def test1():
    parser = make_parser()
    args = parser.parse_args(args=["-C","test_config.py","-f","blah"])
    six.print_(args)

def test_orig():
    try:
        import test.test_argparse
    except ImportError:
        six.print_("argparse tests not available")
    else:
        test_argparse_source_code = inspect.getsource(test.test_argparse)
        test_argparse_source_code = test_argparse_source_code.replace(
            'argparse.ArgumentParser', 'magiconfig.ArgumentParser')
        exec(test_argparse_source_code)

if __name__=="__main__":
    test1()
    #test_orig()