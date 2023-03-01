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

class MagiConfigTest(object):
    def test(self):
        pass

class test_dropin(MagiConfigTest):
    def test(self):
        args = ["-b","2"]
        new_parser = make_parser()
        new_args = new_parser.parse_args(args=args)
        old_parser = make_parser(parser=argparse.ArgumentParser())
        old_args = old_parser.parse_args(args=args)
        return new_args==old_args

class test_config_args(MagiConfigTest):
    def test(self):
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

class test_config_obj(MagiConfigTest):
    def test(self):
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

class test_config_required(MagiConfigTest):
    def test(self):
        parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
            required = True
        )))
        try:
            args = parser.parse_args(args=["-b","2"])
        except argparse.ArgumentError:
            return True
        else:
            return False

class test_conflict_arg(MagiConfigTest):
    def test(self):
        parser = make_parser()
        try:
            parser.add_argument("-C", dest="C", type=str, default="conflict", help="conflicting arg")
        except argparse.ArgumentError:
            return True
        else:
            return False

class test_config_strict(MagiConfigTest):
    def test(self):
        parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
            strict = True
        )))
        try:
            args = parser.parse_args(args=["-C","tests/test_config3.py"])
        except magiconfig.MagiConfigError:
            return True
        else:
            return False

class test_config_strict_arg(MagiConfigTest):
    def test(self):
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

class test_required_arg(MagiConfigTest):
    def test(self):
        parser = make_parser()
        args = parser.parse_args(args=["-C","tests/test_config.py"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = '2',
            ipsum = False,
        )
        return args==expected

class test_override(MagiConfigTest):
    def test(self):
        parser = make_parser()
        args = parser.parse_args(args=["-C","tests/test_config.py","-f","blah"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = 'blah',
            ipsum = False,
        )
        return args==expected

class test_inconsistent_type(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.add_argument("-F","--foo-foo", dest="foo", type=float, default=1.0, help="foo arg 2")
        args = parser.parse_args(args=["-C","tests/test_config.py"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = 2,
            ipsum = False,
        )
        return args==expected

class test_subparsers(MagiConfigTest):
    def test(self):
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

class test_config_join(MagiConfigTest):
    def test(self):
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

class test_extra_dests(MagiConfigTest):
    def test(self):
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

class test_dot_dests(MagiConfigTest):
    def test(self,namespace=None):
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

class test_namespace_convert(MagiConfigTest):
    def test(self):
        return test_dot_dests().test(namespace=argparse.Namespace())

class test_obj_arg(MagiConfigTest):
    def test(self):
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

class test_obj_arg_nodefault(MagiConfigTest):
    def test(self):
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

class test_change_config_arg(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.set_config_options(args = ["-c"])
        args = parser.parse_args(args=["-c","tests/test_config.py"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = '2',
            ipsum = False,
        )
        return args==expected

class test_remove_config_arg(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.set_config_options(args = None)
        try:
            args = parser.parse_args(args=["-C","tests/test_config.py"])
        except argparse.ArgumentError:
            return True
        else:
            return False

class test_config_args_pos(MagiConfigTest):
    def test(self):
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

class test_change_config_arg_pos(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.set_config_options(args = ["poscon"])
        args = parser.parse_args(args=["tests/test_config.py"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = '2',
            ipsum = False,
        )
        return args==expected

class test_config_usage(MagiConfigTest):
    def test(self):
        parser = make_parser()
        expected_usage = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n"
        actual_usage = parser.format_usage()
        return actual_usage==expected_usage

class test_config_help(MagiConfigTest):
    def test(self):
        parser = make_parser()
        expected_help = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n\noptional arguments:\n  -h, --help            show this help message and exit\n  -C CONFIG, --config CONFIG\n                        name of config file to import (w/ object: config)\n  -f FOO, --foo FOO     foo arg\n  -b BAR, --bar BAR     bar arg\n  -i, --ipsum           ipsum arg\n"
        return parser.format_help()==expected_help

class test_change_config_arg_pos_usage(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.set_config_options(args = ["poscon"])
        expected_usage = "usage: PROG [-h] [-f FOO] -b BAR [-i] poscon\n"
        try:
            actual_usage = parser.format_usage()
            return actual_usage==expected_usage
        except:
            return false

class test_config_parse_twice(MagiConfigTest):
    def test(self):
        parser = make_parser()
        args = parser.parse_args(args=["-C","tests/test_config.py"])
        args = parser.parse_args(args=["-C","tests/test_config.py"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = '2',
            ipsum = False,
        )
        return args==expected

class test_config_usage_twice(MagiConfigTest):
    def test(self):
        parser = make_parser()
        expected_usage = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n"
        actual_usage = parser.format_usage()
        args = parser.parse_args(args=["-C","tests/test_config.py"])
        args = parser.parse_args(args=["-C","tests/test_config.py"])
        actual_usage2 = parser.format_usage()
        return actual_usage==expected_usage and actual_usage2==expected_usage

class test_remove_arg(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.remove_argument('-b',keep=True)
        expected_usage = "usage: PROG [-h] [-C CONFIG] [-f FOO] --bar BAR [-i]\n"
        actual_usage = parser.format_usage()
        return actual_usage==expected_usage

class test_remove_action(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.remove_argument('-b')
        expected_help = "usage: PROG [-h] [-C CONFIG] [-f FOO] [-i]\n\noptional arguments:\n  -h, --help            show this help message and exit\n  -C CONFIG, --config CONFIG\n                        name of config file to import (w/ object: config)\n  -f FOO, --foo FOO     foo arg\n  -i, --ipsum           ipsum arg\n"
        actual_help = parser.format_help()
        return actual_help==expected_help

class test_remove_unknown_arg(MagiConfigTest):
    def test(self):
        parser = make_parser()
        try:
            parser.remove_argument('-x')
        except:
            return True
        else:
            return False

###############################
# Tests of deprecated interface
###############################

class test_config_only_deprecated_required(MagiConfigTest):
    def test(self):
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

class test_config_only_deprecated_remove(MagiConfigTest):
    def test(self):
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

class test_config_only_deprecated_deprecated_help(MagiConfigTest):
    def test(self):
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

class test_config_only_deprecated_already_used(MagiConfigTest):
    def test(self):
        parser = make_parser()
        try:
            parser.add_config_only("bar")
        except:
            return True
        else:
            return False

class test_dest_already_config_only_deprecated(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.add_config_only("arg1")
        try:
            parser.add_argument("-a","--arg", dest="arg1", type=str, default="", help="arg1")
        except:
            return True
        else:
            return False

class test_remove_action_then_config_only_deprecated(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.remove_argument('-b')
        try:
            parser.add_config_only("bar")
        except:
            return False
        else:
            return True

class test_default_config_only_deprecated(MagiConfigTest):
    def test(self):
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

class test_config_only_deprecated_change(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.add_config_only(*["extra"])
        try:
            parser.add_config_only(**{"extra":None})
        except:
            return False
        else:
            return True

###############################
# Corresponding tests of new interface
###############################

class test_config_only_required(MagiConfigTest):
    def test(self):
        parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
            strict = True
        )))
        parser.add_config_argument("extra",required=True)
        try:
            args = parser.parse_args(args=["-C","tests/test_config.py"])
        except:
            return True
        else:
            return False

class test_config_only_remove(MagiConfigTest):
    def test(self):
        parser = make_parser(magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions(
            strict = True
        )))
        parser.add_config_argument("extra")
        parser.remove_config_argument("extra")
        try:
            args = parser.parse_args(args=["-C","tests/test_config3.py"])
        except:
            return True
        else:
            return False

class test_config_only_help(MagiConfigTest):
    def test(self):
        parser = make_parser(magiconfig.ArgumentParser(
            config_options=magiconfig.MagiConfigOptions(
                strict = True
            ),
            prog="PROG",
            formatter_class=magiconfig.ArgumentDefaultsHelpFormatter,
        ))
        parser.add_config_argument("arg1")
        parser.add_config_argument("arg2",required=True)
        parser.add_config_argument("arg3",default="test")
        expected_help = "usage: PROG [-h] [-C CONFIG] [-f FOO] -b BAR [-i]\n\noptional arguments:\n  -h, --help            show this help message and exit\n  -C CONFIG, --config CONFIG\n                        name of config file to import (w/ object: config)\n                        (default: None)\n  -f FOO, --foo FOO     foo arg (default: lorem)\n  -b BAR, --bar BAR     bar arg (default: None)\n  -i, --ipsum           ipsum arg (default: False)\n\nconfig-only arguments:\n  arg1\n  arg2                  (required)\n  arg3                  (default: test)\n"
        actual_help = parser.format_help()
        return expected_help==actual_help

class test_config_only_already_used(MagiConfigTest):
    def test(self):
        parser = make_parser()
        try:
            parser.add_config_argument("bar")
        except:
            return True
        else:
            return False

class test_dest_already_config_only(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.add_config_argument("arg1")
        try:
            parser.add_argument("-a","--arg", dest="arg1", type=str, default="", help="arg1")
        except:
            return True
        else:
            return False

class test_remove_action_then_config_only(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.remove_argument('-b')
        try:
            parser.add_config_argument("bar")
        except:
            return False
        else:
            return True

class test_default_config_only(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.remove_argument("-i")
        parser.add_config_argument("ipsum")
        parser.set_defaults(ipsum = True)
        args = parser.parse_args(args=["-C","tests/test_config.py"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = '2',
            ipsum = False,
        )
        return args==expected

class test_set_config_from_none(MagiConfigTest):
    def test(self):
        parser = make_parser(magiconfig.ArgumentParser())
        try:
            parser.set_config_options(args = ["-c"])
        except:
            return False
        else:
            return True

class test_copy_config_options(MagiConfigTest):
    def test(self):
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

class test_remove_config_options(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.remove_config_options()
        try:
            args = parser.parse_args(args=["-C","tests/test_config.py"])
        except:
            return True
        else:
            return False

class test_nargs_config(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.add_argument("-n", "--names", dest="names", type=str, default=[], nargs='+', help = "names arg")
        args = parser.parse_args(args=["-C","tests/test_config4.py"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = '2',
            ipsum = False,
            names = ["Alice", "Bob"],
        )
        return args==expected

class test_nargs_config_none(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.add_argument("-n", "--names", dest="names", default=[], nargs='+', help = "names arg")
        args = parser.parse_args(args=["-C","tests/test_config4c.py"])
        expected = magiconfig.MagiConfig(
            bar = 2.0,
            foo = '2',
            ipsum = False,
            names = OrderedDict([("Alice",True)]),
        )
        return args==expected

class test_choices_config(MagiConfigTest):
    def test(self,config="tests/test_config4.py",should_fail=True,nargs='+',choices=["Alice","Carol"]):
        parser = make_parser()
        parser.add_argument("-n", "--names", dest="names", type=str, default=[], nargs=nargs, choices=choices, help = "names arg")
        try:
            args = parser.parse_args(args=["-C",config])
        except:
            return should_fail
        else:
            return not should_fail

class test_choices_config_single_default(MagiConfigTest):
    def test(self):
        return test_choices_config().test(config="tests/test_config4b.py",should_fail=False)

class test_choices_config_single_arg_good(MagiConfigTest):
    def test(self):
        return test_choices_config().test(config="tests/test_config4b.py",nargs=None,should_fail=False)

class test_choices_config_single_arg_bad(MagiConfigTest):
    def test(self):
        return test_choices_config().test(config="tests/test_config4b.py",nargs=None,choices=["Bob","Carol"])

class test_config_write_read(MagiConfigTest):
    def test(self):
        parser1 = make_parser()
        args1 = parser1.parse_args(args=["-b","2"])
        parser1.write_config(args1, "config_tmp.py")
        parser2 = make_parser()
        args2 = parser2.parse_args(args=["-C","config_tmp.py"])
        return args1==args2

class test_config_write_read_OrderedDict(MagiConfigTest):
    def test(self):
        parser = magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions())
        parser.add_argument("-d","--dict", type=OrderedDict, default=OrderedDict(), help="dict arg")
        config_in = magiconfig.MagiConfig(
            dict = OrderedDict([(1,2)]),
        )
        parser.write_config(config_in, "config_tmp2.py")
        try:
            args = parser.parse_args(args=["-C","config_tmp2.py"])
            return config_in==args
        except:
            return False

class test_config_write_read_OrderedDict_nested(MagiConfigTest):
    def test(self):
        parser = magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions())
        parser.add_argument("-d","--dict", dest="subconfig.dict", type=OrderedDict, default=OrderedDict(), help="dict arg")
        config_in = magiconfig.MagiConfig(
            subconfig = magiconfig.MagiConfig(
                dict = OrderedDict([(1,2)]),
            )
        )
        parser.write_config(config_in, "config_tmp3.py")
        try:
            args = parser.parse_args(args=["-C","config_tmp3.py"])
            return config_in==args
        except:
            return False

class test_config_write_read_OrderedDict_coll(MagiConfigTest):
    def test(self):
        parser = magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions())
        parser.add_argument("-d","--dicts", dest="subconfig.dicts", default=[], help="dict arg")
        config_in = magiconfig.MagiConfig(
            subconfig = magiconfig.MagiConfig(
                dicts = [OrderedDict([(1,2)]),OrderedDict([(3,4)])],
            )
        )
        parser.write_config(config_in, "config_tmp4.py")
        try:
            args = parser.parse_args(args=["-C","config_tmp4.py"])
            return config_in==args
        except:
            return False

# todo: make this test pass
'''
class test_config_write_read_selfref(MagiConfigTest):
    def test(self):
        parser = magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions())
        parser.add_argument("-d","--dict", default={}, help="dict arg")
        config_in = magiconfig.MagiConfig(
            dict = {}
        )
        config_in.dict[1] = config_in.dict
        parser.write_config(config_in, "config_tmp5.py")
        try:
            args = parser.parse_args(args=["-C","config_tmp5.py"])
            return config_in==args
        except:
            return False
'''

class test_config_write_read_OrderedDict_custom(MagiConfigTest):
    def test(self):
        def reprOD(obj):
            import json
            lines = ["OrderedDict(["]
            for key,val in six.iteritems(obj):
                lines.append('    ({}, {}),'.format(repr(key), json.dumps(val, sort_keys=True)))
            lines.append("])")
            return '\n'.join(lines)
        class_reprs = {OrderedDict: reprOD}
        parser = magiconfig.ArgumentParser(config_options=magiconfig.MagiConfigOptions())
        parser.add_argument("-d","--dict", type=OrderedDict, default=OrderedDict(), help="dict arg")
        config_in = magiconfig.MagiConfig(
            dict = OrderedDict([(1,2)]),
        )
        parser.write_config(config_in, "config_tmp6.py", class_reprs=class_reprs)
        expected_config = 'from magiconfig import MagiConfig\nfrom collections import OrderedDict\n\nconfig = MagiConfig()\nconfig.dict = OrderedDict([\n    (1, 2),\n])'
        with open("config_tmp6.py",'r') as infile:
            infile_read = infile.read()
            return expected_config == infile_read

class test_config_write_strict(MagiConfigTest):
    def test(self):
        config = magiconfig.MagiConfig(
            d = {},
        )
        config.d[1] = config.d
        # repr for a self-referential object includes "...", will not eval to original
        try:
            config.write("config_tmp7.py", "config", strict=True)
        except:
            return True
        else:
            return False

class test_config_default_type(MagiConfigTest):
    def test(self):
        parser = make_parser()
        parser.add_argument("--extra", dest="extra", type=str, default=None, help = "extra arg")
        args = parser.parse_args(args=["-C","tests/test_config5.py"])
        return args.extra==None

if __name__=="__main__":
    tests = OrderedDict([(subcl.__name__, subcl) for subcl in MagiConfigTest.__subclasses__()])
    successful = []
    failed = []
    incomplete = []
    for test_name,test_class in six.iteritems(tests):
        try:
            result = test_class().test()
            if result: successful.append(test_name)
            else: failed.append(test_name)
        except:
            incomplete.append(test_name)
    six.print_("Successful tests: "+', '.join(successful))
    six.print_("Failed tests: "+', '.join(failed))
    six.print_("Incomplete tests: "+', '.join(incomplete))
    if len(failed)>0 or len(incomplete)>0:
        sys.exit(1)
