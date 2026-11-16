# magiconfig

Configure Python with Python.

Table of Contents
=================
* [Overview](#overview)
* [Philosophy](#philosophy)
* [Installation](#installation)
* [Quick start](#quick-start)
* [Concepts](#concepts)
   * [Parse order and hierarchy](#parse-order-and-hierarchy)
   * [Precedence](#precedence)
   * [Prefixes and namespaces](#prefixes-and-namespaces)
   * [Special kinds of arguments](#special-kinds-of-arguments)
   * [Imported files](#imported-files)
* [Features](#features)
   * [ArgumentParser](#argumentparser)
      * [Constructor](#constructor)
      * [add_argument()](#add_argument)
      * [parse_args(), parse_known_args()](#parse_args-parse_known_args)
      * [set_default_source(source), clear_default_source()](#set_default_sourcesource-clear_default_source)
      * [add_mutually_exclusive_group(source=None, **kwargs)](#add_mutually_exclusive_groupsourcenone-kwargs)
      * [write_config(namespace, filename, obj="config", separate=False, **write_kwargs)](#write_confignamespace-filename-objconfig-separatefalse-write_kwargs)
      * [remove_argument(arg, keep=False)](#remove_argumentarg-keepfalse)
   * [Composable configs](#composable-configs)
   * [ConfigObject](#configobject)
      * [Defining a ConfigObject](#defining-a-configobject)
      * [build(config, obj="config", strict=False)](#buildconfig-objconfig-strictfalse)
      * [ConfigObject arguments](#configobject-arguments)
      * [Proxies and inheritance](#proxies-and-inheritance)
      * [Typed ConfigObject arguments](#typed-configobject-arguments)
      * [Containers of ConfigObjects](#containers-of-configobjects)
   * [DictAction](#dictaction)
   * [App layer](#app-layer)
   * [MagiConfig](#magiconfig-1)
      * [write(filename, config_obj="config", attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False)](#writefilename-config_objconfig-attr_importsnone-class_importsnone-attr_reprsnone-class_reprsnone-strictfalse)
      * [join(other_config, prefer_other=False)](#joinother_config-prefer_otherfalse)
      * [getattr(), setattr()](#getattr-setattr)
   * [Other functions](#other-functions)
   * [MagiConfigError](#magiconfigerror)
   * [Config printer](#config-printer)
   * [Help and usage](#help-and-usage)
   * [Limitations](#limitations)
   * [Convenience](#convenience)
* [Migrating from v2](#migrating-from-v2)
* [Examples](#examples)
   * [1) Basic setup](#1-basic-setup)
   * [2) Subparsers](#2-subparsers)
   * [3) Config-driven](#3-config-driven)
   * [4) Scaling up](#4-scaling-up)
   * [5) Composable configs](#5-composable-configs)
   * [6) ConfigObjects](#6-configobjects)
   * [7) Proxies and inheritance](#7-proxies-and-inheritance)
   * [8) Typed ConfigObjects and containers](#8-typed-configobjects-and-containers)
   * [9) DictAction and the config printer](#9-dictaction-and-the-config-printer)
   * [10) App layer](#10-app-layer)
* [Development](#development)
* [Inspirations](#inspirations)

## Overview

magiconfig is an extension of argparse that stops the
[configuration complexity clock](https://mikehadlow.blogspot.com/2012/05/configuration-complexity-clock.html)
by enabling users to configure Python with Python.
It provides all the power of Python to manipulate and compose configuration parameters,
bypassing the limitations of text-based configuration languages.

## Philosophy

This module treats argparse as an engine that ultimately provides a namespace of attributes ("dests") to be consumed by user applications.
With magiconfig, these attributes can be provided by imported [`MagiConfig`](#magiconfig-1) Python objects,
in addition to the usual command-line arguments.
Everything is routed through the existing argparse interface (constructor, `add_argument()`, etc.),
with a few additional keyword arguments for magiconfig-specific features.

Beyond single scripts, magiconfig scales up to full applications:
* several config files can be composed on the command line, each providing a different set of arguments ([composable configs](#composable-configs));
* complex objects can be configured on the command line and in config files without writing complex parser actions ([`ConfigObject`](#configobject)),
  and can also be built directly from a config file without any command-line parsing.

## Installation

```
pip install magiconfig
```

magiconfig is a single-file package with no dependencies outside of the Python standard library. It requires Python 3.9 or newer.

## Quick start

```python
from magiconfig import ArgumentParser

parser = ArgumentParser(basic=True)
parser.add_argument("-f", "--foo", type=str, default="lorem", help="foo arg")
parser.add_argument("-b", "--bar", type=float, required=True, help="bar arg")
args = parser.parse_args()
print(args)
parser.write_config(args, "config_out.py")
```

A config file is just Python:
```python
from magiconfig import MagiConfig

config = MagiConfig()
config.bar = 3.0
```

Values can come from the config file (`-C config.py`), the command line (`--foo foo`), or the defaults.
The final namespace can be written into a new config file, which reproduces the same result when passed back with `-C config_out.py`.
See [Example 1](#1-basic-setup).

## Concepts

### Parse order and hierarchy

Each config argument (`config=True`) or ConfigObject argument (`type=SomeConfigObject`) creates a config section,
which has its own internal parsers. The sections are parsed in a fixed hierarchical order:
```
ArgumentParser
    config sections (in the order added)
        ConfigParser
            base: obj, strict, src
            config: the config argument itself
            args: the section's arguments
                nested config sections
                    ConfigParser
                        ...
        ConfigParser
            ...
    the top-level parser's own arguments (including subparsers, help, and version)
```
Each section reads its config file(s) and then its own command-line arguments.
The top-level parser is parsed last, so help and version always work, even if required arguments in a config section are missing.
If there are no config arguments, the parser is just argparse.

### Precedence

The precedence of parameter values is: command line > config file > defaults.

With nested sections, a config file given on the command line for a nested section takes precedence over the value
(a file name or an inline `MagiConfig`) that its parent config provides:
command-line flag > command-line config file > parent config file > defaults.
The precedence follows from the hierarchy, not from the order on the command line:
`--foo 1 -A config.py` and `-A config.py --foo 1` give the same result.

### Prefixes and namespaces

By default, each config section is stored in the namespace under its dest (e.g. `args.A.foo`),
and the flags generated by magiconfig (base arguments and ConfigObject arguments) are prefixed with the section's path (e.g. `--A.obj`, `--model.depth`).
Arguments added to a config section with `source` keep the flags that are given for them (e.g. `--foo`).

With `prefix=False` (only for top-level config arguments), the section's values are merged into the top-level namespace,
and the generated flags are not prefixed (e.g. `--obj`).
This is the "basic" mode (`ArgumentParser(basic=True)`), which reproduces the behavior of magiconfig v2.

The result of `parse_args()` is a [`MagiConfig`](#magiconfig-1) if the top-level parser has no arguments of its own (other than help and version),
or if any subparser has config arguments.
Otherwise (mixed mode), it is a plain `argparse.Namespace` (which may contain `MagiConfig` sections); this cannot be written with `write_config()`.

### Special kinds of arguments

* config-only (`config_only=True`): only provided by configs, not by the command line. Defaults populate the namespace; types and choices are checked.
* transient (`transient=True`): used only for the current run. Transient arguments are never written to config files and never read from them
  (a transient dest in a config file is treated as an unknown attribute: ignored, or an error in strict mode).
* disabled (`disable=True`): not shown in the help and not accepted on the command line, but the default populates the namespace
  (and, in a config section, it can still be set by configs). This is how the base arguments (`obj`, `strict`, `src`) are disabled until requested.

### Imported files

The config files that were loaded for each section are recorded, in load order,
and returned by `magiconfig.imported(section)` as a list of `(path, obj)` tuples (an inline `MagiConfig` from a parent config has path `None`).
For merged sections (`prefix=False`), the files are recorded in the namespace that receives the values.
Written config files list them as comments, e.g. `# imported from: examples/config1.py (obj: config)`.

## Features

magiconfig provides a custom [`ArgumentParser`](#argumentparser) class, which is a drop-in replacement for `argparse.ArgumentParser`.
It also provides the [`MagiConfig`](#magiconfig-1), [`ConfigObject`](#configobject), [`DictAction`](#dictaction), and [`MagiConfigError`](#magiconfigerror) classes,
the [app layer](#app-layer) decorators, and a [config printer](#config-printer).

### ArgumentParser

The API of this class is extended with several additional keyword arguments and functions to manage configs, as well as to provide other useful operations.

#### Constructor

The constructor supports several additional options:
* `basic`: add a config argument `-C/--config` with `prefix=False` and use it as the default source for subsequent arguments; default = `False`
* `auto_source`: each new `config=True` argument becomes the default source for subsequent arguments; default = `False`
* `help_depth`: number of levels of config sections to show in the help message (see [Help and usage](#help-and-usage)); default = `None` (all)

The `parents` argument also copies the config sections of magiconfig parents.

#### `add_argument()`

The interface is unchanged from argparse, with these additional keyword arguments:

| kwarg | applies to | meaning |
|---|---|---|
| `config=True` | config args | the argument is a config file (or files, with `nargs`); creates a config section |
| `type=SomeConfigObject` | ConfigObject args | creates a config section for a [ConfigObject](#configobject-arguments) |
| `action="specify_type"` | typed ConfigObject args | the ConfigObject class is chosen on the command line ([typed](#typed-configobject-arguments)) |
| `container=list` or `dict` | ConfigObject args | a [container](#containers-of-configobjects) of ConfigObjects |
| `source="A"` | any arg | add the argument to a config section: a full dotted path (`"A.sub"`) or a unique dest |
| `obj`, `strict`, `src` | config/ConfigObject args | `ASK` enables the corresponding base argument (`--A.obj`, `--A.strict`/`--A.no-strict`, `--A.src`); any other value sets its default |
| `custom={key: True or dict}` | config/ConfigObject args | enable (`True`) or modify (`dict` of kwargs) a base argument or ConfigObject argument; changing `dest` is not allowed |
| `prefix=False` | top-level config/ConfigObject args | merge into the parent namespace and do not prefix generated flags |
| `description="..."` | config/ConfigObject args | text for the section in the help message |
| `config_only_help=False` | config/ConfigObject args | omit config-only arguments from the help message |
| `config_choices=[...]` | typed ConfigObject args | allowed config file values |
| `config_only=True` | args in a section | provided only by configs (supported kwargs: `default`, `type`, `choices`, `required`, `help`, `action`) |
| `transient=True` | any arg | never written to or read from configs |
| `disable=True` | any arg | not shown or accepted on the command line; the default populates the namespace |

The base arguments of each section are:
* `obj`: name of the object to import from each config file (default: `"config"`); with `nargs`, the same number of objects as config files, or one for all
* `strict`: reject imported configs with unknown attributes (default: `False`)
* `src`: for typed ConfigObject args only: module or file (`.py`) that defines the class (default: `None`)

`nargs` on a config argument means multiple config files, joined in order (later files take precedence).

Positional arguments are only allowed in the top-level parser.
A positional config argument must come before any option flags on the command line.

#### `parse_args(), parse_known_args()`

These function interfaces are unchanged from argparse.
They return a [`MagiConfig`](#magiconfig-1) object (or a plain `argparse.Namespace` in mixed mode, see [Prefixes and namespaces](#prefixes-and-namespaces)).
If an input `namespace` argument is provided but is not of type [`MagiConfig`](#magiconfig-1), a conversion will be attempted.

Abbreviations of long options (`allow_abbrev`) are resolved across all config sections.
Intermixed parsing (`parse_intermixed_args()`) is not supported when there are config arguments.

#### `set_default_source(source), clear_default_source()`

These functions set (or clear) the config section to which subsequent arguments are added if they have no `source`.
`config=True` arguments always create top-level sections; ConfigObject arguments are nested in the default source.

#### `add_mutually_exclusive_group(source=None, **kwargs)`

With `source`, the mutually exclusive group is created in that config section.
Mutual exclusion is only enforced for command-line values, not for config values.

#### `write_config(namespace, filename, obj="config", separate=False, **write_kwargs)`

* `namespace`: [`MagiConfig`](#magiconfig-1) object to be written
* `filename`: name of file to write
* `obj`: name of the [`MagiConfig`](#magiconfig-1) object in the file
* `separate`: write each top-level config section (with a prefix) to a separate file `{stem}_{dest}{ext}`, so the result can be reproduced with e.g. `-A out_A.py -B out_B.py`;
  any remaining attributes are written to `filename` (only if there are any)
* `write_kwargs`: passed to [`MagiConfig.write()`](#writefilename-config_objconfig-attr_importsnone-class_importsnone-attr_reprsnone-class_reprsnone-strictfalse)

This function can be used to preserve the state of the configuration after any command-line modifications (see [Example 1](#1-basic-setup)).
Raises [`MagiConfigError`](#magiconfigerror) for a plain `argparse.Namespace` (mixed mode).

#### `remove_argument(arg, keep=False)`

This function allows removing a single argument (a missing feature in argparse).

* `arg`: flag (for optional arguments, including arguments in config sections), dest (for positional arguments), or dotted dest (for config-only arguments, e.g. `"config.x"`, or just `"x"` with `prefix=False`)
* `keep`: for optional arguments, `True` will remove just the single specified flag `arg` (the entire action is removed only if it has no remaining flags); `False` (default) always removes the action associated with the flag
* removing a config argument removes its entire config section

Exits with `error()` if an unknown argument is provided.

### Composable configs

Multiple config arguments can be used, with different arguments coming from different configs.
This allows composing different sets of arguments that can be shared between different functions, scripts, etc.:
```
python3 test.py -A config1.py --foo 1 -B config2.py --bar a
```
Here, `foo` is an argument added with `source="A"` and `bar` is an argument added with `source="B"`.
Config sections can also be nested: a `config=True` argument added with `source="A"` creates the section `A.sub` (if its dest is `sub`),
which a parent config can provide as a file name or an inline `MagiConfig` (`config.sub = "sub.py"` or `config.sub = MagiConfig(...)`).
See [Example 5](#5-composable-configs).

### ConfigObject

A ConfigObject is a class whose inputs are specified as a "virtual" parser.
The object itself can be added to an [`ArgumentParser`](#argumentparser) as a single argument,
which automatically expands to provide arguments for all the fields that it needs.
These can be obtained from a config file or the command line, just as any other arguments in magiconfig.

#### Defining a ConfigObject

```python
from magiconfig import ConfigObject

class Model(ConfigObject):
    """Extra documentation."""
    _description = "model settings"
    _arguments = dict(
        layers = dict(type=int, default=2, help="number of layers"),
        optimizer = dict(type=Optimizer, help="optimizer config"),
    )
    _mutually_exclusive = [dict(arguments=["a", "b"], required=False)]
    _principal = None
```

* `_arguments`: each key is the dest and the flag name (`--{prefix}{key}`); each value is a dict of `add_argument()` kwargs.
  ConfigObject arguments are always optional arguments. A value can be another ConfigObject (nested).
* `_description`: text for the help section and the docstring
* `_mutually_exclusive`: groups of mutually exclusive arguments
* `_principal`: a callable that takes the arguments as keyword arguments, built instead of the class itself ([proxy](#proxies-and-inheritance))

The class docstring is generated automatically from `_description`, the class's own docstring, and the arguments' types, defaults, and help messages,
so it works with `help()` and documentation tools.
The default constructor sets the arguments as attributes; `repr()` shows them as a `MagiConfig`.

#### `build(config, obj="config", strict=False)`

This class method builds an instance directly from a config (a file name or a `MagiConfig`), without any command-line parsing
(e.g. a colleague provides a config file and you just want to create the object).
Defaults, types, choices, required arguments, and strictness are applied as on the command line; errors are raised as exceptions.

The class method `_build_impl(source)` constructs the object from the parsed `MagiConfig`, keeping only the attributes in `_arguments`;
it can be overridden to customize construction.

#### ConfigObject arguments

```python
parser.add_argument("-M", "--model", type=Model, help="model config")
```
gives `-M/--model` (the config file), `--model.layers`, `--model.optimizer` (a config file for the nested object), `--model.optimizer.name`, etc.
The parsed value is the built object. Use `custom` to enable or modify arguments without changing the class (e.g. `custom=dict(obj=True, layers=dict(default=4))`).
When written with `write_config()`, a ConfigObject is written as the `MagiConfig` it was built from, so the written file can be read back.
See [Example 6](#6-configobjects).

#### Proxies and inheritance

Existing classes can be "converted" to ConfigObjects by creating a proxy ConfigObject with the arguments and `_principal = ExistingClass`.
The argument list can be extended or modified by inheritance:
```python
class ColoredRectangleConfig(RectangleConfig):
    _arguments = RectangleConfig._arguments | dict(color = dict(default="red", help="color"))
```
An argument can be removed with a dict comprehension, e.g. `{k: v for k, v in Parent._arguments.items() if k != "color"}`.
See [Example 7](#7-proxies-and-inheritance).

#### Typed ConfigObject arguments

With `action="specify_type"`, the class is chosen on the command line, followed by optional config files:
```python
parser.add_argument("-M", "--model", action="specify_type", default=ResNet, choices=[ResNet, VGG], help="model class and config file")
```
```
python script.py --model VGG                           # class only: defaults + sub-flags
python script.py --model VGG vgg.py --model.depth 16   # class + config file
```
* Any ConfigObject class is allowed (no common base class is needed); `choices` (classes or names) restricts it, and `config_choices` restricts the config files.
* Class names are resolved with the `src` base argument (a module name, or a file ending in `.py`) if given, then by name in `choices`,
  then in a registry of all ConfigObject subclasses (a name defined in more than one module is an error that suggests using `src`).
* In a parent config, the value mirrors the command line: `config.backbone = VGG` (or `"VGG"`), `(VGG, "vgg.py")`, `(VGG, MagiConfig(depth=16))`, or `MagiConfig(depth=16)` with the default class.
* The command line replaces the parent config's value (class and config files); sub-flags apply in every case.
* With no class from any source, the value is `None` (or an error if `required=True`).
* The help message shows the arguments of the resolved class.
* Written configs contain the class with its config: `config.backbone = (VGG, MagiConfig(depth=16))`.
  Classes are imported from their module, loaded with `import_config()` if they came from a file, or written by name if they are defined in the script (`__main__`).
  A top-level typed argument written with `separate=True` gets a `# type: VGG (src: module)` comment, since the class is part of the command-line value.

#### Containers of ConfigObjects

`container=list` or `container=dict` turns a ConfigObject argument (with `type=SomeConfigObject` or `action="specify_type"`) into a container:
```python
parser.add_argument("--layers", type=Layer, container=list, help="layer configs")
parser.add_argument("--layers", action="specify_type", container=dict, choices=[Conv, Dense], help="layers")
```
```
python script.py --layers layers.py                                  # whole container from a config file
python script.py --layers layers.py --layers.1 Dense dense.py        # replace (or add) one element
python script.py --layers.enc Conv conv.py --layers.dec Dense --layers.dec.units 64   # built from elements only
python script.py --layers.0 --layers.0.dim 10 --layers.1 --layers.1.dim 5            # one class, no config files
```
* `--layers CONFIG [CONFIG ...]`: container config files, whose object is the whole list or dict (several files are joined by index or key).
* `--layers.<index|key> VALUE`: creates or replaces one element: `[CONFIG ...]` for one class, or `TYPE [CONFIG ...]` for `specify_type`.
  List indices must be existing or the next index (appending); a new dict key adds an element.
* `--layers.<index|key>.<arg>`: an argument of that element. These never create an element on their own.
* Element values (in container config files, parent configs, or `default`) have the same forms as single (typed) ConfigObject values,
  e.g. `[Conv, (Dense, "dense.py"), (Conv, MagiConfig(kernel=5))]`.
* The base arguments are shared (`--layers.src`) with per-element overrides (`--layers.1.src`).
* Dict keys must be non-empty strings without `.`, and cannot be `obj`, `strict`, or `src`.
* Precedence: element sub-flags > element flag > container flag > parent config > default.

See [Example 8](#8-typed-configobjects-and-containers).

### DictAction

An argparse action that collects `KEY=VALUE` tokens into a dict (repeated use merges into a copy of the existing value).
Extra `add_argument()` kwargs: `key_type` (default: `str`), `value_type` (default: `None`, keep strings), `dict_type` (a callable returning an empty dict, e.g. `OrderedDict` or `lambda: defaultdict(list)`), `sep` (default: `"="`).
Dicts provided by configs are converted with the same types.
Subclasses can override `parse_params(values)` to interpret the tokens differently (returning `(key, value)` pairs).

### App layer

Functions can be turned into command-line applications with decorators:
```python
import magiconfig

common = magiconfig.shared(verbose = dict(action="store_true", help="verbose output"))

@magiconfig.app()
@magiconfig.arguments(_parents=[common], name = dict(default="world", help="who to greet"))
def greet(name, verbose):
    """Greet someone."""

if __name__=="__main__":
    greet.main()
```
* `arguments(_parents=(), **specs)` attaches a proxy ConfigObject for the function as `fn.Config` (the function itself is unchanged).
* `shared(**specs)` creates a set of arguments that can be shared between functions via `_parents`.
* `app(**parser_kwargs)` attaches `fn.parser` (an `ArgumentParser` with `-C/--config` and `--obj` for the function's arguments) and `fn.main(argv=None)`, which parses the arguments and calls the function.

See [Example 10](#10-app-layer).

### MagiConfig

This class extends `argparse.Namespace` to add a few useful methods.
It is used both as the input object in config files and as the output object of [`ArgumentParser`](#argumentparser).

#### `write(filename, config_obj="config", attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False)`

* `filename`: name of file to write
* `config_obj`: name of [`MagiConfig`](#magiconfig-1) object in file
* `attr_imports`: dictionary with key = attribute name, value = function returning a string of `import` statements
* `class_imports`: dictionary with key = class type, value = function returning a string of `import` statements
* `attr_reprs`: dictionary with key = attribute name, value = function returning a `repr`-style string
* `class_reprs`: dictionary with key = class type, value = function returning a `repr`-style string
* `strict`: for each attribute, check if calling `eval()` on the `repr`-style string returns the original value

By default, the class module and name of each entry in the configuration are used to determine if import statements are needed,
and `repr()` is used to provide a representation of the entry from which it can be reconstructed.
(If an entry is a `Collection` or `Mapping` type, its entries are also inspected for imports. For other `Container` types, their entries are inspected if they can be obtained via `vars()`.)
If these defaults are not correct for a given entry or a given class type, they can be overridden by providing custom functions using the options
`attr_imports`, `class_imports`, `attr_reprs`, `class_reprs` as described above.
The order of precedence is: `attr_* > class_* > default`.
Class objects (also inside tuples, lists, and dicts) are written as imports.
Transient attributes are not written.

#### `join(other_config, prefer_other=False)`

* `other_config`: other [`MagiConfig`](#magiconfig-1) object to merge
* `prefer_other`: prefer values from other config, if dest is present in both configs (default: prefer this config)

#### `getattr()`, `setattr()`

These class methods are extended to handle nested config objects automatically.
Any nonexistent intermediate objects are initialized as [`MagiConfig`](#magiconfig-1) instances. Example:
```python
from magiconfig import MagiConfig
x = MagiConfig()
setattr(x,"y.z","test")
print(x)
```
returns: `MagiConfig(y=MagiConfig(z='test'))`

This enables obtaining dests from nested configs by using dots in the dest names.

`vars(transient=False)` returns the attributes as a dict (including transient attributes only if requested).
(A dest named `vars` would shadow this method.)

### Other functions

* `import_config(file_path, attrs=None)`: import a Python file and return the requested attribute(s) (a dotted name, a list of names, or `None` for the module itself).
  Each file is executed once per process (and again only if it changes), so repeated imports return the same objects.
* `imported(config)`: the config files that were imported for a section (see [Imported files](#imported-files)).

### MagiConfigError

This class derives from `Exception` and denotes magiconfig-specific errors.

### Config printer

The config printer "expands" and fully displays a config file that contains complex logic (e.g. populated via for loops):
```
python -m magiconfig CONFIG [-o OBJ [OBJ ...]] [--write FILE]
```
(also available as the `magiconfig` command).
With `-o`, it prints the named objects (dotted names are allowed); otherwise, it prints all top-level `MagiConfig` objects in the file, in definition order
(including `MagiConfig` objects imported into the file from elsewhere; names starting with `_` are skipped).
An object that is the same instance as one printed earlier is printed as a reference (`b = a`).
The output is itself a valid config file. See [Example 9](#9-dictaction-and-the-config-printer).

### Help and usage

The help message shows the top-level parser's own arguments (and argument groups), then one section per config section,
titled with its dotted path, with the section's description (or the ConfigObject's `_description`), its config argument, enabled base arguments, and arguments,
followed by its config-only arguments and its nested sections (indented).
`help_depth=0` shows only the top-level config arguments (with the other options); `help_depth=n` shows sections down to nesting level `n`.

The usage message shows all arguments if there is at most one config section and no ConfigObject arguments;
otherwise, it shows the top-level arguments and the top-level config arguments with their enabled base arguments.

Argument groups (`add_argument_group()`) are only supported in the top-level parser, for its own arguments:
argument groups are a limited way of organizing help messages that does not support nesting, and magiconfig already organizes the help message by config section.

### Limitations

* Positional arguments are only allowed in the top-level parser, and a positional config argument must come before any option flags.
  Similarly, a typed argument (`--model TYPE [CONFIG ...]`) consumes the following non-option tokens, so a positional value must not directly follow it.
* Mutual exclusion is only enforced for command-line values, not for config values.
* Intermixed parsing is not supported with config arguments.
* `prefix=False` is only supported for top-level config and ConfigObject arguments (not typed or containers); a ConfigObject with `prefix=False` provides its fields rather than a built object.
* Abbreviations are not expanded for flags of typed and container sections (these flags only exist once the class or elements are known).

### Convenience

All public classes and constants from argparse are added to the magiconfig namespace for easier drop-in usage.

A class `ArgumentDefaultsRawHelpFormatter` is defined to present help messages with default values and without line wrapping (from [ConfigArgParse](https://github.com/bw2/ConfigArgParse)).

## Migrating from v2

magiconfig v3 is a clean break from v2: the v2-specific interfaces were removed in favor of additional `add_argument()` kwargs.

| v2 | v3 |
|---|---|
| `ArgumentParser(config_options=MagiConfigOptions())` | `ArgumentParser(basic=True)` |
| `MagiConfigOptions(args=["-c"], ...)` | `add_argument("-c", config=True, prefix=False, ...)` + `set_default_source("c")` |
| `MagiConfigOptions(help=..., required=..., default=..., dest=...)` | the corresponding `add_argument()` kwargs of the config argument |
| `MagiConfigOptions(obj="cfg")` | `obj="cfg"` |
| `MagiConfigOptions(obj_args=["--obj"])` | `obj=ASK` (gives `--obj` with `prefix=False`) |
| `MagiConfigOptions(strict=True)` | `strict=True` |
| `MagiConfigOptions(strict_args=["--strict"])` | `strict=ASK` (gives `--strict`/`--no-strict` with `prefix=False`) |
| `obj_help`, `strict_help`, etc. | `custom=dict(obj=dict(help=...))` |
| `set_config_options()`, `copy_config_options()`, `remove_config_options()` | `remove_argument("-C")` and `add_argument(..., config=True)` |
| `add_config_argument(arg, **kwargs)` | `add_argument(arg, config_only=True, **kwargs)` |
| `remove_config_argument(arg)` | `remove_argument(arg)` |
| `parse_config()` | internal (`_parse_config()`) |
| `ArgumentParser(config_only_help=False)` | `config_only_help=False` on the config argument |

Other changes:
* The default help message for config arguments is "name of config file to import".
* With `basic=True`, the config arguments are shown in a `config:` section of the help message.
* Defaults of config-only arguments populate the namespace, and their types and choices are checked.
* Choices are checked for config values even without a `type`.
* Argument groups are only supported for top-level (non-config) arguments.
* Written config files list the imported config files as comments.

## Examples

The commands below are run from the base directory of the repository.
The help output shown is from Python 3.9; newer versions of argparse format it slightly differently.

### 1) Basic setup

The simple script in [examples/example1.py](./examples/example1.py)
demonstrates the different ways to set values, as well as some of the features of magiconfig.

The help printout for the arguments defined in the script:
```
> python examples/example1.py -h
usage: example1.py [-h] [-C CONFIG] [-f FOO] -b BAR [-i]

optional arguments:
  -h, --help            show this help message and exit

config:
  -C CONFIG, --config CONFIG
                        name of config file to import
  -f FOO, --foo FOO     foo arg
  -b BAR, --bar BAR     bar arg
  -i, --ipsum           ipsum arg
```

When the script is run as follows, it prints the resulting namespace:
```
> python examples/example1.py -C examples/config1.py --foo foo
MagiConfig(bar=3.0, foo='foo', ipsum=False)
```

Here, the `bar` argument is set by the config file [examples/config1.py](./examples/config1.py),
the `foo` argument is set on the command line, and the `ipsum` argument retains its default value.

The script also writes the final namespace into a config file `examples/config1_out.py`:
```python
from magiconfig import MagiConfig

# imported from: examples/config1.py (obj: config)
config = MagiConfig()
config.bar = 3.0
config.foo = 'foo'
config.ipsum = False
```

With this config file, the script can be rerun to produce the same output without
the need to specify any other command-line arguments:
```
> python examples/example1.py -C examples/config1_out.py
MagiConfig(bar=3.0, foo='foo', ipsum=False)
```

### 2) Subparsers

The script in [examples/example2.py](./examples/example2.py)
demonstrates how a common config file [examples/config2.py](./examples/config2.py)
can be used with multiple subparsers.

The parser has two modes defined, `one` (with an argument `foo`)
and `two` (with an argument `bar`).
Each subparser mode specifies a different config object;
in this case, each of these config objects is a member of a top-level config object.

The script can be run in each mode with the same input config file:
```
> python examples/example2.py one -C examples/config2.py
MagiConfig(foo='foo')
> python examples/example2.py two -C examples/config2.py
MagiConfig(bar=2.0)
```

### 3) Config-driven

In a config-driven script, it may be desirable to encapsulate many parameters only in the config file,
while supporting only parameters related to running the script as command-line arguments.
The script in [examples/example3.py](./examples/example3.py) is an example.

It shows how an organized schema with different categories and parameters can be defined and transmitted to the parser.
This allows the parser to use strict mode to validate input configurations, rejecting any config with unknown parameters.
The `verbose` argument is transient: it only affects the current run, and is never written to or read from config files.
The config file [examples/config3.py](./examples/config3.py) can be used with the script:
```
> python examples/example3.py -C examples/config3.py -v
MagiConfig(dataset=MagiConfig(path='/data', signal='signal', background='background'), training=MagiConfig(size=0.5, weights=[1, 1]), hyper=MagiConfig(learning_rate=0.1, loss='log'), verbose=True)
```

This example also shows how config-only arguments can be given default values or marked as required. These attributes are reflected in the help message:
```
> python examples/example3.py --help
usage: example3.py [-h] [-C CONFIG] [--strict | --no-strict] [-v]

optional arguments:
  -h, --help            show this help message and exit

config:
  -C CONFIG, --config CONFIG
                        name of config file to import (default: None)
  --strict, --no-strict
                        reject imported config with unknown attributes (default: True)
  -v, --verbose         enable verbose output (default: False)

  config-only arguments:
    dataset.path        (default: /data)
    dataset.signal      (required)
    dataset.background  (required)
    training.size
    training.weights
    hyper.learning_rate
    hyper.loss
```

### 4) Scaling up

When scaling up an application to handle a large number of possible inputs,
a typical pattern is that some of the parameters are common,
while other parameters may be unique to each input.
Rather than requiring a separate config file for each possible input,
all of the config objects can be generated within a single Python file.
The script in [examples/example4.py](./examples/example4.py)
allows the config object name to be specified on the command line (`obj=ASK`);
other config objects in the config file are just ignored.

The help message for this script is:
```
> python examples/example4.py --help
usage: example4.py [-h] [-C CONFIG] [--obj OBJ] [-f FOO] -b BAR -i INPUT

optional arguments:
  -h, --help            show this help message and exit

config:
  -C CONFIG, --config CONFIG
                        name of config file to import (default: None)
  --obj OBJ             name of object to import from config file (default: config)
  -f FOO, --foo FOO     foo arg (default: lorem)
  -b BAR, --bar BAR     bar arg (default: None)
  -i INPUT, --input INPUT
                        input arg (default: None)
```

The script can be run with different inputs all contained in [examples/config4.py](./examples/config4.py):
```
> python examples/example4.py -C examples/config4.py --obj config.a
MagiConfig(input='a', foo='foo', bar=3.0)
> python examples/example4.py -C examples/config4.py --obj config.b
MagiConfig(input='b', foo='foo', bar=3.0)
```

### 5) Composable configs

The script in [examples/example5.py](./examples/example5.py) has two config arguments, `-D/--data` and `-T/--train`,
each with its own set of arguments:
```
> python examples/example5.py --help
usage: example5.py [-h] [-D DATA] [-T TRAIN]

optional arguments:
  -h, --help            show this help message and exit

data:
  -D DATA, --data DATA  data config
  --path PATH           data path
  --signal SIGNAL       signal sample

train:
  -T TRAIN, --train TRAIN
                        training config
  --lr LR               learning rate
  --epochs EPOCHS       number of epochs
```

Different config files ([examples/config5_data.py](./examples/config5_data.py), [examples/config5_train.py](./examples/config5_train.py))
can be combined, along with command-line arguments:
```
> python examples/example5.py -D examples/config5_data.py -T examples/config5_train.py --epochs 20
MagiConfig(data=MagiConfig(signal='signal_v2', path='/data'), train=MagiConfig(lr=0.01, epochs=20))
```

The script writes each section into a separate file (`separate=True`),
`examples/config5_out_data.py` and `examples/config5_out_train.py`, which reproduce the same result:
```
> python examples/example5.py -D examples/config5_out_data.py -T examples/config5_out_train.py
MagiConfig(data=MagiConfig(path='/data', signal='signal_v2'), train=MagiConfig(epochs=20, lr=0.01))
```

### 6) ConfigObjects

The module [examples/models6.py](./examples/models6.py) defines a ConfigObject `Model` that contains another ConfigObject `Optimizer`.
The script in [examples/example6.py](./examples/example6.py) adds it to a parser as a single argument:
```
> python examples/example6.py --help
usage: example6.py [-h] [-M MODEL]

optional arguments:
  -h, --help            show this help message and exit

model:
  model settings

  -M MODEL, --model MODEL
                        model config
  --model.layers LAYERS
                        number of layers

  model.optimizer:
    optimizer settings

    --model.optimizer OPTIMIZER
                        optimizer config
    --model.optimizer.name {sgd,adam}
                        optimizer name
    --model.optimizer.lr LR
                        learning rate
> python examples/example6.py --model.optimizer.name adam --model.layers 4
4 layers, adam optimizer with lr=0.1
```

The script in [examples/example6_build.py](./examples/example6_build.py) builds the object directly from a colleague's config file
[examples/colleague_config.py](./examples/colleague_config.py), without any command-line parsing,
and prints the automatically generated documentation:
```
> python examples/example6_build.py
8 layers, adam optimizer with lr=0.001
model settings

A toy model with a nested optimizer.

Arguments:
    layers (int, default: 2): number of layers
    optimizer (Optimizer): optimizer config
```

### 7) Proxies and inheritance

The script in [examples/example7.py](./examples/example7.py) configures existing classes `Rectangle` and `ColoredRectangle` with proxy ConfigObjects;
the proxy for `ColoredRectangle` extends the arguments of the proxy for `Rectangle`.
In basic mode, the ConfigObjects are written into a single config file `examples/config7_out.py`, which can be read back:
```
> python examples/example7.py --colored.color blue --rect.width 3
Rectangle(3.0x1.0) ColoredRectangle(1.0x1.0)[blue]
> python examples/example7.py -C examples/config7_out.py
Rectangle(3.0x1.0) ColoredRectangle(1.0x1.0)[blue]
```

### 8) Typed ConfigObjects and containers

The script in [examples/example8.py](./examples/example8.py) chooses the optimizer class on the command line,
and builds a list of layers with a class per element (from [examples/layers8.py](./examples/layers8.py)).
The layer classes do not need to be known to the script: the class `Pool` is loaded from [examples/plugins8.py](./examples/plugins8.py) with `src`.
```
> python examples/example8.py --optimizer Adam --optimizer.lr 0.01 --layers examples/config8.py --layers.3 Pool --layers.3.src examples/plugins8.py
MagiConfig(lr=0.01, betas=[0.9, 0.999])
Conv MagiConfig(channels=16, kernel=3)
Conv MagiConfig(channels=32, kernel=3)
Dense MagiConfig(units=10)
Pool MagiConfig(size=2)
```

The container config file [examples/config8.py](./examples/config8.py) provides the first three layers:
```python
config = [
    Conv,
    (Conv, MagiConfig(channels=32)),
    (Dense, MagiConfig(units=10)),
]
```

The help message shows the arguments of the chosen classes:
```
> python examples/example8.py --optimizer Adam --layers.0 Dense --help
usage: example8.py [-h] [-O TYPE [CONFIG ...]] [-L CONFIG [CONFIG ...]]
                   [--layers.src SRC]

optional arguments:
  -h, --help            show this help message and exit

optimizer:
  -O TYPE [CONFIG ...], --optimizer TYPE [CONFIG ...]
                        optimizer class and config
  --optimizer.lr LR     learning rate
  --optimizer.betas BETAS BETAS
                        beta parameters

layers:
  -L CONFIG [CONFIG ...], --layers CONFIG [CONFIG ...]
                        layer configs
  --layers.src SRC      module or file (.py) that defines the class

  layers.0:
    fully connected layer

    --layers.0 TYPE [CONFIG ...]
                        element 0 (class and config files)
    --layers.0.src SRC  module or file (.py) that defines the class
    --layers.0.units UNITS
                        number of units
```

The script writes the sections separately: `examples/config8_out_layers.py` contains the layers, including the class loaded from a file:
```python
from magiconfig import MagiConfig
from layers8 import Conv
from layers8 import Dense
from magiconfig import import_config
Pool = import_config('examples/plugins8.py', 'Pool')

config = [(Conv, MagiConfig(channels=16, kernel=3)), (Conv, MagiConfig(channels=32, kernel=3)), (Dense, MagiConfig(units=10)), (Pool, MagiConfig(size=2))]
```
and `examples/config8_out_optimizer.py` contains the optimizer config, with its class in a comment:
```
> python examples/example8.py --optimizer Adam examples/config8_out_optimizer.py --layers examples/config8_out_layers.py
MagiConfig(betas=[0.9, 0.999], lr=0.01)
Conv MagiConfig(channels=16, kernel=3)
Conv MagiConfig(channels=32, kernel=3)
Dense MagiConfig(units=10)
Pool MagiConfig(size=2)
```

### 9) DictAction and the config printer

The config file [examples/config9.py](./examples/config9.py) generates a grid of samples in a loop.
The config printer shows its contents:
```
> python -m magiconfig examples/config9.py
from magiconfig import MagiConfig

samples = MagiConfig()
samples.m100_w0p1 = MagiConfig()
samples.m100_w0p1.name = 'm100_w0p1'
samples.m100_w0p1.params = {'mass': 100, 'width': 0.1}
samples.m100_w0p2 = MagiConfig()
samples.m100_w0p2.name = 'm100_w0p2'
samples.m100_w0p2.params = {'mass': 100, 'width': 0.2}
samples.m200_w0p1 = MagiConfig()
samples.m200_w0p1.name = 'm200_w0p1'
samples.m200_w0p1.params = {'mass': 200, 'width': 0.1}
samples.m200_w0p2 = MagiConfig()
samples.m200_w0p2.name = 'm200_w0p2'
samples.m200_w0p2.params = {'mass': 200, 'width': 0.2}

default = samples.m100_w0p1
```

The script in [examples/example9.py](./examples/example9.py) uses a `DictAction` for the parameters,
which can be modified on the command line:
```
> python examples/example9.py -C examples/config9.py --obj samples.m200_w0p2 -p mass=250
MagiConfig(name='m200_w0p2', params={'mass': 250.0, 'width': 0.2})
```

### 10) App layer

The script in [examples/example10.py](./examples/example10.py) turns a function into an application:
```
> python examples/example10.py --help
usage: example10.py [-h] [-C CONFIG] [--obj OBJ]

Greet someone.

optional arguments:
  -h, --help            show this help message and exit

config:
  -C CONFIG, --config CONFIG
                        name of config file to import
  --obj OBJ             name of object to import from config file
  --verbose             verbose output
  --name NAME           who to greet
  --times TIMES         number of greetings
> python examples/example10.py -C examples/config10.py --verbose
greeting magiconfig 2 time(s)
hello, magiconfig!
hello, magiconfig!
```

## Development

The tests use [pytest](https://pytest.org) and include the upstream argparse tests for the running Python version
(modified to use `magiconfig.ArgumentParser`; downloading them requires network access).
Run all tests with:
```
./ci/run_tests.sh
```
Any extra arguments are passed to pytest. The script does not install anything; for example, with [uv](https://docs.astral.sh/uv/):
```
uv run --no-project --python 3.13 --with pytest ci/run_tests.sh
```
The upstream argparse tests require the CPython `test` package; if it is not available (e.g. in uv-managed Python builds), they are skipped,
unless `MAGICONFIG_REQUIRE_ARGPARSE_TESTS=1` is set (as in CI).
The GitHub Actions workflow runs the same script for each supported Python version.

The package is built and published with [flit](https://flit.pypa.io):
```
flit build
flit publish
```
(`flit publish` uploads to PyPI; use `--repository testpypi` to try it on TestPyPI first.)

## Inspirations

This project owes inspiration (and in some cases code) to:
* [ConfigArgParse](https://github.com/bw2/ConfigArgParse)
* [configurati](https://github.com/duckworthd/configurati)
* [WMCore](https://github.com/dmwm/WMCore)
