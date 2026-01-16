"""An extension of argparse to configure Python with Python"""

__version__ = "3.0.0-alpha.0"

import argparse
import sys, os
from collections import defaultdict, OrderedDict
from collections.abc import Container, Mapping, Collection
import functools
import types
import warnings

ASK = '==ASK=='

# from numpy
class VisibleDeprecationWarning(UserWarning):
    pass

def deprecation(message):
    warnings.warn(message, VisibleDeprecationWarning, stacklevel=2)

# from https://stackoverflow.com/questions/31174295/getattr-and-setattr-on-nested-subobjects-chained-properties/31174427#31174427
def _rgetattr(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)
    return functools.reduce(_getattr, [obj] + attr.split('.'))

# from https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
# but more automated
def import_config(file_path, attrs):
    import importlib.util
    import importlib.machinery

    # uses md5 to be deterministic
    def unique_name(file_path):
        import hashlib
        import base64

        abs_path = os.path.abspath(file_path)
        # use base64 for conciseness
        path_hash = base64.b64encode(hashlib.md5(abs_path.encode('utf-8')).digest()).decode('utf-8')
        base_name = os.path.basename(file_path).replace('.', '_')
        module_name = f'{base_name}__{path_hash}'
        return module_name

    module_name = unique_name(file_path)
    if module_name in sys.modules:
        module = sys.modules[module_name]
    else:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    if isinstance(attrs,list):
        return [_rgetattr(module, attr) for attr in attrs]
    else:
        return _rgetattr(module, attrs)

# denotes MagiConfig-specific errors
class MagiConfigError(Exception):
    pass

class MagiConfig(argparse.Namespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._transients = [
            "_transients",
        ]

    def write(self, filename, config_obj, attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False):
        if len(config_obj)==0:
            raise MagiConfigError("config_obj must be specified")

        # defaults
        if attr_imports is None: attr_imports = {}
        if class_imports is None: class_imports = {}
        if attr_reprs is None: attr_reprs = {}
        if class_reprs is None: class_reprs = {}

        # get lines to write
        default_imports = ["from magiconfig import MagiConfig"]
        imports, lines = self._write(config_obj, attr_imports, class_imports, attr_reprs, class_reprs, strict)

        # write namespace into file
        with open(filename,'w') as outfile:
            outfile.write('\n'.join(default_imports+sorted(list(imports))+[""]+lines))

    def _write(self, config_obj, attr_imports, class_imports, attr_reprs, class_reprs, strict):
        imports = set()
        # create a magiconfig
        lines = [config_obj+" = MagiConfig()"]
        prepend = config_obj + "."
        for attr,val in sorted(vars(self).items()):
            if attr in self._transients:
                continue
            valclass = val.__class__
            # recurse for nested configs
            if valclass==self.__class__:
                imports_tmp, lines_tmp = val._write(prepend+attr, attr_imports, class_imports, attr_reprs, class_reprs, strict)
                imports.update(imports_tmp)
                lines.extend(lines_tmp)
            else:
                # precedence: attr-specific > class-specific > default
                imports.update(self._get_imports(attr, val, attr_imports, class_imports))
                repr_fn = attr_reprs.get(attr, class_reprs.get(valclass, repr))
                repr_val = repr_fn(val)
                # detect cases where repr() doesn't work as desired
                if strict:
                    try:
                        repr_worked = eval(repr_val)
                    # catch cases where eval(repr) completely fails
                    except:
                        repr_worked = False
                    if not repr_worked or repr_worked!=val:
                        error_lines = [
                            "Inconsistency between original value and repr for {}:".format(prepend+attr),
                            (val, repr_val)
                        ]
                        raise MagiConfigError('\n'.join(str(el) for el in error_lines))
                lines.append(prepend+str(attr)+" = "+repr_val)
        return imports, lines

    # recursively check imports (avoiding infinite recursion in self-referential case)
    def _get_imports(self, attr, val, attr_imports, class_imports, checked=None):
        valclass = val.__class__
        if checked is None: checked = set()
        imports = set()

        def default_import(val):
            valclass = val.__class__
            if valclass.__module__=='__builtin__' or valclass.__module__=='builtins':
                if valclass.__name__=='module':
                    return "import {}".format(val.__name__)
            else:
                return "from {} import {}".format(valclass.__module__,valclass.__name__)
            return None

        if id(val) not in checked:
            # precedence: attr-specific > class-specific > defaults
            attr_imports_actual = {} if attr is None else attr_imports
            import_fn = attr_imports_actual.get(attr, class_imports.get(valclass, default_import))
            imports_to_add = import_fn(val)
            if imports_to_add is not None:
                imports.add(imports_to_add)

            checked.add(id(val))

            # check collection entries
            coll = None
            if isinstance(val, Mapping):
                coll = val.items()
            elif isinstance(val, Collection):
                coll = val
            elif isinstance(val, Container):
                try:
                    coll = vars(val)
                except:
                    # todo: solution for this case?
                    pass
            if coll is not None:
                for subval in coll:
                    # will be applied to keys and values separately for dicts, i.e. attr-specific only use for MagiConfigs
                    imports.update(self._get_imports(None, subval, attr_imports, class_imports, checked))

        return imports

    # to merge with another config
    def join(self, other_config, prefer_other=False):
        for attr,val in vars(other_config).items():
            if prefer_other or not hasattr(self,attr):
                setattr(self,attr,val)
                # propagate transient property accordingly
                if attr in self._transients and not attr in other_config._transients:
                    self._transients = [t for t in self._transients if t!=attr]
                elif attr not in self._transients and attr in other_config._transients:
                    self._transients.append(attr)

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

class ConfigObject:
    _base_arguments = dict(
        obj = dict(type=str, default="config", disable=True, transient=True, help="name of object to import from config file"),
        strict = dict(default=False, action="store_true", disable=True, transient=True, help="reject imported config with unknown attributes"),
    )
    _arguments = {}
    _help = ""
    _principal = None

    # get combined arguments
    @staticmethod
    def arguments():
        return _base_arguments | _arguments

    # any keys in custom that are not in arguments will be ignored
    @staticmethod
    def add_arguments(cparser, config, custom=None):
        if not custom: custom = {}
        parsers = {}
        prefix = config + "." if cparser.prefix else ""

        def add_argument(parser, arg, kwargs):
            if arg in custom:
                if isinstance(custom[arg], bool):
                    # bool value used to enable or disable, without changing other parameters
                    kwargs.update(disable=not custom[arg])
                else:
                    kwargs.update(custom[arg])
            # maybe not necessary?
            kwargs["source"] = config
            parser.add_argument(f"--{prefix}{arg}", **kwargs)

        for arg, kwargs in _base_arguments.items():
            add_argument(cparser.base, arg, kwargs)

        for arg, kwargs in _arguments.items():
            add_argument(cparser.args, arg, kwargs)

        return parsers

    # standalone function to build from config or file
    @classmethod
    def build(cls, *, config=None, path=None, obj="config"):
        if config and path:
            raise RuntimeError("config and path are mutually exclusive")
        if path:
            config = import_config(path, obj)
        # todo: implement strict option?
        return _build_impl(cls, config)

    # can be overridden in case you want to do something completely different from **vars(config)
    @classmethod
    def _build_impl(cls, config):
        # in order to use ConfigObject as a proxy for an existing object
        builder = _principal if _principal else cls
        # todo: deal with repr in proxy case
        instance = builder(**vars(config))
        return instance

    def __init__(self, **kwargs):
        self._fields = []
        self._transients = []
        for key, val in kwargs.items():
            setattr(self, key, val)
            self._fields.append(key)
        # add default value at the end, in case MagiConfig used for construction provides some values
        # _transients itself always included in _transients by MagiConfig
        self._transients.extend([
            "_fields",
        ])

    def __repr__(self):
        return repr(MagiConfig(**{key:getattr(self,key) for key in self._fields}))

# internal representation of config argument and associated arguments
class MagiConfigObject(ConfigObject):
    _help = "name of config file to import"
    @classmethod
    def _build_impl(cls, config):
        return config

# patch base class to remove recursively through all groups (defined as standalone to be used on other objects)
# this is needed to get correct help messages if set_config_options is called to make changes after initialization
def _remove_action_all(self, action, throw=True):
    try:
        self._actions.remove(action)
        for option_string in action.option_strings:
            self._option_string_actions.pop(option_string)
        if hasattr(self,"_dests_actions"):
            self._dests_actions[action.dest].remove(action)
            if len(self._dests_actions[action.dest])==0:
                self._dests_actions.pop(action.dest)
    except:
        if throw: raise
        else: pass
    # check all groups -> never throw
    for group in self._action_groups + self._mutually_exclusive_groups:
        if action in group._group_actions:
            group._group_actions.remove(action)
        _remove_action_all(group,action,throw=False)

class _ArgumentGroup(argparse._ArgumentGroup):
    def __init__(self, container, *args, **kwargs):
        argparse._ArgumentGroup.__init__(self, container, *args, **kwargs)
        self._dests_actions = container._dests_actions
        self._config_only = container._config_only

    # keep map of dest:action(s)
    _add_action_orig = argparse._ArgumentGroup._add_action

    def _add_action(self, action):
        # check against config-only
        if action.dest in self._config_only: raise argparse.ArgumentError(action, "dest {} already specified as config-only argument".format(action.dest))

        action = self._add_action_orig(action)
        self._dests_actions[action.dest].append(action)
        return action

class _MutuallyExclusiveGroup(argparse._MutuallyExclusiveGroup):
    def __init__(self, container, **kwargs):
        argparse._MutuallyExclusiveGroup.__init__(self, container, **kwargs)
        self._dests_actions = container._dests_actions
        self._config_only = container._config_only

    # keep map of dest:action(s)
    _add_action_orig = argparse._MutuallyExclusiveGroup._add_action

    def _add_action(self, action):
        # check against config-only
        if action.dest in self._config_only: raise argparse.ArgumentError(action, "dest {} already specified as config-only argument".format(action.dest))

        action = self._add_action_orig(action)
        self._dests_actions[action.dest].append(action)
        return action

# patch to remove artificial \0 character (added to enable display of default values for config-only arguments)
def _get_help_string_clean(self, action):
    if action.help=='\0': return ''
    return action.help

argparse.HelpFormatter._get_help_string = _get_help_string_clean

_get_help_string_default_orig = argparse.ArgumentDefaultsHelpFormatter._get_help_string

def _get_help_string_default_clean(self, action):
    if action.help=='\0': action.help = ''
    return _get_help_string_default_orig(self, action)

argparse.ArgumentDefaultsHelpFormatter._get_help_string = _get_help_string_default_clean

# make sure namespace exists and is a MagiConfig
def _check_namespace(namespace):
    if namespace is None: return MagiConfig()
    elif isinstance(namespace,MagiConfig): return namespace
    elif len(vars(namespace))==0: return MagiConfig()
    else: return MagiConfig(**vars(namespace))

# hierarchical parsing for configs and ConfigObjects:
# 1. base arguments (obj, strict)
# 2. config itself
# 3. individual arguments
class ConfigParser:
    def __init__(self, root, parent, prefix=True, standalone = False):
        self.root = root
        self.parent = parent
        self.prefix = prefix
        self.parsers = {
            "base": ArgumentParser(add_help=False, wrapper=self) if not standalone else None,
            "config": ArgumentParser(add_help=False, wrapper=self) if not standalone else None,
            "args": ArgumentParser(add_help=False, wrapper=self),
        }
        self.standalone = standalone
        self.transients = []

    @property
    def base(self):
        return self.parsers["base"]
    @property
    def config(self):
        return self.parsers["config"]
    @property
    def args(self):
        return self.parsers["args"]

    def lock(self, all=False):
        for key, val in self.parsers.items():
            if key=="args" and not all:
                continue
            val._locked = True

    def parse_known_args(self, args=None, namespace=None):
        remainder = args
        if self.base:
            base_args, remainder = self.base.parse_known_args(remainder, namespace)
        if self.config:
            config_args, remainder = self.config.parse_known_args(remainder, namespace)
            # load the config using base_args info
        if self.args:
            other_args, remainder = self.args.parse_known_args(remainder, namespace)
        return other_args, remainder

class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        self._basic = kwargs.pop("basic", False)
        self._wrapper = kwargs.pop("wrapper", None)
        # must be defined before base class constructor is called
        self._dests_actions = defaultdict(list)
        self._config_only = OrderedDict()
        self._config_parsers = OrderedDict()
        self._standalone_parser = ConfigParser(self, self, standalone=True) if not self._wrapper else None
        self._default_source = None
        self._locked = False
        super().__init__(self, *args, **kwargs)

        # initialize config arg in basic scenario
        if self._basic:
            self.add_argument("-C", "--config", config=True)
            self.set_default_source("config")

    def _find_source(self, source):
        for key in self._config_parsers:
            if key==source:
                return self._config_parsers[key]["args"]
            result = self._config_parsers[key]._find_source(source)
            if result:
                return result
        return None

    def set_default_source(self, source):
        if self._find_source(source):
            self._default_source = source
        else:
            raise MagiConfigError(f"Unknown source {source}")

    def clear_default_source(self):
        self._default_source = None

    add_argument_orig = argparse.ArgumentParser.add_argument

    def add_argument_wrapped(self, *args, **kwargs):
        action = self.add_argument_orig(*args, **kwargs)
        action._wrapper = self._wrapper
        return action

    def add_argument(self, *args, **kwargs):
        # check a few base args
        type_arg = kwargs.get("type", None)
        help_arg = kwargs.get("help", None)
        default_arg = kwargs.get("default", None)

        # pull out all custom kwargs
        # inappropriate kwargs for a given case will just be ignored
        source = kwargs.pop("source", "")
        # default/basic case
        if not source and self._default_source:
            source = self._default_source
        # assign to source
        if source:
            # find source, even if nested
            source_parser = self._find_source(source)
            if source_parser:
                return source_parser.add_argument(*args, **kwargs)
            else:
                raise MagiConfigError(f"Could not find source {source}")
        # if no source, assign to standalone parser

        config = kwargs.pop("config", False)
        # convenience settings for base args (instead of using custom)
        obj = kwargs.pop("obj", None)
        strict = kwargs.pop("strict", None)
        config_only_help = kwargs.pop("config_only_help", True)
        if config:
            type_arg = MagiConfigObject

        # for ConfigObjects
        custom = kwargs.pop("custom", None)
        prefix = kwargs.pop("prefix", True)

        # for individual args
        disable = kwargs.pop("disable", False)
        transient = kwargs.pop("transient", False)
        config_only = kwargs.pop("config_only", False)

        # check for incompatible combinations
        if config_only and not self._wrapper:
            raise MagiConfigError("Cannot add config_only argument to top-level parser; please assign a source")

        config_object = isinstance(type_arg, ConfigObject)
        if config_object:
            if not help_arg: kwargs["help"] = type_arg._help
            cparser = ConfigParser(
                root = self._wrapper.root if self._wrapper else self,
                parent = self,
                prefix = prefix,
            )

            # this is the actual argument that reads the name of the config file
            config_arg = cparser.config.add_argument_wrapped(*args, type=str, **kwargs)
            config_dest = config_arg.dest

            # todo: handle convenience settings
            type_arg.add_arguments(cparser, config_dest, custom=custom)
            self._config_parsers[config_dest] = cparser

            # for ConfigObjects, lock all to prevent extra args being added via source
            cparser.lock(all=not config)

            return config_arg
        else:
            if self._locked:
                raise MagiConfigError("This parser is locked, so extra arguments cannot be added")

            if disable:
                dummy = ArgumentParser()
                disabled_action = dummy.add_argument_orig(*args, **kwargs)
                self._defaults[disabled_action.dest] = default_arg
                return None

            if config_only:
                return self.add_config_argument(*args, **kwargs)

            if self._wrapper:
                this_arg = self.add_argument_wrapped(*args, **kwargs)
            else:
                this_arg = self._standalone_parser.add_argument_wrapped(*args, **kwargs)

            # handle transient (just ignore for non-wrapped parsers)
            if transient and self._wrapper:
                self._wrapper.transients.append(this_arg.dest)

            return this_arg

    parse_known_args_orig = argparse.ArgumentParser.parse_known_args

    def _suppress_required(self, actions):
        required = []
        for action in actions:
            if action.required:
                action.required = False
                required.append(action)
        return required

    # this should take the list returned by the previous function
    def _restore_required(self, actions):
        for action in actions:
            action.required = True

    def parse_known_args(self, args=None, namespace=None):
        if args is None: args = sys.argv[1:]
        else: args = list(args)

        def check_subparser_config_actions():
            if self._subparsers is None:
                return False
            subparser_objects = next((action.choices.values() for action in self._subparsers._actions if isinstance(action,argparse._SubParsersAction)),[])
            # if any subparsers have config_actions, then return a MagiConfig
            return any(parser._config_actions is not None for parser in subparser_objects)

        # get correct namespace type
        if self._config_actions is not None or check_subparser_config_actions():
            namespace = _check_namespace(namespace)

        # fall back to default argparse behavior
        if self._config_actions is None:
            return self.parse_known_args_orig(args=args,namespace=namespace)

        # create a subordinate instance with just the config options
        config_only_parser = ArgumentParser(
            config_options = self.config_options,
            add_help = False,
        )
        # prevent exit on error() (from ConfigArgParse)
        def error_method(self, message):
            raise argparse.ArgumentError(None, message)
        config_only_parser.error = types.MethodType(error_method, config_only_parser)
        # subordinate parser is not allowed to throw or exit
        # if a required arg is missing, it will be checked later
        try:
            tmpspace, _ = config_only_parser.parse_known_args_orig(args=args)
        except:
            tmpspace = None

        # fall back to default argparse behavior
        # this will check config_required (config args still included with rest of args)
        if tmpspace is None or getattr(tmpspace,self._dest,None) is None:
            tmpspace, remaining_args = self.parse_known_args_orig(args=args,namespace=namespace)
        else:
            # get namespace as filled by config
            namespace = self.parse_config(
                getattr(tmpspace,self._dest),
                getattr(tmpspace,self._obj_dest,self.config_options.obj),
                getattr(tmpspace,self._strict_dest,self.config_options.strict),
                namespace=namespace
            )

            # call parse_known_args_orig again, with all args (supplying namespace from above)
            tmpspace, remaining_args = self.parse_known_args_orig(args=args,namespace=namespace)

            # restore required actions
            self._restore_required(self._required)
            # in case this runs again
            self._required = []

        # remove config option dests from namespace
        for dest in self._config_dests:
            if hasattr(tmpspace,dest): delattr(tmpspace,dest)

        # finish
        return tmpspace, remaining_args

    def parse_config(self, config_name, config_obj, config_strict, namespace=None):
        # in case used standalone
        namespace = _check_namespace(namespace)

        # import config as module
        config = import_config(config_name, config_obj)

        # handle values in sub-configs by restoring dots in keys
        def flatten_vars(config,pre=""):
            flat_vars = {}
            for attr,val in vars(config).items():
                if isinstance(val,MagiConfig):
                    flat_vars.update(flatten_vars(val,attr+"."))
                else:
                    flat_vars[pre+attr] = val
            return flat_vars

        # loop over vars(config) to populate namespace
        unknown_attrs = []
        self._required = []
        flat_vars = flatten_vars(config)
        possible_required_actions = []
        for attr,val in flat_vars.items():
            if attr in self._dests_actions or attr in self._config_only:
                tmp = val
                # check type if uniquely provided (and not None)
                if (len(self._dests_actions[attr])==1 or len(set([action.type for action in self._dests_actions[attr]]))==1) and self._dests_actions[attr][0].type is not None:
                    # use _get_values() rather than _get_value() to handle nargs cases; also enforces choices if any
                    tmp_action = self._dests_actions[attr][0]
                    # argparse does not apply type or choice checks to default args
                    if tmp==tmp_action.default:
                        pass
                    # nargs=0 is usually _StoreTrueAction or _StoreFalseAction:
                    # _get_values() expects an empty list for those, but we want to check the type of the provided value
                    elif isinstance(tmp_action,argparse._StoreTrueAction) or isinstance(tmp_action,argparse._StoreFalseAction):
                        tmp = bool(tmp)
                    # generically handle any other cases with nargs=0
                    elif tmp_action.nargs==0:
                        if tmp_action.type: tmp = tmp_action.type(tmp)
                    else:
                        # _get_values() expects a list
                        if not isinstance(tmp,list): tmp = [tmp]
                        tmp = self._get_values(tmp_action,tmp)
                setattr(namespace,attr,tmp)
                possible_required_actions.extend(self._dests_actions[attr])
            else:
                unknown_attrs.append(attr)
        # remove required attr from associated actions
        self._required = self._suppress_required(possible_required_actions)

        # check missing required config-only args
        config_only_missing = set([dest for dest,action in self._config_only.items() if action.required]) - set([attr for attr in flat_vars])
        if len(config_only_missing)>0:
            raise MagiConfigError("Imported config missing required attributes: "+','.join(sorted(list(config_only_missing))))

        # check strict
        if config_strict and len(unknown_attrs)>0:
            raise MagiConfigError("Imported config contained unknown attributes: "+','.join(unknown_attrs))

        return namespace

    # write namespace into file using config_obj
    def write_config(self, namespace, filename, obj=None, attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False):
        if obj is None:
            if self.config_options is not None: obj = self.config_options.obj
            else: obj = "config"
        namespace.write(filename, obj, attr_imports, class_imports, attr_reprs, class_reprs, strict)

    def _get_config_only_kwargs(self, arg, **kwargs):
        return dict(kwargs, dest=arg, option_strings=[])

    # add a config-only argument
    # available properties: default, type, choices, required, help
    # mostly based on argparse add_argument()
    def add_config_argument(self, arg, **kwargs):
        kwargs = self._get_config_only_kwargs(arg, **kwargs)

        # if no default was supplied, use the parser-level default
        if 'default' not in kwargs:
            dest = kwargs['dest']
            if dest in self._defaults:
                kwargs['default'] = self._defaults[dest]
            elif self.argument_default is not None:
                kwargs['default'] = self.argument_default

        # if not required, treat as optional (needed for some argparse handling, e.g. help w/ no default specified)
        if not kwargs.get('required',False):
            kwargs['nargs'] = argparse.OPTIONAL

        # create the (dummy) action object, and add it to the parser
        action_class = self._pop_action_class(kwargs)
        if not callable(action_class):
            raise ValueError('unknown action "%s"' % (action_class,))
        action = action_class(**kwargs)

        # raise an error if the action type is not callable
        type_func = self._registry_get('type', action.type, action.type)
        if not callable(type_func):
            raise ValueError('%r is not callable' % (type_func,))

        if type_func is FileType:
            raise ValueError('%r is a FileType class object, instance of it'
                             ' must be passed' % (type_func,))

        action = self._add_config_only_action(action)
        if action.help is None:
            if action.required: action.help = "(required)"
            elif action.default is not None: action.help = "\0" # must be non-None, non-whitespace string to activate default formatting

        return action

    # directly copied (to use patched Group classes)
    def add_argument_group(self, *args, **kwargs):
        group = _ArgumentGroup(self, *args, **kwargs)
        self._action_groups.append(group)
        return group

    def add_mutually_exclusive_group(self, **kwargs):
        group = _MutuallyExclusiveGroup(self, **kwargs)
        self._mutually_exclusive_groups.append(group)
        return group

    # changes to _add_action are now made in the Group classes

    def _add_config_only_action(self, action):
        # check for existing dests
        if action.dest in self._config_only: raise argparse.ArgumentError(action, "conflicting config-only dest: {}".format(action.dest))
        if action.dest in self._dests_actions: raise argparse.ArgumentError(action, "dest {} already specified as regular (not config-only) argument".format(action.dest))

        # add to actions list
        self._config_only[action.dest] = action
        action.container = self

        return action

    def remove_config_argument(self, arg):
        if arg in self._config_only:
            self._config_only.pop(arg)
        else:
            self.error("attempt to remove unrecognized config-only argument: {}".format(arg))

    _remove_action = _remove_action_all

    # allow removing single argument
    # for optional arguments: if keep is true, just removes the single specified arg; otherwise, removes entire action
    # for positional arguments, arg=dest, and all positional actions w/ that dest are removed
    def remove_argument(self, arg, keep=False):
        # check per arg whether positional or optional
        found = False
        if arg[0] in self.prefix_chars:
            # optional, check option strings
            if arg in self._option_string_actions:
                action = self._option_string_actions.pop(arg)
                action.option_strings.remove(arg)
                if not keep or len(action.option_strings)==0:
                    self._remove_action(action)
                found = True
        else:
            # positional, check dests
            if arg in self._dests_actions:
                for action in self._dests_actions[arg]:
                    # remove only positional
                    if len(action.option_strings)==0:
                        self._dests_actions[arg].remove(action)
                found = True
        if not found:
            self.error("attempt to remove unrecognized argument: {}".format(arg))

    # modified to include config-only args
    def format_help(self):
        formatter = self._get_formatter()

        # usage
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)

        # description
        formatter.add_text(self.description)

        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()

        # config-only args
        if len(self._config_only)>0 and self._config_only_help:
            formatter.start_section("config-only arguments")
            # get list of (dummy) actions
            config_only_actions = [action for dest,action in self._config_only.items()]
            formatter.add_arguments(config_only_actions)
            formatter.end_section()

        # epilog
        formatter.add_text(self.epilog)

        # determine help from format above
        return formatter.format_help()

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

# convenience definition
# (from ConfigArgParse)
class ArgumentDefaultsRawHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawTextHelpFormatter,
    argparse.RawDescriptionHelpFormatter):
    """HelpFormatter that adds default values AND doesn't do line-wrapping"""
pass
