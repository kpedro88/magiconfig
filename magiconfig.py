"""An extension of argparse to configure Python with Python"""

__version__ = "3.0.0a1"

import argparse
import copy
import functools
import importlib
import importlib.util
import os
import sys
import warnings
from collections import OrderedDict, defaultdict
from collections.abc import Collection, Container, Mapping

__all__ = [
    "ASK",
    "CONFIG_DEFAULT_HELP",
    "MagiConfigError",
    "MagiConfig",
    "ConfigObject",
    "ArgumentParser",
    "import_config",
    "imported",
    "DictAction",
    "arguments",
    "shared",
    "app",
    "main",
    # re-exported from argparse
    "Action",
    "ArgumentDefaultsHelpFormatter",
    "ArgumentDefaultsRawHelpFormatter",
    "ArgumentError",
    "ArgumentTypeError",
    "BooleanOptionalAction",
    "FileType",
    "HelpFormatter",
    "MetavarTypeHelpFormatter",
    "Namespace",
    "ONE_OR_MORE",
    "OPTIONAL",
    "PARSER",
    "REMAINDER",
    "RawDescriptionHelpFormatter",
    "RawTextHelpFormatter",
    "SUPPRESS",
    "ZERO_OR_MORE",
]

ASK = '==ASK=='
CONFIG_DEFAULT_HELP = "name of config file to import"


class MagiConfigError(Exception):
    """Denotes MagiConfig-specific errors."""


# from https://stackoverflow.com/questions/31174295/getattr-and-setattr-on-nested-subobjects-chained-properties/31174427#31174427
def _rgetattr(obj, attr, *default):
    """getattr() for a dotted path of attributes, with an optional default."""
    def _getattr(obj, attr):
        return getattr(obj, attr, *default)
    return functools.reduce(_getattr, [obj] + attr.split('.'))


# module name -> path as given, and file state (mtime, size) when loaded, for modules loaded by import_config()
_import_config_paths = {}
_import_config_states = {}


def import_config(file_path, attrs=None):
    """Import a Python file as a module and return the requested attribute(s).

    `attrs` may be a (dotted) attribute name, a list of names, or None to return the module itself.
    The module name is derived deterministically from the absolute path,
    so a file is executed only once per process (unless it changes) and repeated imports return the same objects.
    """
    # from https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    import base64
    import hashlib

    abs_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_path):
        raise MagiConfigError(f"Config file not found: {file_path}")
    # md5 for determinism, base64 for conciseness (made identifier-safe)
    path_hash = base64.b64encode(hashlib.md5(abs_path.encode('utf-8')).digest(), b'__').decode('utf-8').rstrip('=')
    module_name = f"{os.path.basename(file_path).replace('.', '_')}__{path_hash}"
    stat = os.stat(abs_path)
    file_state = (stat.st_mtime_ns, stat.st_size)
    if module_name in sys.modules and _import_config_states.get(module_name) == file_state:
        module = sys.modules[module_name]
    else:
        # (re)load if not loaded yet or if the file changed since it was loaded
        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get(module_name)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            if previous is None:
                del sys.modules[module_name]
            else:
                sys.modules[module_name] = previous
            raise
        _import_config_paths[module_name] = file_path
        _import_config_states[module_name] = file_state

    def get(attr):
        try:
            return _rgetattr(module, attr)
        except AttributeError:
            raise MagiConfigError(f"Object {attr} not found in config file {file_path}") from None

    if attrs is None:
        return module
    elif isinstance(attrs, list):
        return [get(attr) for attr in attrs]
    else:
        return get(attrs)


def imported(config):
    """List of (path, obj) for the config files that were loaded to produce this section, in load order.

    An inline MagiConfig provided by a parent config is recorded with path None.
    """
    return config._imported


def _class_expr(cls):
    """Imports and expression to write a class object into a config file."""
    module = cls.__module__
    qualname = cls.__qualname__
    top = qualname.split('.')[0]
    if module == "__main__":
        # resolved by name (via the ConfigObject registry) when the same script reads it back
        return set(), repr(qualname)
    elif module in _import_config_paths:
        return {
            "from magiconfig import import_config",
            f"{top} = import_config({_import_config_paths[module]!r}, {top!r})",
        }, qualname
    elif module == "builtins":
        return set(), qualname
    else:
        return {f"from {module} import {top}"}, qualname


def _format_file(imports, lines, comments=None):
    """Contents of a config file: optional comments, imports (statements before assignments), then the given lines."""
    import_lines = sorted(imports, key=lambda line: (not line.startswith(("import ", "from ")), line))
    header = list(comments or []) + ["from magiconfig import MagiConfig"]
    return '\n'.join(header + import_lines + [""] + lines)


def _write_file(filename, imports, lines, comments=None):
    with open(filename, 'w') as outfile:
        outfile.write(_format_file(imports, lines, comments))


class MagiConfig(argparse.Namespace):
    """A namespace that is used both as the input object in config files and as the output of ArgumentParser.

    Attribute access with dotted names (e.g. getattr(x, "y.z")) traverses nested MagiConfigs,
    creating intermediate MagiConfigs as needed when setting.
    Hidden slots (excluded from vars(), ==, and repr) record transient attributes, the sources of built ConfigObjects,
    and the config files that were imported.
    """
    __slots__ = ("_transients", "_sources", "_imported")

    def __init__(self, **kwargs):
        object.__setattr__(self, "_transients", set())
        object.__setattr__(self, "_sources", {})
        object.__setattr__(self, "_imported", [])
        super().__init__(**kwargs)

    def vars(self, transient=False):
        """Attributes as a dict, including transient attributes only if requested."""
        return {k: v for k, v in self.__dict__.items() if transient or k not in self._transients}

    def write(self, filename, config_obj="config", attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False):
        """Write this config into a Python file that defines it as the object `config_obj`."""
        if len(config_obj) == 0:
            raise MagiConfigError("config_obj must be specified")
        imports, lines = self._write(config_obj, _WriteOptions(attr_imports, class_imports, attr_reprs, class_reprs, strict))
        _write_file(filename, imports, lines)

    def _write(self, config_obj, opts):
        imports = set()
        lines = [f"# imported from: {path} (obj: {obj})" for path, obj in self._imported if path is not None]
        lines.append(config_obj + " = MagiConfig()")
        prepend = config_obj + "."
        for attr, val in sorted(self.vars().items()):
            if attr in self._sources:
                val = self._sources[attr]
                if not isinstance(val, MagiConfig):
                    imports_tmp, expr = _source_expr(val, opts)
                    imports.update(imports_tmp)
                    lines.append(prepend + attr + " = " + expr)
                    continue
            if isinstance(val, MagiConfig):
                imports_tmp, lines_tmp = val._write(prepend + attr, opts)
                imports.update(imports_tmp)
                lines.extend(lines_tmp)
            else:
                imports_tmp, expr = opts.value_expr(prepend + attr, attr, val)
                imports.update(imports_tmp)
                lines.append(prepend + attr + " = " + expr)
        return imports, lines

    def _inline(self, opts):
        """Imports and a single MagiConfig(...) expression for this config (used inside other expressions)."""
        imports = set()
        items = []
        for attr, val in sorted(self.vars().items()):
            if attr in self._sources:
                imports_tmp, expr = _source_expr(self._sources[attr], opts)
            elif isinstance(val, MagiConfig):
                imports_tmp, expr = val._inline(opts)
            else:
                imports_tmp, expr = opts.value_expr(attr, attr, val)
            imports.update(imports_tmp)
            items.append((attr, expr))
        if all(attr.isidentifier() for attr, _ in items):
            body = ", ".join(f"{attr}={expr}" for attr, expr in items)
        else:
            body = "**{" + ", ".join(f"{attr!r}: {expr}" for attr, expr in items) + "}"
        return imports, f"MagiConfig({body})"

    def join(self, other_config, prefer_other=False):
        """Merge another config into this one, preferring this config's values unless `prefer_other`."""
        for attr, val in other_config.vars(transient=True).items():
            if prefer_other or attr not in self.__dict__:
                setattr(self, attr, val)
                # propagate hidden properties accordingly
                if attr in other_config._transients:
                    self._transients.add(attr)
                else:
                    self._transients.discard(attr)
                if attr in other_config._sources:
                    self._sources[attr] = other_config._sources[attr]
                else:
                    self._sources.pop(attr, None)
        self._imported.extend(other_config._imported)

    def __setattr__(self, attr, val):
        pre, _, post = attr.rpartition('.')
        if len(pre) > 0:
            if not hasattr(self, pre):
                setattr(self, pre, MagiConfig())
            setattr(_rgetattr(self, pre), post, val)
        else:
            object.__setattr__(self, post, val)

    def __getattr__(self, attr):
        # only called when regular lookup fails; plain names are therefore missing
        if '.' not in attr:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{attr}'")
        return _rgetattr(self, attr)


class _WriteOptions:
    """User customizations for writing values: imports and reprs by attribute or by class, and strict checking."""
    def __init__(self, attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False):
        self.attr_imports = attr_imports or {}
        self.class_imports = class_imports or {}
        self.attr_reprs = attr_reprs or {}
        self.class_reprs = class_reprs or {}
        self.strict = strict

    def value_expr(self, name, attr, val):
        """Imports and repr-style expression for a regular value."""
        if isinstance(val, type) or isinstance(val, (tuple, list, dict)) and _contains_class(val):
            return _source_expr(val, self)
        valclass = val.__class__
        imports = self.get_imports(attr, val)
        # precedence: attr-specific > class-specific > default
        repr_fn = self.attr_reprs.get(attr, self.class_reprs.get(valclass, repr))
        repr_val = repr_fn(val)
        # detect cases where repr() doesn't work as desired
        if self.strict:
            try:
                repr_worked = eval(repr_val)
            # catch cases where eval(repr) completely fails
            except Exception:
                repr_worked = False
            if not repr_worked or repr_worked != val:
                raise MagiConfigError(f"Inconsistency between original value and repr for {name}:\n{(val, repr_val)}")
        return imports, repr_val

    # recursively check imports (avoiding infinite recursion in self-referential case)
    def get_imports(self, attr, val, checked=None):
        valclass = val.__class__
        if checked is None:
            checked = set()
        imports = set()

        def default_import(val):
            valclass = val.__class__
            if valclass.__module__ == 'builtins':
                if valclass.__name__ == 'module':
                    return f"import {val.__name__}"
            else:
                return f"from {valclass.__module__} import {valclass.__name__}"
            return None

        if id(val) not in checked:
            # precedence: attr-specific > class-specific > defaults
            attr_imports_actual = {} if attr is None else self.attr_imports
            import_fn = attr_imports_actual.get(attr, self.class_imports.get(valclass, default_import))
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
                except TypeError:
                    pass
            if coll is not None:
                for subval in coll:
                    # applied to keys and values separately for dicts, i.e. attr-specific only used for MagiConfigs
                    imports.update(self.get_imports(None, subval, checked))

        return imports


def _contains_class(val, checked=None):
    """Whether a (nested) tuple/list/dict contains class objects, which need imports rather than repr()."""
    if checked is None:
        checked = set()
    if isinstance(val, type):
        return True
    if not isinstance(val, (tuple, list, dict)) or id(val) in checked:
        return False
    checked.add(id(val))
    items = val.values() if isinstance(val, dict) else val
    return any(_contains_class(item, checked) for item in items)


def _source_expr(val, opts):
    """Imports and expression for the source of a built ConfigObject
    (a MagiConfig, a (class, MagiConfig) tuple for typed args, or a list/dict of those for containers),
    or for any tuple/list/dict containing classes."""
    if isinstance(val, MagiConfig):
        return val._inline(opts)
    elif isinstance(val, type):
        return _class_expr(val)
    elif isinstance(val, (tuple, list)):
        imports = set()
        exprs = []
        for item in val:
            imports_tmp, expr = _source_expr(item, opts)
            imports.update(imports_tmp)
            exprs.append(expr)
        if isinstance(val, tuple):
            return imports, "(" + ", ".join(exprs) + ("," if len(exprs) == 1 else "") + ")"
        return imports, "[" + ", ".join(exprs) + "]"
    elif isinstance(val, dict):
        imports = set()
        exprs = []
        for key, item in val.items():
            imports_tmp, expr = _source_expr(item, opts)
            imports.update(imports_tmp)
            exprs.append(f"{key!r}: {expr}")
        return imports, "{" + ", ".join(exprs) + "}"
    else:
        return opts.value_expr(None, None, val)


def _check_namespace(namespace):
    """Make sure the namespace exists and is a MagiConfig."""
    if namespace is None:
        return MagiConfig()
    elif isinstance(namespace, MagiConfig):
        return namespace
    else:
        return MagiConfig(**vars(namespace))


def _mark_transient(namespace, dest):
    pre, _, post = dest.rpartition('.')
    target = _rgetattr(namespace, pre, None) if pre else namespace
    if isinstance(target, MagiConfig):
        target._transients.add(post)


def _as_list(values):
    if values is None:
        return []
    elif isinstance(values, (list, tuple)):
        return list(values)
    else:
        return [values]


# base arguments for each config section: added to the section's "base" parser, and disabled unless requested
_BASE_ARGUMENTS = dict(
    obj=dict(type=str, default="config", disable=True, help="name of object to import from config file"),
    strict=dict(action=argparse.BooleanOptionalAction, default=False, disable=True, help="reject imported config with unknown attributes"),
    src=dict(type=str, default=None, disable=True, help="module or file (.py) that defines the class"),
)

# magiconfig-specific kwargs for add_argument()
_MAGI_KWARGS = (
    "config", "source", "obj", "strict", "src", "config_choices", "container", "custom", "prefix", "description",
    "config_only", "config_only_help", "transient", "disable",
)

# name -> {(module, qualname): class} for all ConfigObject subclasses
_config_object_registry = defaultdict(dict)


def _is_config_object(cls):
    return isinstance(cls, type) and issubclass(cls, ConfigObject)


class ConfigObject:
    """A class whose inputs are specified as argparse arguments.

    Subclasses define:
    * `_arguments`: dict of {name: add_argument kwargs}; each name is the dest and the flag (--{prefix}{name})
    * `_description`: text for the help section and the generated docstring
    * `_mutually_exclusive`: list of dict(arguments=[names], required=bool)
    * `_principal`: optional callable taking **kwargs, built instead of the class itself (proxy mode)

    A ConfigObject can be added to an ArgumentParser as a single argument (type=SomeConfigObject),
    which expands to provide all of its arguments, or built standalone from a config with build().
    """
    _arguments = {}
    _description = ""
    _mutually_exclusive = []
    _principal = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _config_object_registry[cls.__name__][(cls.__module__, cls.__qualname__)] = cls
        cls.__doc__ = cls._generate_doc(cls.__dict__.get("__doc__"))

    @classmethod
    def _generate_doc(cls, own_doc):
        parts = [text.strip() for text in (cls._description, own_doc) if text and text.strip()]
        if cls._arguments:
            arg_lines = ["Arguments:"]
            for name, kwargs in cls._arguments.items():
                props = []
                type_arg = kwargs.get("type")
                if type_arg is not None:
                    props.append(getattr(type_arg, "__name__", repr(type_arg)))
                if kwargs.get("required"):
                    props.append("required")
                elif "default" in kwargs:
                    default = kwargs["default"]
                    props.append(f"default: {default.__name__ if isinstance(default, type) else repr(default)}")
                line = f"    {name}" + (f" ({', '.join(props)})" if props else "")
                if kwargs.get("help"):
                    line += f": {kwargs['help']}"
                arg_lines.append(line)
            parts.append("\n".join(arg_lines))
        return "\n\n".join(parts) if parts else None

    @classmethod
    def build(cls, config, obj="config", strict=False):
        """Build an instance from a config (a file path or a MagiConfig), without any command-line parsing.

        Defaults, types, choices, required arguments, and strictness are applied as on the command line.
        Errors are raised as exceptions.
        """
        root = ArgumentParser(prog=cls.__name__, add_help=False)
        root.add_argument("--config", type=cls, obj=obj, strict=strict)
        value, _, _ = root._config_parsers["config"].parse([], config, False)
        return value

    @classmethod
    def _build_impl(cls, source):
        """Construct the object from a parsed MagiConfig `source`, keeping only the attributes in `_arguments`.

        Can be overridden to customize construction.
        """
        kwargs = {k: v for k, v in source.vars(transient=True).items() if k in cls._arguments}
        builder = cls._principal if cls._principal is not None else cls
        return builder(**kwargs)

    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)

    def __repr__(self):
        return repr(MagiConfig(**vars(self)))

    def __eq__(self, other):
        return type(self) is type(other) and vars(self) == vars(other)


def _remove_action_all(container, action):
    """Remove an action from a container and from all of its groups."""
    if action in container._actions:
        container._actions.remove(action)
    for option_string in action.option_strings:
        if container._option_string_actions.get(option_string) is action:
            container._option_string_actions.pop(option_string)
    dests_actions = container._dests_actions
    if action in dests_actions.get(action.dest, []):
        dests_actions[action.dest].remove(action)
        if len(dests_actions[action.dest]) == 0:
            dests_actions.pop(action.dest)
    for group in container._action_groups + container._mutually_exclusive_groups:
        if action in group._group_actions:
            group._group_actions.remove(action)


def _check_group_kwargs(kwargs):
    magi = [key for key in kwargs if key in _MAGI_KWARGS]
    if magi:
        raise MagiConfigError(f"magiconfig arguments cannot be used in argument groups: {', '.join(magi)}")


class _ArgumentGroup(argparse._ArgumentGroup):
    """Argument group that lets its parser (_parser) track and check every action that is added."""
    def add_argument(self, *args, **kwargs):
        _check_group_kwargs(kwargs)
        return super().add_argument(*args, **kwargs)

    def _add_action(self, action):
        self._parser._pre_add_action(action)
        action = super()._add_action(action)
        self._parser._post_add_action(action)
        return action


class _MutuallyExclusiveGroup(argparse._MutuallyExclusiveGroup):
    def add_argument(self, *args, **kwargs):
        _check_group_kwargs(kwargs)
        return super().add_argument(*args, **kwargs)


class _MagiFormatterMixin:
    """Help formatting for magiconfig parsers (applied only to their formatters)."""
    def _format_action(self, action):
        # config-only arguments: show only the default (if the formatter displays defaults) or required status
        if action.help == '\0':
            action = copy.copy(action)
            action.help = ''
            action.help = super()._get_help_string(action).strip() or None
        return super()._format_action(action)


_formatter_classes = {}


def _magi_formatter_class(cls):
    if cls not in _formatter_classes:
        _formatter_classes[cls] = type(cls.__name__, (_MagiFormatterMixin, cls), {})
    return _formatter_classes[cls]


class _MagiParserBase:
    """Logic shared by the top-level and nested parsers: config-only args, dest tracking, reading configs."""
    def _init_magi(self):
        # must be defined before the argparse constructor is called
        self._dests_actions = defaultdict(list)
        self._config_only = OrderedDict()
        self._transients = set()
        self._groups_locked = False

    def add_argument_group(self, *args, **kwargs):
        if self._groups_locked:
            raise MagiConfigError("Only the top-level parser can have argument groups")
        group = _ArgumentGroup(self, *args, **kwargs)
        group._parser = self
        self._action_groups.append(group)
        return group

    def add_mutually_exclusive_group(self, **kwargs):
        group = _MutuallyExclusiveGroup(self, **kwargs)
        self._mutually_exclusive_groups.append(group)
        return group

    def _pre_add_action(self, action):
        if action.dest in self._config_only:
            raise argparse.ArgumentError(action, f"dest {action.dest} already specified as config-only argument")

    def _post_add_action(self, action):
        self._dests_actions[action.dest].append(action)

    def _add_config_only(self, arg, hidden=False, **kwargs):
        """Add a (dummy) action for a dest that is only provided by configs, not by the command line.
        Supported kwargs: default, type, choices, required, help, action."""
        kwargs = dict(kwargs, dest=arg, option_strings=[])

        # if no default was supplied, use the parser-level default
        if 'default' not in kwargs:
            if arg in self._defaults:
                kwargs['default'] = self._defaults[arg]
            elif self.argument_default is not None:
                kwargs['default'] = self.argument_default

        action_class = self._pop_action_class(kwargs)
        if not callable(action_class):
            raise ValueError(f'unknown action "{action_class}"')
        # if not required, treat as optional (needed for some argparse handling, e.g. help w/ no default specified)
        if not kwargs.get('required', False) and action_class is argparse._StoreAction:
            kwargs['nargs'] = argparse.OPTIONAL
        action = action_class(**kwargs)

        type_func = self._registry_get('type', action.type, action.type)
        if not callable(type_func):
            raise ValueError(f'{type_func!r} is not callable')

        if action.dest in self._config_only:
            raise argparse.ArgumentError(action, f"conflicting config-only dest: {action.dest}")
        if action.dest in self._dests_actions:
            raise argparse.ArgumentError(action, f"dest {action.dest} already specified as regular (not config-only) argument")

        action.container = self
        action.hidden = hidden
        self._config_only[action.dest] = action
        # defaults of config-only args populate the namespace
        if action.default is not None:
            self._defaults[action.dest] = action.default

        if action.help is None:
            if action.required:
                action.help = "(required)"
            elif action.default is not None:
                # must be a non-whitespace string to activate default formatting (removed by _MagiFormatterMixin)
                action.help = '\0'

        return action

    def _parse_config(self, config, strict, namespace, suppress_required, child_dests=()):
        """Populate the namespace from a loaded config, checking types and choices of known dests.

        Attributes matching a child section's dest are returned separately (to be passed to that child).
        Transient dests are never read from configs and count as unknown.
        """
        child_inherited = {}
        flat_vars = {}

        # handle values in sub-configs by restoring dots in keys
        def flatten_vars(config, pre=""):
            for attr, val in config.vars().items():
                if not pre and attr in child_dests:
                    child_inherited[attr] = val
                elif isinstance(val, MagiConfig):
                    flatten_vars(val, pre + attr + ".")
                else:
                    flat_vars[pre + attr] = val
        flatten_vars(config)

        unknown_attrs = []
        for attr, val in flat_vars.items():
            actions = self._dests_actions.get(attr) or ([self._config_only[attr]] if attr in self._config_only else None)
            if actions is None or attr in self._transients:
                unknown_attrs.append(attr)
                continue
            from_config = getattr(actions[0], "from_config", None)
            if from_config is not None:
                val = from_config(val)
            # check type (if uniquely provided and not None) and choices
            elif len(set(action.type for action in actions)) == 1 and (actions[0].type is not None or actions[0].choices is not None):
                action = actions[0]
                # argparse does not apply type or choice checks to default args
                if val == action.default:
                    pass
                # nargs=0 is usually _StoreTrueAction or _StoreFalseAction:
                # _get_values() expects an empty list for those, but we want to check the type of the provided value
                elif action.nargs == 0:
                    if action.type is not None:
                        val = action.type(val)
                else:
                    # use _get_values() rather than _get_value() to handle nargs cases; also enforces choices if any
                    val = self._get_values(action, val if isinstance(val, list) else [val])
            elif isinstance(actions[0], (argparse._StoreTrueAction, argparse._StoreFalseAction)):
                val = bool(val)
            setattr(namespace, attr, val)
            # values from the config satisfy required arguments
            for action in actions:
                if action.required:
                    action.required = False
                    self._root._suppressed.append(action)

        if not suppress_required:
            config_only_missing = sorted(dest for dest, action in self._config_only.items() if action.required and dest not in flat_vars)
            if config_only_missing:
                raise MagiConfigError("Imported config(s) missing required attributes: " + ','.join(config_only_missing))

        if strict and unknown_attrs:
            raise MagiConfigError("Imported config(s) contained unknown attributes: " + ','.join(unknown_attrs))

        return child_inherited

    def _add_disabled(self, args, kwargs):
        """An argument that does not appear on the command line or in the help; its default populates the namespace."""
        if len(args) == 1 and args[0][:1] not in self.prefix_chars:
            dest = args[0]
        else:
            dest = self._get_optional_kwargs(*args, **kwargs)["dest"]
        self._defaults[dest] = kwargs.get("default")
        return dest


class _NestedParser(_MagiParserBase, argparse.ArgumentParser):
    """Internal parser for one part (base args, config arg, or args) of a config section."""
    def __init__(self, root, allow_positionals=False):
        self._init_magi()
        self._root = root
        self._allow_positionals = allow_positionals
        super().__init__(
            prog=root.prog,
            add_help=False,
            allow_abbrev=False,
            prefix_chars=root.prefix_chars,
            argument_default=root.argument_default,
            formatter_class=root.formatter_class,
            exit_on_error=root.exit_on_error,
        )
        self._groups_locked = True

    def error(self, message):
        # reported by the top-level parser, with its usage and prog
        raise argparse.ArgumentError(None, message)

    def _pre_add_action(self, action):
        if not action.option_strings and not self._allow_positionals:
            raise MagiConfigError(f"Positional argument {action.dest} cannot be added to a config section; positional arguments are only allowed in the top-level parser")
        super()._pre_add_action(action)
        root = self._root
        for option_string in action.option_strings:
            if option_string in root._option_string_actions or option_string in root._nested_option_strings or option_string in self._option_string_actions:
                raise argparse.ArgumentError(action, f"conflicting option string: {option_string}")

    def _post_add_action(self, action):
        super()._post_add_action(action)
        for option_string in action.option_strings:
            self._root._nested_option_strings[option_string] = (self, action)


class _SubParsersAction(argparse._SubParsersAction):
    """Keeps the hidden properties of a subparser's MagiConfig result in the parent's MagiConfig."""
    def __call__(self, parser, namespace, values, option_string=None):
        subparser = self._name_parser_map.get(values[0])
        if not isinstance(namespace, MagiConfig) or not isinstance(subparser, ArgumentParser):
            return super().__call__(parser, namespace, values, option_string)

        parse_known_args = subparser.parse_known_args

        def wrapped(*args, **kwargs):
            subnamespace, arg_strings = parse_known_args(*args, **kwargs)
            if isinstance(subnamespace, MagiConfig):
                namespace._transients.update(subnamespace._transients)
                namespace._sources.update(subnamespace._sources)
                namespace._imported.extend(subnamespace._imported)
            return subnamespace, arg_strings

        subparser.parse_known_args = wrapped
        try:
            return super().__call__(parser, namespace, values, option_string)
        finally:
            del subparser.parse_known_args


# sentinel to detect whether a config arg was given on the command line
_UNSET = object()


class ConfigParser:
    """A config section (from a config=True or ConfigObject argument), parsed hierarchically:
    1. base arguments (obj, strict, src)
    2. the config argument itself
    3. the section's arguments, including nested sections

    Variants:
    * typed (action="specify_type"): the ConfigObject class is chosen on the command line or in the parent config,
      and the section's arguments are rebuilt for that class (set_type)
    * container (container=list or dict): a list or dict of ConfigObjects, with one element section per index or key;
      element sections are rebuilt at each parse
    """
    def __init__(self, root, parent, dest, ctype, prefix=True, description=None, config_only_help=True,
                 typed=False, container=None, element=False, choices=None, config_choices=None, custom=None):
        self.root = root
        self.parent = parent
        self.dest = dest
        self.ctype = ctype
        self.prefix = prefix
        self.path = f"{parent.path}.{dest}" if parent is not None else dest
        # location of this section's values in the top-level namespace
        if prefix:
            self.ns_path = f"{parent.ns_path}.{dest}" if parent is not None and parent.ns_path else dest
        else:
            self.ns_path = parent.ns_path if parent is not None else ""
        double_prefix = root.prefix_chars[0] * 2
        self.flag_prefix = f"{double_prefix}{self.ns_path}." if self.ns_path else double_prefix
        self.base = _NestedParser(root)
        self.config = _NestedParser(root, allow_positionals=parent is None)
        self.args = _NestedParser(root)
        self.children = OrderedDict()
        self.user_description = description
        self.config_only_help = config_only_help
        self.config_action = None
        self.typed = typed
        self.container = container
        self.element = element
        self.choices = choices
        self.config_choices = config_choices
        self.custom = custom or {}
        # for containers: the element class (if not typed) and the default container value
        self.element_type = None
        self.container_default = None
        # user arguments can be added (via source) only to config=True sections
        self.locked = ctype is not MagiConfig

    @property
    def description(self):
        if self.user_description is not None:
            return self.user_description
        return getattr(self.ctype, "_description", None) or None

    def parsers(self):
        return [self.base, self.config, self.args]

    def sections(self):
        """This section and all nested sections, depth first."""
        yield self
        for child in self.children.values():
            yield from child.sections()

    def base_names(self):
        return ("obj", "strict", "src") if self.typed else ("obj", "strict")

    def parse(self, args, inherited, suppress_required):
        """Parse this section from the command line `args`, with an optional value `inherited` from the parent config.

        Returns (value, source, remaining args): the value is a MagiConfig for config=True sections
        or a built object for ConfigObjects; the source is what is written to reproduce it
        (the MagiConfig used to build it, a (class, MagiConfig) tuple for typed args, or a list/dict of those for containers).
        """
        root = self.root
        # required flags are suppressed only while this section is parsed
        mark = len(root._suppressed)
        try:
            return self._parse(args, inherited, suppress_required)
        finally:
            root._restore_required(mark)

    def _parse(self, args, inherited, suppress_required):
        root = self.root
        if suppress_required or inherited is not None:
            root._suppress_required([self.config_action])
        if suppress_required:
            root._suppress_required(self.base._actions)
        base_ns, args = self.base.parse_known_args(args, argparse.Namespace())
        cfg_ns, args = self.config.parse_known_args(args, argparse.Namespace(**{self.config_action.dest: _UNSET}))
        given = getattr(cfg_ns, self.config_action.dest)

        if self.container is not None:
            return self.parse_container(args, given, inherited, base_ns, suppress_required)

        if given is not _UNSET:
            values = given
        elif inherited is not None:
            values = inherited
        else:
            values = self.config_action.default

        if self.typed:
            cls, values = self.split_typed(values, given is not _UNSET)
            if cls is None:
                if self.element:
                    raise MagiConfigError(f"{self.config_name()}: a class must be specified")
                return None, None, args
            cls = self.resolve_class(cls, base_ns.src)
            if cls is not self.ctype:
                self.set_type(cls)
            for value in _as_list(values):
                if isinstance(value, str):
                    self.check_choice(value, self.config_choices)

        loaded = self.load(values, base_ns.obj)

        namespace = MagiConfig()
        child_inherited = self.args._parse_config(loaded, base_ns.strict, namespace, suppress_required, self.children)
        for child in self.children.values():
            cvalue, csource, args = child.parse(args, child_inherited.get(child.dest), suppress_required)
            child.attach(namespace, cvalue, csource)
        if suppress_required:
            root._suppress_required(self.args._actions)
        namespace, args = self.args.parse_known_args(args, namespace)
        for dest in self.args._transients:
            _mark_transient(namespace, dest)
        namespace._imported.extend(loaded._imported)

        # with prefix=False, the fields are merged into the parent namespace, so nothing is built
        if self.ctype is MagiConfig or not self.prefix:
            return namespace, namespace, args
        value = self.ctype._build_impl(namespace)
        return value, (self.ctype, namespace) if self.typed else namespace, args

    def load(self, values, objs):
        """Load and join the config(s) in order (later ones preferred): paths are imported, MagiConfigs used directly."""
        values = _as_list(values)
        objs = _as_list(objs)
        if len(objs) == 1:
            objs = objs * len(values)
        if len(objs) != len(values):
            raise MagiConfigError(f"{self.config_name()}: must specify either 1 or N config objects, where N is the number of configs")
        loaded = MagiConfig()
        for value, obj in zip(values, objs):
            if isinstance(value, MagiConfig):
                config = value
                path = None
            elif isinstance(value, str):
                config = import_config(value, obj)
                path = value
            else:
                raise MagiConfigError(f"{self.config_name()}: invalid config value {value!r} (expected a file name or a MagiConfig)")
            loaded.join(config, prefer_other=True)
            loaded._imported.append((path, obj))
        return loaded

    def config_name(self):
        return "argument " + ("/".join(self.config_action.option_strings) or self.config_action.dest)

    # typed sections

    def split_typed(self, values, from_command_line):
        """Split a typed value into (class or name, config values).

        Command line: [TYPE, CONFIG...]. Parent config or default: a class or name, a (class or name, config...) tuple,
        or a MagiConfig (with the default class).
        """
        if from_command_line:
            return values[0], values[1:]
        elif isinstance(values, tuple):
            return values[0], list(values[1:])
        elif isinstance(values, MagiConfig):
            return self.config_action.default, [values]
        else:
            return values, []

    def check_choice(self, value, choices, name=None):
        if choices is not None and value not in choices:
            names = ", ".join(choice.__name__ if isinstance(choice, type) else repr(choice) for choice in choices)
            shown = name if name is not None else value
            raise argparse.ArgumentError(None, f"{self.config_name()}: invalid choice: {shown!r} (choose from {names})")

    def resolve_class(self, value, src):
        """Resolve a class or class name: src (module or .py file) > choices (by name) > ConfigObject registry."""
        if isinstance(value, type):
            cls = value
        elif src is not None:
            module = import_config(src) if src.endswith(".py") else importlib.import_module(src)
            cls = getattr(module, value, None)
            if cls is None:
                raise MagiConfigError(f"{self.config_name()}: class {value} not found in {src}")
        else:
            cls = next((choice for choice in self.choices or [] if isinstance(choice, type) and choice.__name__ == value), None)
            if cls is None:
                candidates = list(_config_object_registry.get(value, {}).values())
                if len(candidates) > 1:
                    modules = ", ".join(candidate.__module__ for candidate in candidates)
                    raise MagiConfigError(f"{self.config_name()}: class name {value} is ambiguous (defined in {modules}); specify src")
                if not candidates:
                    if self.choices is not None:
                        self.check_choice(value, self.choices)
                    raise MagiConfigError(f"{self.config_name()}: unknown ConfigObject class {value}")
                cls = candidates[0]
        if not _is_config_object(cls):
            raise MagiConfigError(f"{self.config_name()}: {cls!r} is not a ConfigObject")
        if self.choices is not None and not any(choice is cls if isinstance(choice, type) else choice == cls.__name__ for choice in self.choices):
            self.check_choice(None, self.choices, cls.__name__)
        return cls

    def set_type(self, ctype):
        """(Re)build the section's arguments for a ConfigObject class."""
        self.unregister(args_only=True)
        self.args = _NestedParser(self.root)
        self.children = OrderedDict()
        self.ctype = ctype
        self.root._populate(self, ctype)

    def unregister(self, args_only=False):
        """Remove the option strings of this section (and nested sections) from the global registry."""
        registry = self.root._nested_option_strings
        parsers = [self.args] if args_only else self.parsers()
        for child in self.children.values():
            child.unregister()
        for parser in parsers:
            for action in parser._actions:
                for option_string in action.option_strings:
                    registry.pop(option_string, None)

    # containers

    def load_container(self, values, obj):
        """Load and join container config files (by index or key, later ones preferred)."""
        result = self.container()
        for value in values:
            loaded = import_config(value, obj)
            self.check_container(loaded)
            if self.container is list:
                result[:len(loaded)] = loaded
            else:
                result.update(loaded)
        return result

    def check_container(self, value):
        if not isinstance(value, self.container):
            raise MagiConfigError(f"{self.config_name()}: expected a {self.container.__name__}, got {type(value).__name__}")
        if self.container is dict:
            for key in value:
                self.check_key(key)

    def check_key(self, key):
        if not isinstance(key, str) or not key or "." in key or key in _BASE_ARGUMENTS:
            raise MagiConfigError(f"{self.config_name()}: invalid key {key!r} (keys must be non-empty strings without '.' and cannot be {', '.join(_BASE_ARGUMENTS)})")

    def element_flags(self, args):
        """Indices or keys of element flags (--{dest}.{index or key}) on the command line, in order."""
        keys = []
        for arg in args:
            if arg == "--":
                break
            if arg.startswith(self.flag_prefix):
                segment = arg[len(self.flag_prefix):].split("=", 1)[0]
                if "." not in segment and segment not in self.base_names() and segment not in keys:
                    keys.append(segment)
        return keys

    def parse_container(self, args, given, inherited, base_ns, suppress_required):
        if given is not _UNSET:
            value = self.load_container(given, base_ns.obj)
        elif inherited is not None:
            value = inherited
        elif self.container_default is not None:
            value = self.container_default
        else:
            value = self.container()
        self.check_container(value)

        new_keys = self.element_flags(args)
        if self.container is list:
            for key in new_keys:
                if not key.isdigit():
                    raise MagiConfigError(f"{self.config_name()}: invalid list index {key!r}")
            appended = sorted(int(key) for key in new_keys if int(key) >= len(value))
            if appended != list(range(len(value), len(value) + len(appended))):
                raise MagiConfigError(f"{self.config_name()}: list indices must be existing or consecutive after the last element ({len(value)})")
            keys = list(range(len(value) + len(appended)))
        else:
            for key in new_keys:
                self.check_key(key)
            keys = list(value) + [key for key in new_keys if key not in value]

        # elements are rebuilt at each parse
        for child in self.children.values():
            child.unregister()
        self.children = OrderedDict()

        values = self.container()
        sources = self.container()
        for key in keys:
            child = self.root._add_element(self, key, base_ns)
            element = value[key] if (key < len(value) if self.container is list else key in value) else None
            cvalue, csource, args = child.parse(args, element, suppress_required)
            if self.container is list:
                values.append(cvalue)
                sources.append(csource)
            else:
                values[key] = cvalue
                sources[key] = csource
        return values, sources, args

    def attach(self, namespace, value, source):
        """Store this section's result in the parent namespace: under its dest, or merged if prefix=False."""
        if self.prefix:
            setattr(namespace, self.dest, value)
            if isinstance(namespace, MagiConfig):
                if source is not value and source is not None:
                    namespace._sources[self.dest] = source
                else:
                    namespace._sources.pop(self.dest, None)
        elif isinstance(namespace, MagiConfig):
            namespace.join(source, prefer_other=True)
        else:
            for attr, val in source.vars(transient=True).items():
                setattr(namespace, attr, val)

    def find(self, path):
        """All sections (this one or nested) whose full dotted path or bare dest matches."""
        return [section for section in self.sections() if section.path == path or section.dest == path]

    def section_actions(self):
        return self.config._actions + self.base._actions + self.args._actions

    def format_help(self, formatter, level, depth):
        formatter.start_section(self.path)
        formatter.add_text(self.description)
        show_children = depth is None or level < depth
        actions = self.section_actions()
        if not show_children:
            actions = actions + [action for child in self.children.values() for action in child.config._actions + child.base._actions]
        formatter.add_arguments(actions)
        config_only = [action for action in self.args._config_only.values() if not action.hidden]
        if config_only and self.config_only_help:
            formatter.start_section("config-only arguments")
            formatter.add_arguments(config_only)
            formatter.end_section()
        if show_children:
            for child in self.children.values():
                child.format_help(formatter, level + 1, depth)
            if self.container is not None and not self.children:
                self.format_element_template(formatter, level + 1, depth)
        formatter.end_section()

    def format_element_template(self, formatter, level, depth):
        """Document the elements of an empty container."""
        segment = "N" if self.container is list else "KEY"
        if self.typed:
            names = ", ".join(choice.__name__ if isinstance(choice, type) else str(choice) for choice in self.choices or [])
            text = f"elements: {self.flag_prefix}{segment} TYPE [CONFIG ...]" + (f" (choose from {names})" if names else "")
            formatter.add_text(text)
            return
        # build the element section in a separate parser, so its flags are not registered here
        template = ArgumentParser(prog=self.root.prog, prefix_chars=self.root.prefix_chars, formatter_class=self.root.formatter_class, add_help=False)
        template.add_argument(self.flag_prefix + segment, type=self.element_type, nargs="*", metavar="CONFIG", help="element config")
        for section in template._config_parsers.values():
            section.format_help(formatter, level, depth)

    def remove(self):
        """Remove this section (and all nested sections) from the top-level parser."""
        root = self.root
        self.unregister()
        for section in self.sections():
            if root._default_source is section:
                root._default_source = None
        siblings = self.parent.children if self.parent is not None else root._config_parsers
        siblings.pop(self.dest)


class ArgumentParser(_MagiParserBase, argparse.ArgumentParser):
    """Drop-in replacement for argparse.ArgumentParser that can also read values from Python config files.

    Additional constructor arguments:
    * basic: add a config arg -C/--config whose values are merged into the result (prefix=False),
      and use it as the default source for subsequent arguments
    * auto_source: each new config=True arg becomes the default source for subsequent arguments
    * help_depth: number of levels of config sections to show in the help (None = all)
    """
    def __init__(self, *args, basic=False, auto_source=False, help_depth=None, **kwargs):
        self._init_magi()
        self._config_parsers = OrderedDict()
        self._nested_option_strings = {}
        self._default_source = None
        self._auto_source = auto_source
        self.help_depth = help_depth
        self._suppressed = []
        # record of magiconfig-specific calls, replayed for parsers that use this one as a parent
        self._magi_calls = []
        self._replayed_groups = {}
        super().__init__(*args, **kwargs)
        self.register('action', 'parsers', _SubParsersAction)
        # argparse copies the native actions of parents; the config sections are recreated from the recorded calls
        parents = args[4] if len(args) > 4 else kwargs.get("parents", [])
        for parent in parents:
            for method, call_args, call_kwargs in getattr(parent, "_magi_calls", []):
                getattr(self, method)(*call_args, **call_kwargs)

        if basic:
            self.add_argument("-C", "--config", config=True, prefix=False)
            self.set_default_source("config")

    # sections

    def _sections(self):
        for cparser in self._config_parsers.values():
            yield from cparser.sections()

    def _find_section(self, source):
        matches = [section for cparser in self._config_parsers.values() for section in cparser.find(source)]
        if len(matches) == 0:
            raise MagiConfigError(f"Unknown source {source}")
        elif len(matches) > 1:
            raise MagiConfigError(f"Ambiguous source {source}: could be {', '.join(section.path for section in matches)}")
        return matches[0]

    def set_default_source(self, source):
        """Assign subsequent arguments (without an explicit source) to this config section."""
        self._default_source = self._find_section(source)
        self._magi_calls.append(("set_default_source", (source,), {}))

    def clear_default_source(self):
        """Subsequent arguments (without an explicit source) are added to this parser itself."""
        self._default_source = None
        self._magi_calls.append(("clear_default_source", (), {}))

    def _has_configs(self):
        if self._config_parsers:
            return True
        if self._subparsers is not None:
            for action in self._subparsers._group_actions:
                if isinstance(action, argparse._SubParsersAction):
                    for parser in action.choices.values():
                        if isinstance(parser, ArgumentParser) and parser._has_configs():
                            return True
        return False

    # adding arguments

    def add_argument(self, *args, **kwargs):
        """argparse add_argument(), with additional kwargs for configs and config sections (see README)."""
        magi = {key: kwargs.pop(key) for key in _MAGI_KWARGS if key in kwargs}
        if not magi and self._default_source is None and not self._creates_section(kwargs, magi):
            return super().add_argument(*args, **kwargs)

        self._magi_calls.append(("add_argument", args, dict(kwargs, **magi)))
        source = magi.pop("source", None)
        if source is not None:
            section = self._find_section(source)
            if section.locked:
                raise MagiConfigError(f"Arguments cannot be added to ConfigObject section {section.path}")
        elif not magi.get("config", False) and kwargs.get("action") not in ("help", "version", argparse._HelpAction, argparse._VersionAction):
            # config=True args always create top-level sections; ConfigObjects are nested in the default source
            section = self._default_source
        else:
            section = None
        return self._add(section, args, kwargs, magi)

    def add_mutually_exclusive_group(self, source=None, **kwargs):
        """argparse add_mutually_exclusive_group(), optionally in a config section (source)."""
        if source is None:
            return super().add_mutually_exclusive_group(**kwargs)
        section = self._find_section(source)
        if section.locked:
            raise MagiConfigError(f"Arguments cannot be added to ConfigObject section {section.path}")
        group = section.args.add_mutually_exclusive_group(**kwargs)
        # record additions to this group, for parsers that use this one as a parent
        index = len(self._magi_calls)
        self._magi_calls.append(("_add_group", (index, source), kwargs))
        add_argument = group.add_argument

        def add_argument_recorded(*args, **kwargs):
            self._magi_calls.append(("_add_to_group", (index,) + args, kwargs))
            return add_argument(*args, **kwargs)
        group.add_argument = add_argument_recorded
        return group

    def _add_group(self, index, source, **kwargs):
        self._replayed_groups[index] = self.add_mutually_exclusive_group(source=source, **kwargs)

    def _add_to_group(self, index, *args, **kwargs):
        return self._replayed_groups[index].add_argument(*args, **kwargs)

    @staticmethod
    def _creates_section(kwargs, magi):
        return magi.get("config", False) or _is_config_object(kwargs.get("type")) or kwargs.get("action") == "specify_type"

    def _add(self, section, args, kwargs, magi, group=None):
        """Add an argument to a config section (or to this parser if section is None)."""
        if self._creates_section(kwargs, magi):
            return self._add_section(section, args, kwargs, magi)

        parser = section.args if section is not None else self
        target = group if group is not None else parser
        transient = magi.pop("transient", False)
        config_only = magi.pop("config_only", False)
        disable = magi.pop("disable", False)
        if magi:
            raise MagiConfigError(f"Arguments only valid for config args: {', '.join(magi)}")
        if config_only:
            if transient:
                raise MagiConfigError(f"Argument {args[0]} cannot be both transient and config-only")
            if section is None:
                raise MagiConfigError(f"Cannot add config-only argument {args[0]} to top-level parser; please assign a source")
            return parser._add_config_only(*args, **kwargs)
        if disable:
            dest = parser._add_disabled(args, kwargs)
            if section is not None:
                # still readable from configs
                config_kwargs = {k: v for k, v in kwargs.items() if k in ("default", "type", "choices", "action")}
                parser._add_config_only(dest, hidden=True, **config_kwargs)
            return None
        if target is self:
            action = super().add_argument(*args, **kwargs)
        else:
            action = target.add_argument(*args, **kwargs)
        if transient:
            parser._transients.add(action.dest)
        return action

    def _add_section(self, parent, args, kwargs, magi):
        """Create a config section for a config=True, ConfigObject, or typed ConfigObject argument (or a container of them)."""
        kwargs = dict(kwargs)
        typed = kwargs.get("action") == "specify_type"
        if typed:
            kwargs.pop("action")
            if "type" in kwargs:
                raise MagiConfigError("action='specify_type' cannot be combined with type")
        if magi.pop("config", False):
            ctype = MagiConfig
        elif typed:
            ctype = None
        else:
            ctype = kwargs.pop("type")
        container = magi.pop("container", None)
        if container not in (None, list, dict) or container is not None and ctype is MagiConfig:
            raise MagiConfigError("container must be list or dict, and is only supported for ConfigObject args")
        prefix = magi.pop("prefix", True)
        if not prefix and parent is not None:
            raise MagiConfigError("prefix=False is only supported for top-level config args")
        if not prefix and (typed or container is not None):
            raise MagiConfigError("prefix=False is not supported for typed or container args")
        custom = dict(magi.pop("custom", None) or {})
        for key in ("obj", "strict", "src"):
            val = magi.pop(key, None)
            if val is not None:
                if key == "src" and not typed:
                    raise MagiConfigError("src is only supported for typed ConfigObject args (action='specify_type')")
                custom_key = dict(custom[key]) if isinstance(custom.get(key), dict) else {}
                custom_key.update({"disable": False} if val == ASK else {"default": val})
                custom[key] = custom_key
        section_kwargs = dict(
            prefix=prefix,
            description=magi.pop("description", None),
            config_only_help=magi.pop("config_only_help", True),
            typed=typed,
            container=container,
            choices=kwargs.pop("choices", None) if typed else None,
            config_choices=magi.pop("config_choices", None),
            custom=custom,
        )
        if magi:
            raise MagiConfigError(f"Arguments not supported for this config arg: {', '.join(magi)}")
        kwargs.setdefault("help", CONFIG_DEFAULT_HELP)

        if len(args) == 1 and args[0][:1] not in self.prefix_chars:
            dest = args[0]
        else:
            dest = self._get_optional_kwargs(*args, **kwargs)["dest"]
        section = ConfigParser(self, parent, dest, None if container is not None else ctype, **section_kwargs)

        # the argument that reads the config file(s) (preceded by the class for typed args)
        if container is not None:
            section.element_type = ctype
            section.container_default = kwargs.pop("default", None)
            kwargs.update(nargs="+", metavar="CONFIG")
        elif typed:
            kwargs.update(nargs="+", metavar=("TYPE", "CONFIG"))
        else:
            kwargs["type"] = str
        section.config_action = section.config.add_argument(*args, **kwargs)

        self._add_base_args(section, kwargs.get("nargs") if ctype is MagiConfig or not (typed or container) else None)

        known = set(section.base_names())
        if container is None:
            default = section.config_action.default
            if typed and isinstance(default, tuple):
                default = default[0]
            if typed and isinstance(default, type):
                section.ctype = default
            if section.ctype not in (None, MagiConfig):
                self._populate(section, section.ctype)
                known.update(section.ctype._arguments)
        elif ctype is not None:
            known.update(ctype._arguments)
        for key in custom:
            if key not in known:
                warnings.warn(f"{self._ctype_name(ctype)}: unknown argument {key} in custom; ignoring")

        siblings = parent.children if parent is not None else self._config_parsers
        siblings[dest] = section
        if ctype is MagiConfig and self._auto_source:
            self._default_source = section
        return section.config_action

    def _add_base_args(self, section, nargs=None, defaults=None):
        for key in section.base_names():
            base_kwargs = dict(_BASE_ARGUMENTS[key])
            if key == "obj" and nargs is not None:
                base_kwargs["nargs"] = nargs
            base_kwargs = self._customize(section.ctype, key, base_kwargs, section.custom)
            if defaults is not None:
                base_kwargs["default"] = getattr(defaults, key)
            self._add_member(section, section.base, key, base_kwargs)

    def _populate(self, section, ctype):
        """Add the arguments of a ConfigObject class to a section."""
        groups = {}
        for entry in ctype._mutually_exclusive:
            mutex = section.args.add_mutually_exclusive_group(required=entry.get("required", False))
            for name in entry["arguments"]:
                groups[name] = mutex
        for key, arg_kwargs in ctype._arguments.items():
            arg_kwargs = self._customize(ctype, key, dict(arg_kwargs), section.custom)
            self._add_member(section, section.args, key, arg_kwargs, groups.get(key))

    def _add_element(self, container, key, shared):
        """Create the section for one element of a container; its base args default to the container's (shared) values."""
        element = ConfigParser(
            self, container, str(key), container.element_type, typed=container.typed, element=True,
            choices=container.choices, config_choices=container.config_choices, custom=container.custom,
        )
        element.config_action = element.config.add_argument(
            container.flag_prefix + str(key), dest="element",
            nargs="+" if container.typed else "*", metavar=("TYPE", "CONFIG") if container.typed else "CONFIG",
            help=f"element {key} (" + ("class and config files" if container.typed else "config files") + ")",
        )
        self._add_base_args(element, defaults=shared)
        if element.ctype is not None:
            self._populate(element, element.ctype)
        container.children[str(key)] = element
        return element

    @staticmethod
    def _ctype_name(ctype):
        if ctype is MagiConfig:
            return "config"
        return f"ConfigObject {ctype.__name__}" if ctype is not None else "ConfigObject"

    def _customize(self, ctype, key, kwargs, custom):
        """Apply customizations: presence of the key enables the argument; a dict updates its kwargs (except dest)."""
        if key not in custom:
            return kwargs
        kwargs["disable"] = False
        changes = custom[key]
        if isinstance(changes, dict):
            changes = dict(changes)
            if "dest" in changes:
                changes.pop("dest")
                warnings.warn(f"{self._ctype_name(ctype)}: modification of dest is not allowed; discarding this customization for {key}")
            kwargs.update(changes)
        return kwargs

    def _add_member(self, section, parser, key, kwargs, group=None):
        """Add a base argument or ConfigObject argument (key = dest) to a section's parser."""
        magi = {k: kwargs.pop(k) for k in _MAGI_KWARGS if k in kwargs}
        if magi.get("config_only"):
            args = [key]
        else:
            args = [section.flag_prefix + key]
            kwargs["dest"] = key
        if parser is section.args:
            return self._add(section, args, kwargs, magi, group)
        # base parser
        if magi.get("disable"):
            parser._add_disabled(args, kwargs)
        else:
            parser.add_argument(*args, **kwargs)

    def _pre_add_action(self, action):
        super()._pre_add_action(action)
        for option_string in action.option_strings:
            if option_string in self._nested_option_strings:
                raise argparse.ArgumentError(action, f"conflicting option string: {option_string}")

    # removing arguments

    def remove_argument(self, arg, keep=False):
        """Remove a single argument (a missing feature in argparse).

        * arg: flag (for optional arguments, including nested ones and config args), dest (for positional arguments),
          or dotted dest (for config-only arguments)
        * keep: for optional arguments, True removes just the specified flag (and the action only if it has no remaining flags);
          False removes the entire action
        Removing a config arg (without keep) removes its entire config section.
        """
        if arg in self._option_string_actions:
            action = self._option_string_actions.pop(arg)
            action.option_strings.remove(arg)
            if not keep or len(action.option_strings) == 0:
                _remove_action_all(self, action)
            return
        if arg in self._nested_option_strings:
            parser, action = self._nested_option_strings[arg]
            section = next((section for section in self._sections() if section.config_action is action), None)
            if section is not None and (not keep or len(action.option_strings) == 1):
                section.remove()
                return
            self._nested_option_strings.pop(arg)
            parser._option_string_actions.pop(arg)
            action.option_strings.remove(arg)
            if not keep or len(action.option_strings) == 0:
                for option_string in action.option_strings:
                    self._nested_option_strings.pop(option_string)
                _remove_action_all(parser, action)
            return
        positionals = [action for action in self._actions if not action.option_strings and action.dest == arg]
        if positionals:
            for action in positionals:
                _remove_action_all(self, action)
            return
        if arg in self._config_parsers and not self._config_parsers[arg].config_action.option_strings:
            self._config_parsers[arg].remove()
            return
        for section in self._sections():
            for dest in section.args._config_only:
                if (f"{section.ns_path}.{dest}" if section.ns_path else dest) == arg:
                    section.args._config_only.pop(dest)
                    section.args._defaults.pop(dest, None)
                    return
        self.error(f"attempt to remove unrecognized argument: {arg}")

    # parsing

    def _suppress_required(self, actions):
        for action in actions:
            if action.required:
                action.required = False
                self._suppressed.append(action)

    def _restore_required(self, mark=0):
        for action in self._suppressed[mark:]:
            action.required = True
        del self._suppressed[mark:]

    def _expand_abbrevs(self, args):
        """Expand unambiguous abbreviations of long options across this parser and all config sections."""
        option_strings = list(self._option_string_actions) + list(self._nested_option_strings)
        long_prefix = tuple(char * 2 for char in self.prefix_chars)
        # flags under typed or container sections only exist once the class or elements are known
        skip = tuple(section.flag_prefix for section in self._sections() if section.typed or section.container is not None)
        expanded = []
        for iarg, arg in enumerate(args):
            if arg == "--":
                expanded.extend(args[iarg:])
                break
            if arg.startswith(long_prefix) and not arg.startswith(skip):
                option, sep, value = arg.partition("=")
                if option not in option_strings:
                    matches = [option_string for option_string in option_strings if option_string.startswith(option)]
                    if len(matches) == 1:
                        arg = matches[0] + sep + value
                    elif len(matches) > 1:
                        raise argparse.ArgumentError(None, f"ambiguous option: {option} could match {', '.join(matches)}")
            expanded.append(arg)
        return expanded

    def _help_requested(self, args):
        help_strings = {
            option_string for action in self._actions if isinstance(action, (argparse._HelpAction, argparse._VersionAction))
            for option_string in action.option_strings
        }
        for arg in args:
            if arg == "--":
                return False
            if arg in help_strings:
                return True
        return False

    def _make_namespace(self, namespace):
        """MagiConfig, unless this parser has its own arguments (other than help/version/subparsers) and no subparser configs."""
        own_actions = [
            action for action in self._actions
            if not isinstance(action, (argparse._HelpAction, argparse._VersionAction, argparse._SubParsersAction))
        ]
        if not own_actions or not self._config_parsers:
            return _check_namespace(namespace)
        return namespace if namespace is not None else argparse.Namespace()

    def parse_known_args(self, args=None, namespace=None):
        """argparse parse_known_args(); with config args, the config sections are parsed first (in the order added),
        then this parser's own arguments (including subparsers, help, and version)."""
        if not self._has_configs():
            return super().parse_known_args(args, namespace)

        args = sys.argv[1:] if args is None else list(args)
        try:
            if self.fromfile_prefix_chars is not None:
                args = self._read_args_from_files(args)
            if self.allow_abbrev:
                args = self._expand_abbrevs(args)
            namespace = self._make_namespace(namespace)
            suppress_required = self._help_requested(args)
            for cparser in self._config_parsers.values():
                value, source, args = cparser.parse(args, None, suppress_required)
                cparser.attach(namespace, value, source)
            namespace, args = super().parse_known_args(args, namespace)
            for dest in self._transients:
                _mark_transient(namespace, dest)
            return namespace, args
        except argparse.ArgumentError as err:
            if self.exit_on_error:
                self.error(str(err))
            raise

    def parse_known_intermixed_args(self, args=None, namespace=None):
        """argparse parse_known_intermixed_args(); not supported with config args."""
        if self._has_configs():
            raise MagiConfigError("Intermixed parsing is not supported with config args")
        return super().parse_known_intermixed_args(args, namespace)

    # writing

    def write_config(self, namespace, filename, obj="config", separate=False, **write_kwargs):
        """Write a parsed namespace into a config file.

        With separate=True, each top-level config section (with prefix=True) is written to {stem}_{dest}{ext},
        and any remaining attributes to filename (only if there are any).
        Other kwargs are passed to MagiConfig.write().
        """
        if not isinstance(namespace, MagiConfig):
            if type(namespace) is argparse.Namespace:
                raise MagiConfigError("Cannot write plain argparse namespace (maybe from ArgumentParser in mixed mode)")
            raise MagiConfigError(f"Cannot write namespace of unknown type {type(namespace).__name__}")
        if not separate:
            namespace.write(filename, obj, **write_kwargs)
            return

        stem, ext = os.path.splitext(filename)
        opts = _WriteOptions(**write_kwargs)
        rest = MagiConfig()
        rest.join(namespace)
        rest._imported = []
        for cparser in self._config_parsers.values():
            if not cparser.prefix or cparser.dest not in namespace:
                continue
            delattr(rest, cparser.dest)
            rest._transients.discard(cparser.dest)
            rest._sources.pop(cparser.dest, None)
            value = namespace._sources.get(cparser.dest, getattr(namespace, cparser.dest))
            comments = None
            if isinstance(value, tuple):
                # typed: the class is part of the command-line value, so it is recorded in a comment
                cls, value = value
                module = _import_config_paths.get(cls.__module__, cls.__module__)
                comments = [f"# type: {cls.__name__}" + (f" (src: {module})" if module != "__main__" else "")]
            if isinstance(value, MagiConfig):
                imports, lines = value._write(obj, opts)
            elif value is not None:
                imports, expr = _source_expr(value, opts)
                lines = [f"{obj} = {expr}"]
            else:
                continue
            _write_file(f"{stem}_{cparser.dest}{ext}", imports, lines, comments)
        if rest.vars():
            imports, lines = rest._write(obj, opts)
            _write_file(filename, imports, lines)

    # help

    def _get_formatter(self):
        formatter = super()._get_formatter()
        if self._config_parsers:
            formatter.__class__ = _magi_formatter_class(formatter.__class__)
        return formatter

    def _usage_actions(self):
        """Full usage (all actions) for at most one config=True section; otherwise short usage (config args only)."""
        sections = list(self._sections())
        full = len(sections) <= 1 and all(section.ctype is MagiConfig for section in sections)
        actions = list(self._actions)
        groups = list(self._mutually_exclusive_groups)
        for cparser in self._config_parsers.values():
            actions.extend(cparser.config._actions + cparser.base._actions)
            if full:
                actions.extend(cparser.args._actions)
                groups.extend(cparser.args._mutually_exclusive_groups)
        return actions, groups

    def format_usage(self):
        """argparse format_usage(), including config args (see _usage_actions)."""
        if not self._config_parsers:
            return super().format_usage()
        formatter = self._get_formatter()
        formatter.add_usage(self.usage, *self._usage_actions())
        return formatter.format_help()

    def format_help(self):
        """argparse format_help(), followed by one section per config section (nested sections indented)."""
        if not self._config_parsers:
            return super().format_help()
        formatter = self._get_formatter()
        formatter.add_usage(self.usage, *self._usage_actions())
        formatter.add_text(self.description)

        # with help_depth=0, top-level config args are listed with this parser's own arguments
        extra = []
        if self.help_depth == 0:
            extra = [action for cparser in self._config_parsers.values() for action in cparser.config._actions + cparser.base._actions]

        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            actions = list(action_group._group_actions)
            if action_group is self._optionals:
                actions.extend(action for action in extra if action.option_strings)
            elif action_group is self._positionals:
                actions.extend(action for action in extra if not action.option_strings)
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(actions)
            formatter.end_section()

        if self.help_depth != 0:
            for cparser in self._config_parsers.values():
                cparser.format_help(formatter, 1, self.help_depth)

        formatter.add_text(self.epilog)
        return formatter.format_help()


class DictAction(argparse.Action):
    """Collect KEY=VALUE pairs into a dict; repeated use merges into (a copy of) the existing value.

    Extra kwargs for add_argument():
    * key_type, value_type: conversions for keys and values (None = keep strings)
    * dict_type: callable that returns an empty dict (e.g. OrderedDict, or lambda: defaultdict(list))
    * sep: separator between key and value
    Subclasses can override parse_params() to interpret the command-line tokens differently.
    Dicts provided by configs are converted with the same key and value types.
    """
    def __init__(self, option_strings, dest, nargs="*", key_type=str, value_type=None, dict_type=dict, sep="=", **kwargs):
        self.key_type = key_type
        self.value_type = value_type
        self.dict_type = dict_type
        self.sep = sep
        kwargs.setdefault("metavar", f"KEY{sep}VALUE")
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)

    def parse_params(self, values):
        """(key, value) pairs from the command-line tokens."""
        for token in values:
            key, sep, value = token.partition(self.sep)
            if not sep:
                raise argparse.ArgumentError(self, f"expected KEY{self.sep}VALUE: {token!r}")
            yield key, value

    def convert(self, pairs):
        result = self.dict_type()
        for key, value in pairs:
            try:
                if self.key_type is not None:
                    key = self.key_type(key)
                if self.value_type is not None:
                    value = self.value_type(value)
            except (TypeError, ValueError):
                raise argparse.ArgumentError(self, f"invalid entry: {key!r}: {value!r}") from None
            result[key] = value
        return result

    def __call__(self, parser, namespace, values, option_string=None):
        result = self.dict_type()
        current = getattr(namespace, self.dest, None)
        if current is not None:
            result.update(current)
        result.update(self.convert(self.parse_params(values)))
        setattr(namespace, self.dest, result)

    def from_config(self, value):
        return self.convert(value.items())


def shared(**specs):
    """A set of arguments (add_argument kwargs by name) that can be shared between functions via arguments(_parents=...)."""
    return type("Shared", (ConfigObject,), dict(_arguments=specs))


def arguments(_parents=(), **specs):
    """Decorator that attaches a proxy ConfigObject for the function as fn.Config.

    The arguments are the merged _arguments of the parents (e.g. from shared()), updated with specs
    (add_argument kwargs by name). The function itself is unchanged.
    """
    def decorator(fn):
        merged = {}
        for parent in _parents:
            merged.update(parent._arguments)
        merged.update(specs)
        fn.Config = type(fn.__name__, (ConfigObject,), dict(
            _arguments=merged,
            _description=fn.__doc__ or "",
            _principal=staticmethod(fn),
            __module__=fn.__module__,
            __qualname__=f"{fn.__qualname__}.Config",
        ))
        return fn
    return decorator


def app(**parser_kwargs):
    """Decorator (applied outside arguments()) that makes the function a command-line application.

    Attaches fn.parser (an ArgumentParser with -C/--config for the function's arguments)
    and fn.main(argv=None), which parses the arguments and calls the function with them.
    Run it explicitly, e.g.: if __name__ == "__main__": fn.main()
    """
    def decorator(fn):
        if not hasattr(fn, "Config"):
            arguments()(fn)
        parser_kwargs.setdefault("description", fn.__doc__)
        parser = ArgumentParser(**parser_kwargs)
        parser.add_argument("-C", "--config", type=fn.Config, prefix=False, obj=ASK, description=argparse.SUPPRESS)
        fn.parser = parser

        def main(argv=None):
            return fn.Config._build_impl(parser.parse_args(argv))
        fn.main = main
        return fn
    return decorator


def main(argv=None):
    """Config printer: print (or write) the fully expanded MagiConfig object(s) defined in a config file.

    The output is itself a valid config file.
    """
    parser = argparse.ArgumentParser(prog="magiconfig", description=main.__doc__.split("\n")[0])
    parser.add_argument("config", help="config file")
    parser.add_argument("-o", "--obj", nargs="+", help="name(s) of the object(s) to print (dotted names allowed; default: all top-level MagiConfig objects)")
    parser.add_argument("--write", metavar="FILE", help="write to this file instead of printing")
    args = parser.parse_args(argv)

    if args.obj:
        objects = list(zip(args.obj, import_config(args.config, args.obj)))
    else:
        # definition order; MagiConfigs imported into the file are part of its namespace
        objects = [
            (name, value) for name, value in vars(import_config(args.config)).items()
            if not name.startswith("_") and isinstance(value, MagiConfig)
        ]

    opts = _WriteOptions()
    imports = set()
    blocks = []
    defined = set()
    printed = {}
    for name, value in objects:
        lines = []
        # intermediate objects for dotted names
        parts = name.split(".")
        for i in range(1, len(parts)):
            prefix = ".".join(parts[:i])
            if prefix not in defined:
                lines.append(f"{prefix} = MagiConfig()")
                defined.add(prefix)
        if id(value) in printed:
            lines.append(f"{name} = {printed[id(value)]}")
        elif isinstance(value, MagiConfig):
            def record(config, path):
                printed.setdefault(id(config), path)
                for attr, val in config.vars().items():
                    if isinstance(val, MagiConfig):
                        record(val, f"{path}.{attr}")
            record(value, name)
            imports_tmp, lines_tmp = value._write(name, opts)
            imports.update(imports_tmp)
            lines.extend(lines_tmp)
        else:
            imports_tmp, expr = opts.value_expr(name, name, value)
            imports.update(imports_tmp)
            lines.append(f"{name} = {expr}")
        defined.add(name)
        blocks.append("\n".join(lines))

    text = _format_file(imports, ["\n\n".join(blocks)]) + "\n"
    if args.write:
        with open(args.write, "w") as outfile:
            outfile.write(text)
    else:
        sys.stdout.write(text)


# add all public classes and constants from argparse namespace to this namespace to be interchangeable
# (from ConfigArgParse)
Action = argparse.Action
ArgumentDefaultsHelpFormatter = argparse.ArgumentDefaultsHelpFormatter
ArgumentError = argparse.ArgumentError
ArgumentTypeError = argparse.ArgumentTypeError
BooleanOptionalAction = argparse.BooleanOptionalAction
FileType = argparse.FileType
HelpFormatter = argparse.HelpFormatter
MetavarTypeHelpFormatter = argparse.MetavarTypeHelpFormatter
Namespace = argparse.Namespace
ONE_OR_MORE = argparse.ONE_OR_MORE
OPTIONAL = argparse.OPTIONAL
PARSER = argparse.PARSER
REMAINDER = argparse.REMAINDER
RawDescriptionHelpFormatter = argparse.RawDescriptionHelpFormatter
RawTextHelpFormatter = argparse.RawTextHelpFormatter
SUPPRESS = argparse.SUPPRESS
ZERO_OR_MORE = argparse.ZERO_OR_MORE


# convenience definition
# (from ConfigArgParse)
class ArgumentDefaultsRawHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawTextHelpFormatter,
    argparse.RawDescriptionHelpFormatter):
    """HelpFormatter that adds default values AND doesn't do line-wrapping"""


if __name__ == "__main__":
    # run from the "magiconfig" module (not this "__main__" copy), so classes match those used by config files
    import magiconfig
    magiconfig.main()
