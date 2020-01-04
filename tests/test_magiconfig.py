import magiconfig
import argparse
import six
import sys
import types
from collections import OrderedDict

# swap out arg_parser's error(..) method so that instead of calling sys.exit(..) it just raises an error.
# (from ConfigArgParse)
def replace_error_method(arg_parser):
    def error_method(self, message):
        raise argparse.ArgumentError(None, message)

    def exit_method(self, status, message):
        self._exit_method_called = True

    arg_parser._exit_method_called = False
    arg_parser.error = types.MethodType(error_method, arg_parser)
    arg_parser.exit = types.MethodType(exit_method, arg_parser)

    return arg_parser

def make_parser(parser=None):
    if parser is None: parser = magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions())
    replace_error_method(parser)
    parser.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")
    parser.add_argument("-i","--ipsum", dest="ipsum", action="store_true", help="ipsum arg")
    return parser

def test_dropin():
    args = ["-b","2"]
    new_parser = make_parser()
    new_args = new_parser.parse_args(args=args)
    old_parser = make_parser(parser=argparse.ArgumentParser())
    old_args = old_parser.parse_args(args=args)
    return new_args==old_args

def test_config_args():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        args=["-c"],
    )))
    args = parser.parse_args(args=["-c","tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

def test_config_obj():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        obj="cfg",
    )))
    args = parser.parse_args(args=["-C","tests/test_config2.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

def test_config_required():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        required = True
    )))
    try:
        args = parser.parse_args(args=["-b","2"])
    except argparse.ArgumentError:
        return True
    else:
        return False

def test_config_strict():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        strict = True
    )))
    try:
        args = parser.parse_args(args=["-C","tests/test_config3.py"])
    except ValueError:
        return True
    else:
        return False

def test_required_arg():
    parser = make_parser()
    args = parser.parse_args(args=["-C","tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

def test_override():
    parser = make_parser()
    args = parser.parse_args(args=["-C","tests/test_config.py","-f","blah"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = 'blah',
        ipsum = False,
    )
    return args==expected

def test_inconsistent_type():
    parser = make_parser()
    parser.add_argument("-F","--foo-foo", dest="foo", type=float, default=1.0, help="foo arg 2")
    args = parser.parse_args(args=["-C","tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = 2,
        ipsum = False,
    )
    return args==expected

def test_subparsers():
    # parser does not need config_options if it will have subparsers
    parser = magiconfig.ArgumentParser()
    subparsers = parser.add_subparsers()
    parser_one = subparsers.add_parser("one",config_options=magiconfig.MagiConfigOptions(
        obj = "config.one"
    ))
    parser_one.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser_two = subparsers.add_parser("two",config_options=magiconfig.MagiConfigOptions(
        obj = "config.two"
    ))
    parser_two.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")
    args_one = parser.parse_args(args=["one","-C","tests/test_config_sub.py"])
    expected_one = magiconfig.MagiConfig(
        foo = '2'
    )
    args_two = parser.parse_args(args=["two","-C","tests/test_config_sub.py"])
    expected_two = magiconfig.MagiConfig(
        bar = 2.0
    )
    return args_one==expected_one and args_two==expected_two

def test_config_join():
    config_one = magiconfig.MagiConfig(
        foo = '2',
        bar = 2.0
    )
    config_two = magiconfig.MagiConfig(
        foo = '3'
    )
    config_three = magiconfig.MagiConfig(
        bar = 3.0,
        ipsum = True
    )
    config_one.join(config_two,prefer_other=True)
    config_one.join(config_three)
    expected_config = magiconfig.MagiConfig(
        foo = '3',
        bar = 2.0,
        ipsum = True
    )
    return config_one==expected_config

def test_extra_dests():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        strict = True
    )))
    parser.set_defaults(
        "extra",
    )
    args = parser.parse_args(args=["-C","tests/test_config3.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
        extra = "blah",
    )
    return args==expected

if __name__=="__main__":
    tests = OrderedDict([
        ("test_dropin",test_dropin),
        ("test_config_args",test_config_args),
        ("test_config_obj",test_config_obj),
        ("test_config_required",test_config_required),
        ("test_config_strict",test_config_strict),
        ("test_required_arg",test_required_arg),
        ("test_override",test_override),
        ("test_inconsistent_type",test_inconsistent_type),
        ("test_subparsers",test_subparsers),
        ("test_config_join",test_config_join),
        ("test_extra_dests",test_extra_dests),
    ])
    successful = []
    failed = []
    for test_name,test in six.iteritems(tests):
        result = test()
        if result: successful.append(test_name)
        else: failed.append(test_name)
    six.print_("Successful tests: "+', '.join(successful))
    six.print_("Failed tests: "+', '.join(failed))
    if len(failed)>0:
        sys.exit(1)
