import argparse
import sys, os, imp, uuid
import six
import collections
import functools

# from https://stackoverflow.com/questions/31174295/getattr-and-setattr-on-nested-subobjects-chained-properties/31174427#31174427
def _rgetattr(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)
    return functools.reduce(_getattr, [obj] + attr.split('.'))

class MagiConfig(argparse.Namespace):
    def write(self, filename, config_obj):
        if len(config_obj)==0:
            raise ValueError("config_obj must be specified")
        # write namespace into file
        with open(filename,'w') as outfile:
            lines = []
            prepend = ""
            # create a magiconfig
            lines.extend(["from magiconfig import MagiConfig","",config_obj+" = MagiConfig()"])
            prepend = config_obj + "."
            lines.extend([prepend+str(attr)+" = "+repr(val) for attr,val in sorted(six.iteritems(vars(self)))])
            outfile.write('\n'.join(lines))

    # to merge with another config
    def join(self, other_config, prefer_other=False):
        for attr,val in six.iteritems(vars(other_config)):
            if prefer_other or not hasattr(self,attr):
                setattr(self,attr,val)

    def __setattr__(self, attr, val):
        pre, _, post = attr.rpartition('.')
        if len(pre)>0:
            if not hasattr(self,pre):
                object.__setattr__(self,pre,MagiConfig())
            object.__setattr__(_rgetattr(self,pre), post, val)
        else:
            object.__setattr__(self, post, val)

    def __getattr__(self, attr):
        def _getattr(obj, attr):
            return obj.__getattribute__(attr)
        return functools.reduce(_getattr, [self] + attr.split('.'))

class MagiConfigOptions(object):
    # arguments:
    # args = arguments used to indicate config file
    # help = custom help message for config arg
    # required = require config_arg to be provided when parsing
    # default = default value for config filename
    # obj = string identifying magiconfig object in module imported from config file
    # obj_args = optional argument to specify obj on command line
    # obj_help = custom help message for obj arg
    # strict = reject imported config if it has unknown keys
    # strict_args = optional argument to specify strictness on command line
    # strict_help = custom help message for strict arg
    def __init__(self, args=["-C","--config"], help=None, required=False, default="", obj="config", obj_args=None, obj_help=None, strict=False, strict_args=None, strict_help=None):
        if (obj is None or len(obj)==0) and obj_args is None:
            raise ValueError("obj or obj_args must be specified")

        self.args = args
        self.help = help
        self.required = required
        self.default = default
        self.obj = obj
        self.obj_args = obj_args
        self.obj_help = obj_help
        self.strict = strict
        self.strict_args = strict_args
        self.strict_help = strict_help

class ArgumentParser(argparse.ArgumentParser):
    # additional argument:
    # config_options: default is None, otherwise expects instance of MagiConfigOptions
    def __init__(self, *args, **kwargs):
        self.config_options = kwargs.pop("config_options", None)
        argparse.ArgumentParser.__init__(self, *args, **kwargs)
        self._config_actions = None
        self._other_actions = []
        self._other_defaults = {}
        self._config_defaults = {}

        # initialize config args from options
        self._init_config()

    def _init_config(self):
        # reset relevant members
        if self._config_actions is not None: self._remove_config_args()
        self._dest = ""
        self._obj_dest = ""
        self._strict_dest = ""
        self._config_actions = None
        self._config_option_string_actions = {}

        # set up config arg(s) if any
        # dest is fixed because it is only used in internal namespace
        if self.config_options is not None and self.config_options.args is not None and len(self.config_options.args)>0:
            self._config_actions = []
            self._dest = "config"
            self._obj_dest = "obj"
            self._strict_dest = "strict"
            self._config_actions.append(self.add_argument(
                *self.config_options.args,
                dest=self._dest,
                type=str,
                help=self.config_options.help if self.config_options.help is not None else "name of config file to import (w/ object"+(": "+self.config_options.obj if self.config_options.obj_args is None else " from "+",".join(self.config_options.obj_args))+")",
                required=self.config_options.required,
                default=self.config_options.default if len(self.config_options.default)>0 else None
            ))
            if self.config_options.obj_args is not None:
                self._config_actions.append(self.add_argument(
                    *self.config_options.obj_args,
                    dest=self._obj_dest,
                    type=str,
                    help=self.config_options.obj_help if self.config_options.obj_help is not None else "name of object to import from config file",
                    required=self.config_options.obj is None,
                    default=self.config_options.obj
                ))
            if self.config_options.strict_args is not None:
                # strict arg switches from the default value
                self._config_actions.append(self.add_argument(
                    *self.config_options.strict_args,
                    dest=self._strict_dest,
                    action="store_true" if self.config_options.strict==False else "store_false",
                    help=self.config_options.strict_help if self.config_options.strict_help is not None else ("reject" if self.config_options.strict==False else "accept")+" imported config with unknown attributes",
                    default=self.config_options.strict
                ))
            for config_action in self._config_actions:
                for option_string in config_action.option_strings:
                    self._config_option_string_actions[option_string] = config_action

    parse_known_args_orig = argparse.ArgumentParser.parse_known_args

    def _remove_config_args(self):
        for config_action in self._config_actions:
            for option_string in config_action.option_strings:
                self._option_string_actions.pop(option_string)
            self._remove_action(config_action)

    def _restore_config_args(self):
        for config_action in self._config_actions:
            for option_string in config_action.option_strings:
                self._option_string_actions[option_string] = config_action
            self._actions.append(config_action)

    def parse_known_args(self, args=None, namespace=None):
        if args is None: args = sys.argv[1:]
        else: args = list(args)
    
        if namespace is None: namespace = MagiConfig()

        # fall back to default argparse behavior
        if self._config_actions is None:
            return self.parse_known_args_orig(args=args,namespace=namespace)

        # separate config actions from other actions
        self._remove_config_args()

        # reset known args to just config_args and parse
        self._other_actions, self._actions = self._actions, self._config_actions
        self._other_defaults, self._defaults = self._defaults, {}
        self._other_option_string_actions, self._option_string_actions = self._option_string_actions, self._config_option_string_actions
        tmpspace, remaining_args = self.parse_known_args_orig(args=args)

        # fall back to default argparse behavior
        # (config_required already checked above, when parsing for config_arg)
        if not hasattr(tmpspace,self._dest) or tmpspace.config is None:
            # restore known args and parse
            self._actions, self._other_actions = self._other_actions, []
            self._defaults, self._other_defaults = self._other_defaults, {}
            self._option_string_actions, self._other_option_string_actions = self._other_option_string_actions, {}
            return self.parse_known_args_orig(args=args,namespace=namespace)

        # get namespace as filled by config
        namespace = self.parse_config(
            tmpspace.config,
            getattr(tmpspace,self._obj_dest) if hasattr(tmpspace,self._obj_dest) else self.config_options.obj,
            getattr(tmpspace,self._strict_dest) if hasattr(tmpspace,self._strict_dest) else self.config_options.strict,
            namespace=namespace
        )

        # restore known args
        self._actions, self._other_actions = self._other_actions, []
        self._defaults, self._other_defaults = self._other_defaults, {}
        self._option_string_actions, self._other_option_string_actions = self._other_option_string_actions, {}

        # call parse_known_args_orig again (supplying namespace from above)
        tmpspace, remaining_args = self.parse_known_args_orig(args=remaining_args,namespace=namespace)

        # restore required actions
        for action in self._required:
            action.required = True
        # in case this runs again
        self._required = []
        # restore config actions
        self._restore_config_args()

        # finish
        return tmpspace, remaining_args

    def parse_config(self, config_name, config_obj, config_strict, namespace=None):
        # import config as module
        # (from configurati)
        module_id = str(uuid.uuid4())
        module = imp.load_source(module_id, os.path.abspath(config_name))
        config = _rgetattr(module,config_obj)

        # get dict of dest:action(s) from other_actions
        dests = collections.defaultdict(list)
        for action in self._other_actions:
            dests[action.dest].append(action)

        # handle values in sub-configs by restoring dots in keys
        def flatten_vars(config,pre=""):
            flat_vars = {}
            for attr,val in six.iteritems(vars(config)):
                if isinstance(val,MagiConfig):
                    flat_vars.update(flatten_vars(val,attr+"."))
                else:
                    flat_vars[pre+attr] = val
            return flat_vars

        # loop over vars(config) to populate namespace
        known_attrs = []
        unknown_attrs = []
        self._required = []
        flat_vars = flatten_vars(config)
        for attr,val in six.iteritems(flat_vars):
            if attr in dests or attr in self._config_defaults:
                known_attrs.append(attr)
                tmp = val
                # check type if uniquely provided
                if len(dests[attr])==1 or len(set([action.type for action in dests[attr]]))==1:
                    tmp = self._get_value(dests[attr][0],tmp)
                setattr(namespace,attr,tmp)
                # remove required attr from associated actions
                for action in dests[attr]:
                    if action.required:
                        action.required = False
                        self._required.append(action)
            else:
                unknown_attrs.append(attr)

        # check strict
        if config_strict and len(unknown_attrs)>0:
            raise ValueError("Imported config contained unknown attributes: "+','.join(unknown_attrs))

        return namespace

    # allow modifying options for config args
    def set_config_options(self, **kwargs):
        # modify config options
        for key,val in six.iteritems(kwargs):
            if hasattr(self.config_options,key): setattr(self.config_options,key,val)
            else: raise ValueError("Attempt to set invalid config option: "+key)

        # reinitialize
        self._init_config()

    # write namespace into file using config_obj
    def write_config(self, namespace, filename):
        namespace.write(filename,self.config_options.obj)

    # keep track of non-arg defaults
    set_defaults_orig = argparse.ArgumentParser.set_defaults

    def set_defaults(self, *args, **kwargs):
        self.set_defaults_orig(**kwargs)

        arg_dests = [action.dest for action in self._actions]
        self._config_defaults.update({key:val for key,val in six.iteritems(kwargs) if key not in arg_dests})
        self._config_defaults.update({key:None for key in args})

# updates to subparsers
argparse._SubParsersAction.add_parser_orig = argparse._SubParsersAction.add_parser
def add_parser_new(self, name, **kwargs):
    if six.PY2:
        # taken from python3 version
        aliases = kwargs.pop('aliases', ())

    parser = self.add_parser_orig(name,**kwargs)

    if six.PY2:
        # make parser available under aliases also
        for alias in aliases:
            self._name_parser_map[alias] = parser

    return parser
argparse._SubParsersAction.add_parser = add_parser_new

# add all public classes and constants from argparse namespace to this namespace to be interchangeable
# (from ConfigArgParse)
HelpFormatter = argparse.HelpFormatter
RawDescriptionHelpFormatter = argparse.RawDescriptionHelpFormatter
RawTextHelpFormatter = argparse.RawTextHelpFormatter
ArgumentDefaultsHelpFormatter = argparse.ArgumentDefaultsHelpFormatter
ArgumentError = argparse.ArgumentError
ArgumentTypeError = argparse.ArgumentTypeError
Action = argparse.Action
FileType = argparse.FileType
Namespace = argparse.Namespace
ONE_OR_MORE = argparse.ONE_OR_MORE
OPTIONAL = argparse.OPTIONAL
REMAINDER = argparse.REMAINDER
SUPPRESS = argparse.SUPPRESS
ZERO_OR_MORE = argparse.ZERO_OR_MORE
