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
    if parser is None: parser = magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(),prog="PROG")
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

def test_conflict_arg():
    parser = make_parser()
    try:
        parser.add_argument("-C", dest="C", type=str, default="conflict", help="conflicting arg")
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
    except magiconfig.MagiConfigError:
        return True
    else:
        return False

def test_config_strict_arg():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        strict = False,
        strict_args = ["--strict"],
    )))
    try:
        args = parser.parse_args(args=["-C","tests/test_config3.py","--strict"])
    except magiconfig.MagiConfigError:
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
    parser.add_config_only(
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

def test_dot_dests(namespace=None):
    parser = magiconfig.ArgumentParser(
        config_options = magiconfig.MagiConfigOptions(
            strict = True
        )
    )
    parser.add_argument("-f","--foo", dest="one.foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b","--bar", dest="two.bar", type=float, required=True, help="bar arg")
    args = parser.parse_args(args=["-C","tests/test_config_sub.py"],namespace=namespace)
    expected = magiconfig.MagiConfig()
    expected.one = magiconfig.MagiConfig(foo = '2')
    expected.two = magiconfig.MagiConfig(bar = 2.0)
    return args==expected

def test_namespace_convert():
    return test_dot_dests(namespace=argparse.Namespace())

def test_obj_arg():
    parser = make_parser(magiconfig.ArgumentParser(config_options = magiconfig.MagiConfigOptions(
        obj = "config.one",
        obj_args = ["-O","--obj"]
    )))
    args = parser.parse_args(args=["-C","tests/test_config_sub.py","-O","config.two"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = "lorem",
        ipsum = False,
    )
    return args==expected

def test_obj_arg_nodefault():
    parser = make_parser(magiconfig.ArgumentParser(config_options = magiconfig.MagiConfigOptions(
        obj = None,
        obj_args = ["-O","--obj"]
    )))
    try:
        args = parser.parse_args(args=["-C","tests/test_config_sub.py"])
    except argparse.ArgumentError:
        return True
    else:
        return False

def test_change_config_arg():
    parser = make_parser()
    parser.set_config_options(args = ["-c"])
    args = parser.parse_args(args=["-c","tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

def test_remove_config_arg():
    parser = make_parser()
    parser.set_config_options(args = None)
    try:
        args = parser.parse_args(args=["-C","tests/test_config.py"])
    except argparse.ArgumentError:
        return True
    else:
        return False

def test_config_args_pos():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        args=["poscon"],
    )))
    args = parser.parse_args(args=["tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

def test_change_config_arg_pos():
    parser = make_parser()
    parser.set_config_options(args = ["poscon"])
    args = parser.parse_args(args=["tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

def test_config_usage():
    parser = make_parser()
    expected_usage = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n"
    actual_usage = parser.format_usage()
    return actual_usage==expected_usage

def test_config_help():
    parser = make_parser()
    expected_help = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n\noptional arguments:\n  -h, --help            show this help message and exit\n  -C CONFIG, --config CONFIG\n                        name of config file to import (w/ object: config)\n  -f FOO, --foo FOO     foo arg\n  -b BAR, --bar BAR     bar arg\n  -i, --ipsum           ipsum arg\n"
    return parser.format_help()==expected_help

def test_change_config_arg_pos_usage():
    parser = make_parser()
    parser.set_config_options(args = ["poscon"])
    expected_usage = "usage: PROG [-h] [-f FOO] -b BAR [-i] poscon\n"
    try:
        actual_usage = parser.format_usage()
        return actual_usage==expected_usage
    except:
        return false

def test_config_parse_twice():
    parser = make_parser()
    args = parser.parse_args(args=["-C","tests/test_config.py"])
    args = parser.parse_args(args=["-C","tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

def test_config_usage_twice():
    parser = make_parser()
    expected_usage = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n"
    actual_usage = parser.format_usage()
    args = parser.parse_args(args=["-C","tests/test_config.py"])
    args = parser.parse_args(args=["-C","tests/test_config.py"])
    actual_usage2 = parser.format_usage()
    return actual_usage==expected_usage and actual_usage2==expected_usage

def test_remove_arg():
    parser = make_parser()
    parser.remove_argument('-b',keep=True)
    expected_usage = "usage: PROG [-h] [-C CONFIG] [-f FOO] --bar BAR [-i]\n"
    actual_usage = parser.format_usage()
    return actual_usage==expected_usage

def test_remove_action():
    parser = make_parser()
    parser.remove_argument('-b')
    expected_help = "usage: PROG [-h] [-C CONFIG] [-f FOO] [-i]\n\noptional arguments:\n  -h, --help            show this help message and exit\n  -C CONFIG, --config CONFIG\n                        name of config file to import (w/ object: config)\n  -f FOO, --foo FOO     foo arg\n  -i, --ipsum           ipsum arg\n"
    actual_help = parser.format_help()
    return actual_help==expected_help

def test_remove_unknown_arg():
    parser = make_parser()
    try:
        parser.remove_argument('-x')
    except:
        return True
    else:
        return False

def test_config_only_required():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        strict = True
    )))
    parser.add_config_only(
        extra=None,
    )
    try:
        args = parser.parse_args(args=["-C","tests/test_config.py"])
    except:
        return True
    else:
        return False

def test_config_only_remove():
    parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
        strict = True
    )))
    parser.add_config_only(
        "extra"
    )
    parser.remove_config_only(
        "extra"
    )
    try:
        args = parser.parse_args(args=["-C","tests/test_config3.py"])
    except:
        return True
    else:
        return False

def test_config_only_help():
    parser = make_parser(magiconfig.ArgumentParser(
        config_options=magiconfig.MagiConfigOptions(
            strict = True
        ),
        prog="PROG",
        formatter_class=magiconfig.ArgumentDefaultsHelpFormatter,
    ))
    parser.add_config_only(
        "arg1",
        arg2=None,
        arg3="test",
    )
    expected_help = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n\noptional arguments:\n  -h, --help            show this help message and exit\n  -C CONFIG, --config CONFIG\n                        name of config file to import (w/ object: config)\n                        (default: None)\n  -f FOO, --foo FOO     foo arg (default: lorem)\n  -b BAR, --bar BAR     bar arg (default: None)\n  -i, --ipsum           ipsum arg (default: False)\n\nconfig-only arguments:\n  arg1\n  arg2                  (required)\n  arg3                  (default: test)\n"
    actual_help = parser.format_help()
    return expected_help==actual_help

def test_config_only_already_used():
    parser = make_parser()
    try:
        parser.add_config_only("bar")
    except:
        return True
    else:
        return False

def test_dest_already_config_only():
    parser = make_parser()
    parser.add_config_only("arg1")
    try:
        parser.add_argument("-a","--arg", dest="arg1", type=str, default="", help="arg1")
    except:
        return True
    else:
        return False

def test_set_config_from_none():
    parser = make_parser(magiconfig.ArgumentParser())
    try:
        parser.set_config_options(args = ["-c"])
    except:
        return False
    else:
        return True

def test_copy_config_options():
    parser = make_parser()
    options2 = magiconfig.MagiConfigOptions(args = ["-c"])
    parser.copy_config_options(options2)
    args = parser.parse_args(args=["-c","tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

def test_remove_action_then_config_only():
    parser = make_parser()
    parser.remove_argument('-b')
    try:
        parser.add_config_only("bar")
    except:
        return False
    else:
        return True

def test_default_config_only():
    parser = make_parser()
    parser.remove_argument("-i")
    parser.add_config_only("ipsum")
    parser.set_defaults(ipsum = True)
    args = parser.parse_args(args=["-C","tests/test_config.py"])
    expected = magiconfig.MagiConfig(
        bar = 2.0,
        foo = '2',
        ipsum = False,
    )
    return args==expected

if __name__=="__main__":
    tests = OrderedDict([
        ("test_dropin",test_dropin),
        ("test_config_args",test_config_args),
        ("test_config_obj",test_config_obj),
        ("test_config_required",test_config_required),
        ("test_conflict_arg",test_conflict_arg),
        ("test_config_strict",test_config_strict),
        ("test_config_strict_arg",test_config_strict_arg),
        ("test_required_arg",test_required_arg),
        ("test_override",test_override),
        ("test_inconsistent_type",test_inconsistent_type),
        ("test_subparsers",test_subparsers),
        ("test_config_join",test_config_join),
        ("test_extra_dests",test_extra_dests),
        ("test_dot_dests",test_dot_dests),
        ("test_namespace_convert",test_namespace_convert),
        ("test_obj_arg",test_obj_arg),
        ("test_obj_arg_nodefault",test_obj_arg_nodefault),
        ("test_change_config_arg",test_change_config_arg),
        ("test_remove_config_arg",test_remove_config_arg),
        ("test_config_args_pos",test_config_args_pos),
        ("test_change_config_arg_pos",test_change_config_arg_pos),
        ("test_config_usage",test_config_usage),
        ("test_config_help",test_config_help),
        ("test_change_config_arg_pos_usage",test_change_config_arg_pos_usage),
        ("test_config_parse_twice",test_config_parse_twice),
        ("test_config_usage_twice",test_config_usage_twice),
        ("test_remove_arg",test_remove_arg),
        ("test_remove_action",test_remove_action),
        ("test_config_only_required",test_config_only_required),
        ("test_config_only_remove",test_config_only_remove),
        ("test_config_only_help",test_config_only_help),
        ("test_config_only_already_used",test_config_only_already_used),
        ("test_dest_already_config_only",test_dest_already_config_only),
        ("test_set_config_from_none",test_set_config_from_none),
        ("test_copy_config_options",test_copy_config_options),
        ("test_remove_action_then_config_only",test_remove_action_then_config_only),
        ("test_default_config_only",test_default_config_only),
    ])
    successful = []
    failed = []
    for test_name,test in six.iteritems(tests):
        try:
            result = test()
            if result: successful.append(test_name)
            else: failed.append(test_name)
        except:
            failed.append(test_name)
    six.print_("Successful tests: "+', '.join(successful))
    six.print_("Failed tests: "+', '.join(failed))
    if len(failed)>0:
        sys.exit(1)
