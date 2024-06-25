import argparse
import sys, os, imp, uuid
import six
import collections
from six.moves.collections_abc import Sized, Iterable, Container, Mapping
import functools
import types
import warnings

__version__ = "2.4.4"

# from https://github.com/python/cpython/blob/main/Lib/_collections_abc.py
# missing from python < 3.6
def _check_methods(C, *methods):
    mro = C.__mro__
    for method in methods:
        for B in mro:
            if method in B.__dict__:
                if B.__dict__[method] is None:
                    return NotImplemented
                break
        else:
            return NotImplemented
    return True

class Collection(Sized, Iterable, Container):
    __slots__ = ()
    @classmethod
    def __subclasshook__(cls, C):
        if cls is Collection:
            return _check_methods(C,  "__len__", "__iter__", "__contains__")
        return NotImplemented

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

# denotes MagiConfig-specific errors
class MagiConfigError(Exception):
    pass

class MagiConfig(argparse.Namespace):
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
        for attr,val in sorted(six.iteritems(vars(self))):
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
                coll = six.iteritems(val)
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
    # dest = destination for config arg
    # obj = string identifying magiconfig object in module imported from config file
    # obj_args = optional argument to specify obj on command line
    # obj_help = custom help message for obj arg
    # obj_dest = destination for obj arg
    # strict = reject imported config if it has unknown keys
    # strict_args = optional argument to specify strictness on command line
    # strict_help = custom help message for strict arg
    # strict_dest = destination for strict arg
    def __init__(
        self,
        args=["-C","--config"], help=None, required=False, default="", dest="config",
        obj="config", obj_args=None, obj_help=None, obj_dest="obj",
        strict=False, strict_args=None, strict_help=None, strict_dest="strict",
    ):
        if (obj is None or len(obj)==0) and obj_args is None:
            raise MagiConfigError("obj or obj_args must be specified")

        self.args = args
        self.help = help
        self.required = required
        self.default = default
        self.dest = dest
        self.obj = obj
        self.obj_args = obj_args
        self.obj_help = obj_help
        self.obj_dest = obj_dest
        self.strict = strict
        self.strict_args = strict_args
        self.strict_help = strict_help
        self.strict_dest = strict_dest

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

class ArgumentParser(argparse.ArgumentParser):
    # additional argument:
    # config_options: default is None, otherwise expects instance of MagiConfigOptions
    def __init__(self, *args, **kwargs):
        self.config_options = kwargs.pop("config_options", None)
        self._config_only_help = kwargs.pop("config_only_help", True)
        # must be defined before base class constructor is called
        self._dests_actions = collections.defaultdict(list)
        self._config_only = collections.OrderedDict()
        argparse.ArgumentParser.__init__(self, *args, **kwargs)
        self._config_actions = None

        # to toggle legacy behavior
        self._ignore_conflict_config_only = False

        # initialize config args from options
        self._init_config()

    def _init_config(self):
        # reset relevant members
        if self._config_actions is not None:
            for config_action in self._config_actions:
                self._remove_action(config_action,throw=False)
        self._dest = ""
        self._obj_dest = ""
        self._strict_dest = ""
        self._config_actions = None

        # get dest w/ check for positionals
        # based on argparse.add_argument() condition
        # (args = None is not considered, because dest must be provided in that case)
        def check_positional(args,default_dest,chars=self.prefix_chars):
            if args is not None and len(args) == 1 and args[0][0] not in chars:
                return args[0], True
            else:
                return default_dest, False
        # set up config arg(s) if any
        # dest is fixed because it is only used in internal namespace
        if self.config_options is not None and self.config_options.args is not None and len(self.config_options.args)>0:
            self._config_actions = []
            # defaults
            self._dest, _config_pos = check_positional(self.config_options.args,self.config_options.dest)
            self._obj_dest, _obj_pos = check_positional(self.config_options.obj_args,self.config_options.obj_dest)
            self._strict_dest, _strict_pos = check_positional(self.config_options.strict_args,self.config_options.strict_dest)
            self._config_dests = [self._dest, self._obj_dest, self._strict_dest]

            # exclude dest kwarg for positional
            _config_kwargs = dict(
                type=str,
                help=self.config_options.help if self.config_options.help is not None else "name of config file to import (w/ object"+(": "+self.config_options.obj if self.config_options.obj_args is None else " from "+",".join(self.config_options.obj_args))+")",
            )
            if self.config_options.default is not None and len(self.config_options.default)>0:
                _config_kwargs.update(
                    default=self.config_options.default,
                )
            if not _config_pos:
                _config_kwargs.update(
                    dest=self._dest,
                    required=self.config_options.required,
                )
            self._config_actions.append(self.add_argument(
                *self.config_options.args,
                **_config_kwargs
            ))

            if self.config_options.obj_args is not None:
                _obj_kwargs = dict(
                    type=str,
                    help=self.config_options.obj_help if self.config_options.obj_help is not None else "name of object to import from config file",
                )
                _obj_required = self.config_options.obj is None or len(self.config_options.obj)==0
                if not _obj_required:
                    _obj_kwargs.update(
                        default=self.config_options.obj,
                    )
                if not _obj_pos:
                    _obj_kwargs.update(
                        dest=self._obj_dest,
                        required=_obj_required,
                    )
                self._config_actions.append(self.add_argument(
                    *self.config_options.obj_args,
                    **_obj_kwargs
                ))

            if self.config_options.strict_args is not None:
                # strict arg switches from the default value
                _strict_kwargs = dict(
                    action="store_true" if self.config_options.strict==False else "store_false",
                    help=self.config_options.strict_help if self.config_options.strict_help is not None else ("reject" if self.config_options.strict==False else "accept")+" imported config with unknown attributes",
                    default=self.config_options.strict,
                )
                if not _strict_pos:
                    _strict_kwargs.update(
                        dest = self._strict_dest
                    )
                self._config_actions.append(self.add_argument(
                    *self.config_options.strict_args,
                    **_strict_kwargs
                ))

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

    # make sure it exists and is a MagiConfig
    def _check_namespace(self, namespace):
        if namespace is None: return MagiConfig()
        elif isinstance(namespace,MagiConfig): return namespace
        elif len(vars(namespace))==0: return MagiConfig()
        else: return MagiConfig(vars(namespace))

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
            namespace = self._check_namespace(namespace)

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
        namespace = self._check_namespace(namespace)

        # import config as module
        # (from configurati)
        module_id = str(uuid.uuid4())
        module = imp.load_source(module_id, os.path.abspath(config_name))
        config = _rgetattr(module,config_obj)

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
        unknown_attrs = []
        self._required = []
        flat_vars = flatten_vars(config)
        possible_required_actions = []
        for attr,val in six.iteritems(flat_vars):
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
        config_only_missing = set([dest for dest,action in six.iteritems(self._config_only) if action.required]) - set([attr for attr in flat_vars])
        if len(config_only_missing)>0:
            raise MagiConfigError("Imported config missing required attributes: "+','.join(sorted(list(config_only_missing))))

        # check strict
        if config_strict and len(unknown_attrs)>0:
            raise MagiConfigError("Imported config contained unknown attributes: "+','.join(unknown_attrs))

        return namespace

    # allow modifying options for config args
    def set_config_options(self, **kwargs):
        # modify config options
        if self.config_options is None: self.config_options = MagiConfigOptions()
        for key,val in six.iteritems(kwargs):
            if hasattr(self.config_options,key): setattr(self.config_options,key,val)
            else: raise MagiConfigError("Attempt to set invalid config option: "+key)

        # reinitialize
        self._init_config()

    # also allow copying existing set of options
    def copy_config_options(self, config_options):
        self.set_config_options(**vars(config_options))

    # allow removing config options
    def remove_config_options(self):
        self.config_options = None
        self._init_config()

    # write namespace into file using config_obj
    def write_config(self, namespace, filename, obj=None, attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False):
        if obj is None:
            if self.config_options is not None: obj = self.config_options.obj
            else: obj = "config"
        namespace.write(filename, obj, attr_imports, class_imports, attr_reprs, class_reprs, strict)

    # add config-only arguments
    # args: no default value, not required
    # kwargs: default value OR required (value=None)
    def add_config_only(self, *args, **kwargs):
        deprecation("ArgumentParser.add_config_only() is deprecated and will be removed in magiconfig 3.0.0; please switch to ArgumentParser.add_config_argument().")

        # check for existing dests
        existing_dests = [arg for arg in list(args) + list(kwargs) if arg in self._dests_actions]
        if len(existing_dests)>0: raise MagiConfigError("the following dests are already used by regular (not config-only) arguments: "+', '.join(existing_dests))

        # legacy behavior: add_config_only could be called for the same dest multiple times
        self._ignore_conflict_config_only = True
        for dest in args:
            self.add_config_argument(dest)
        for dest,default in six.iteritems(kwargs):
            if default is None:
                self.add_config_argument(dest, required=True)
            else:
                self.add_config_argument(dest, default=default)
        self._ignore_conflict_config_only = False

    # remove config-only argument
    def remove_config_only(self, arg):
        deprecation("ArgumentParser.remove_config_only() is deprecated and will be removed in magiconfig 3.0.0; please switch to ArgumentParser.remove_config_argument().")

        self.remove_config_argument(arg)

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
            elif action.default is not None: action.help = " " # must be non-None string to activate default formatting
            #else: action.help = " "

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
        if action.dest in self._config_only and not self._ignore_conflict_config_only: raise argparse.ArgumentError(action, "conflicting config-only dest: {}".format(action.dest))
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
            config_only_actions = [action for dest,action in six.iteritems(self._config_only)]
            formatter.add_arguments(config_only_actions)
            formatter.end_section()

        # epilog
        formatter.add_text(self.epilog)

        # determine help from format above
        return formatter.format_help()

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

# convenience definition
# (from ConfigArgParse)
class ArgumentDefaultsRawHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawTextHelpFormatter,
    argparse.RawDescriptionHelpFormatter):
    """HelpFormatter that adds default values AND doesn't do line-wrapping"""
pass
