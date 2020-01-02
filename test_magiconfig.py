import magiconfig
import six

def make_parser():
    parser = magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions())
    parser.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")
    parser.add_argument("-i","--ipsum", dest="ipsum", required=True, action="store_true", help="ipsum arg")
    return parser

def test1():
    parser = make_parser()
    args = parser.parse_args(args=["-C","test_config.py","-f","blah"])
    six.print_(args)

if __name__=="__main__":
    test1()
