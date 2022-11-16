# magiconfig

Configure Python with Python.

Table of Contents
=================
* [Overview](#overview)
* [Philosophy](#philosophy)
* [Features](#features)
   * [ArgumentParser](#argumentparser)
      * [Constructor](#constructor)
      * [parse_args(), parse_known_args()](#parse_args-parse_known_args)
      * [parse_config(config_name, config_obj, config_strict, namespace=None)](#parse_configconfig_name-config_obj-config_strict-namespacenone)
      * [set_config_options(**kwargs)](#set_config_optionskwargs)
      * [copy_config_options(config_options)](#copy_config_optionsconfig_options)
      * [remove_config_options()](#remove_config_options)
      * [write_config(namespace, filename, obj=None, attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False)](#write_confignamespace-filename-objnone-attr_importsnone-class_importsnone-attr_reprsnone-class_reprsnone-strictfalse)
      * [add_config_argument(arg, **kwargs)](#add_config_argumentarg-kwargs)
      * [remove_config_argument(arg)](#remove_config_argumentarg)
      * [add_config_only(*args, **kwargs)](#add_config_onlyargs-kwargs)
      * [remove_config_only(arg)](#remove_config_onlyarg)
      * [remove_argument(arg, keep=False)](#remove_argumentarg-keepfalse)
   * [MagiConfigOptions](#magiconfigoptions)
      * [Constructor](#constructor-1)
   * [MagiConfig](#magiconfig-1)
      * [write(filename, config_obj, attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False)](#writefilename-config_obj-attr_importsnone-class_importsnone-attr_reprsnone-class_reprsnone-strictfalse)
      * [join(other_config, prefer_other=False)](#joinother_config-prefer_otherfalse)
   * [MagiConfigError](#magiconfigerror)
   * [Other](#other)
      * [Subparser aliases](#subparser-aliases)
      * [Convenience](#convenience)
* [Examples](#examples)
   * [1) Basic setup](#1-basic-setup)
   * [2) Subparsers](#2-subparsers)
   * [3) Config-driven](#3-config-driven)
   * [4) Scaling up](#4-scaling-up)
* [Inspirations](#inspirations)

(Created by [gh-md-toc](https://github.com/ekalinin/github-markdown-toc))

## Overview

magiconfig is an extension of argparse that stops the
[configuration complexity clock](https://mikehadlow.blogspot.com/2012/05/configuration-complexity-clock.html)
by enabling users to configure Python with Python.
It provides all the power of Python to manipulate and compose configuration parameters,
bypassing the limitations of text-based configuration languages.

## Philosophy

This module treats argparse as an engine that ultimately provides a namespace of attributes ("dests") to be consumed by user applications.
With magiconfig, these attributes can be provided by an imported [`MagiConfig`](#MagiConfig-1) Python object,
in addition to the usual command-line arguments.

## Features

magiconfig is compatible with both Python 2 and Python 3.
It provides a custom [`ArgumentParser`](#ArgumentParser) class, which is a drop-in replacement for `argparse.ArgumentParser`.
It also provides [`MagiConfig`](#MagiConfig-1), [`MagiConfigOptions`](#MagiConfigOptions), and [`MagiConfigError`](#MagiConfigError) classes.
The precedence of parameter values is: command line > config file > defaults.

### ArgumentParser

The API of this class is extended with several additional functions to manage config settings, as well as to provide other useful operations.

#### Constructor

The constructor supports several additional options:
* `config_options`: takes an instance of [`MagiConfigOptions`](#MagiConfigOptions); default = `None` (falls back to standard argparse behavior)
* `config_only_help`: include config-only args in the help message (see [`add_config_argument()`](#add_config_argumentarg-kwargs)); default = `True`

#### `parse_args(), parse_known_args()`

These function interfaces are unchanged from argparse, but they return a [`MagiConfig`](#MagiConfig-1) object.
If an input `namespace` argument is provided but is not of type [`MagiConfig`](#MagiConfig-1), a conversion will be attempted.

#### `parse_config(config_name, config_obj, config_strict, namespace=None)`

This is mainly an internal function used in `parse_known_args()`, but like that function, it could also be used standalone.

* `config_name`: name of config file to import
* `config_obj`: name of config object inside config file
* `config_strict`: whether to reject imported config object if it has unknown attributes
* `namespace`: `Namespace` object to append to, if any

Raises [`MagiConfigError`](#MagiConfigError) if any required config-only arguments are missing or if `config_strict` is `True` and the imported config has unknown attributes.

#### `set_config_options(**kwargs)`

This function allows changing the config options after the parser is initialized.
It accepts all parameters that can be used to construct an instance of [`MagiConfigOptions`](#MagiConfigOptions).
Raises [`MagiConfigError`](#MagiConfigError) if any other parameters are provided.

#### `copy_config_options(config_options)`

This function allows copying another [`MagiConfigOptions`](#MagiConfigOptions) object to be used in this parser.
Raises [`MagiConfigError`](#MagiConfigError) if an object with any unknown parameters is provided.

#### `remove_config_options()`

This function allows removing all config options from the parser.

#### `write_config(namespace, filename, obj=None, attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False)`

* `namespace`: [`MagiConfig`](#MagiConfig-1) object to be written
* `filename`: name of file to write
* `obj`: name of the [`MagiConfig`](#MagiConfig-1) object in the file (default: class member `config_options.obj` or `"config"` if no `config_options` specified)
* `attr_imports`: dictionary with key = attribute name, value = function returning a string of `import` statements
* `class_imports`: dictionary with key = class type, value = function returning a string of `import` statements
* `attr_reprs`: dictionary with key = attribute name, value = function returning a `repr`-style string
* `class_reprs`: dictionary with key = class type, value = function returning a `repr`-style string
* `strict`: for each attribute, check if calling `eval()` on the `repr`-style string returns the original value

This function can be used to preserve the state of the configuration after any command-line modifications (see [Example 1](#1-basic-setup)).
By default, the class module and name of each entry in the configuration are used to determine if import statements are needed,
and `repr()` is used to provide a representation of the entry from which it can be reconstructed.
(If an entry is a `Collection` or `Mapping` type, its entries are also inspected for imports. For other `Container` types, their entries are expected if they can be obtained via `vars()`.)
If these defaults are not correct for a given entry or a given class type, they can be overridden by providing custom functions using the options
`attr_imports`, `class_imports`, `attr_reprs`, `class_reprs` as described above.
The order of precedence is: `attr_* > class_* > default`.
Strict checking of the validity of `repr`-style strings is currently disabled by default, but may be enabled by default in the next major release (3.0.0).

#### `add_config_argument(arg, **kwargs)`

This interface allows adding a dest (`arg`) that is only provided by the config, not by a command-line argument.
The supported `kwargs` are: `default`, `type`, `choices`, `required`, `help` (an appropriate subset of `argparse.ArgumentParser.add_argument()`).

#### `remove_config_argument(arg)`

* `arg`: name of config-only arg to remove

Raises `KeyError` if arg is not found in the list of config-only args.

#### `add_config_only(*args, **kwargs)`

**This function is deprecated and will be removed in magiconfig 3.0.0; please switch to [add_config_argument()](#add_config_argumentarg-kwargs).**

This interface allows adding dests that are only provided by the config, not by command-line arguments.

* `args`: no default value, not required
* `**kwargs`: default value OR required (value=`None`)

Raises [`MagiConfigError`](#MagiConfigError) if any dests have already been used by arguments (actions) added to the parser.
Similarly, `add_argument()` now raises `ArgumentError` if it specifies a dest that has already been added as config-only by this function.

#### `remove_config_only(arg)`

**This function is deprecated and will be removed in magiconfig 3.0.0; please switch to [remove_config_argument()](#remove_config_argumentarg).**

* `arg`: name of config-only arg to remove

Raises `KeyError` if arg is not found in the list of config-only args.

#### `remove_argument(arg, keep=False)`

This function allows removing a single argument (a missing feature in argparse).

* `arg`: flag (for optional arguments) or dest (for positional arguments)
* `keep`: for optional arguments, `True` will remove just the single specified flag `arg` (the entire action is removed only if it has no remaining flags); `False` (default) always removes the action associated with the flag
* for positional arguments, all positional actions with the specified dest are removed (but not optional arguments with that dest)

Exits with `error()` if an unknown argument is provided.

### MagiConfigOptions

This simple class stores options related to the use of configs in the [`ArgumentParser`](#ArgumentParser).

#### Constructor

* `args`: the command-line arguments to indicate the config file (default: `["-C", "--config"]`)
* `help`: custom help message for config args (optional)
* `required`: if the config arg is required when parsing (default: `False`)
* `default`: default value for the config file name (default: `None`)
* `dest`: destination for config arg (default: `"config"`)
* `obj`: name of the `MagiConfig` object to be imported from the config file (default: `"config"`)
* `obj_args`: command-line arguments to indicate the name of the object to be imported (optional)
* `obj_help`: custom help message for obj args (optional)
* `obj_dest`: destination for obj arg (default: `"obj"`)
* `strict`: reject imported config object if it has unknown attributes (default: `False`)
* `strict_args`: optional command-line arguments to toggle strictness
  * if `strict` above is set to `False`, providing an arg will toggle it to `True`; if set to `True`, will toggle it to `False`
* `strict_help`: custom help message for strict args (optional)
* `strict_dest`: destination for strict arg (default: `"strict"`)

The values for `args`, `obj_args`, and `strict_args` can be positional arguments (rather than the optional arguments shown here).

### MagiConfig

This class extends `argparse.Namespace` to add a few useful methods.
It is used both as the input object in config files and as the output object of [`ArgumentParser`](#ArgumentParser).

#### `write(filename, config_obj, attr_imports=None, class_imports=None, attr_reprs=None, class_reprs=None, strict=False)`

* `filename`: name of file to write
* `config_obj`: name of [`MagiConfig`](#MagiConfig-1) object in file
* other options: see documentation for [`ArgumentParser.write_config()`](#write_confignamespace-filename-objnone-attr_importsnone-class_importsnone-attr_reprsnone-class_reprsnone-strictfalse)

#### `join(other_config, prefer_other=False)`

* `other_config`: other [`MagiConfig`](#MagiConfig-1) object to merge
* `prefer_other`: prefer values from other config, if dest is present in both configs (default: prefer this config)

#### `getattr()`, `setattr()`

These class methods are extended to handle nested config objects automatically.
Any nonexistent intermediate objects are initialized as [`MagiConfig`](#MagiConfig-1) instances. Example:
```python
from magiconfig import MagiConfig
x = MagiConfig()
setattr(x,"y.z","test")
print(x)
```
returns: `MagiConfig(y=MagiConfig(z='test'))`

This enables obtaining dests from nested configs by using dots in the dest names.

### MagiConfigError

This class derives from `Exception` and denotes magiconfig-specific errors.

### Other

#### Subparser aliases

`_SubParsersAction.add_parser` is modified to backport the use of subparser aliases to Python 2.

#### Convenience

All public classes and constants from argparse are added to the magiconfig namespace for easier drop-in usage.

A class `ArgumentDefaultsRawHelpFormatter` is defined to present help messages with default values and without line wrapping (from [ConfigArgParse](https://github.com/bw2/ConfigArgParse)).

## Examples

### 1) Basic setup

The simple script in [examples/example1.py](./examples/example1.py)
demonstrates the different ways to set values, as well as some of the features of magiconfig.

The help printout for the arguments defined in the script:
```
usage: example1.py [-h] [-C CONFIG] [-f FOO] -b BAR [-i]

optional arguments:
  -h, --help            show this help message and exit
  -C CONFIG, --config CONFIG
                        name of config file to import (w/ object: config)
  -f FOO, --foo FOO     foo arg
  -b BAR, --bar BAR     bar arg
  -i, --ipsum           ipsum arg
```

When the script is run as follows:
```
python3 examples/example1.py -C examples/config1.py --foo 'foo'
```

It prints the resulting namespace:
```
MagiConfig(bar=3.0, foo='foo', ipsum=False)
```

Here, the `bar` argument is set by the config file [examples/config1.py](./examples/config1.py),
the `foo` argument is set on the command line, and the `ipsum` argument retains its default value.

The script also writes the final namespace into a config file `examples/config1_out.py`:
```python
from magiconfig import MagiConfig

config = MagiConfig()
config.bar = 3.0
config.foo = 'foo'
config.ipsum = False
```

With this config file, the script can be rerun to produce the same output without
the need to specify any other command-line arguments:
`python examples/example1.py -C examples/config1_out.py`.

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
The config file [examples/config3.py](./examples/config3.py) can be used with the script:
```
> python examples/example3.py -C examples/config3.py -v
MagiConfig(dataset=MagiConfig(background='background', path='/data', signal='signal'), hyper=MagiConfig(learning_rate=0.1, loss='log'), training=MagiConfig(size=0.5, weights=[1, 1]), verbose=True)
```

This example also shows how config-only arguments can be given default values or marked as required. These attributes are reflected in the help message:
```
> python examples/example3.py --help
usage: example3.py [-h] [-C CONFIG] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -C CONFIG, --config CONFIG
                        name of config file to import (w/ object: config) (default: None)
  -v, --verbose         enable verbose output (default: False)

config-only arguments:
  dataset.background    (required)
  dataset.path            (default: /data)
  dataset.signal        (required)
  hyper.learning_rate
  hyper.loss
  training.size
  training.weights
```

### 4) Scaling up

When scaling up an application to handle a large number of possible inputs,
a typical pattern is that some of the parameters are common,
while other parameters may be unique to each input.
Rather than requiring a separate config file for each possible input,
all of the config objects can be generated within a single Python file.
The script in [examples/example4.py](./examples/example4.py)
allows the config object name to be specified on the command line;
other config objects in the config file are just ignored.

The help message for this script is:
```
usage: example4.py [-h] [-C CONFIG] [-O OBJ] [-f FOO] -b BAR -i INPUT

optional arguments:
  -h, --help            show this help message and exit
  -C CONFIG, --config CONFIG
                        name of config file to import (w/ object from -O,--obj) (default: None)
  -O OBJ, --obj OBJ     name of object to import from config file (default: config)
  -f FOO, --foo FOO     foo arg (default: lorem)
  -b BAR, --bar BAR     bar arg (default: None)
  -i INPUT, --input INPUT
                        input arg (default: None)
```

The script can be run with different inputs all contained in [examples/config4.py](./examples/config4.py):
```
> python3 examples/example4.py -C examples/config4.py -O config.a
MagiConfig(bar=3.0, foo='foo', input='a')
> python3 examples/example4.py -C examples/config4.py -O config.b
MagiConfig(bar=3.0, foo='foo', input='b')
```

## Inspirations

This project owes inspiration (and in some cases code) to:
* [ConfigArgParse](https://github.com/bw2/ConfigArgParse)
* [configurati](https://github.com/duckworthd/configurati)
* [WMCore](https://github.com/dmwm/WMCore)
