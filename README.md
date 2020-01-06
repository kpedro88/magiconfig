# magiconfig

Configure Python with Python.

## Overview

magiconfig is an extension of argparse that stops the
[configuration complexity clock](https://mikehadlow.blogspot.com/2012/05/configuration-complexity-clock.html)
by enabling users to configure Python with Python.
It provides all the power of Python to manipulate and compose configuration parameters,
bypassing the limitations of text-based configuration languages.

## Philosophy

This module treats argparse as an engine that ultimately provides a namespace of attributes ("dests") to be consumed by user applications.
With magiconfig, these attributes can be provided by an imported `MagiConfig` Python object,
in addition to the usual command-line arguments.

## Features

* compatible with both Python 2 and Python 3
* provides custom `ArgumentParser` class, which is a drop-in replacement for `argparse.ArgumentParser`
* provides `MagiConfig` object that extends `argparse.Namespace` to add useful methods:
  * `write()`: produce a Python config file that reproduces the current state of the namespace
  * `join()`: merge with another config object
  * used both as the input object in config files and as the output object of the parser
* options related to the Python config file and object are contained in the class `MagiConfigOptions`:
  * `args`: the command-line arguments to indicate the config file (default: "-C", "--config")
  * `obj`: name of the `MagiConfig` object to be imported from the config file (default: "config")
  * `required`: if the config arg is required when parsing (default: False)
  * `default`: default value for the config file name (default: None)
  * `strict`: reject imported config object if it has unknown attributes (default: False)
    * additional dests, unrelated to the command-line arguments, can be specified using `ArgumentParser.set_defaults(*args,**kwargs)`
    * to specify additional dests without providing default values, provide strings for `*args` in the above method
* precedence of parameter values: command line > config file > defaults
* values provided in a config file satisfy the "required" attribute of any such arguments specified in the parser
* types specified for dests in argparse arguments are enforced for attributes imported from a config file
  * exception: if multiple types are specified for a single dest, types are ignored in imported attributes
* dests can be obtained from nested configs by using dots in the dest names

## Examples

### 1) Basic setup

The simple script in [examples/example1.py](./examples/example1.py)
demonstrates the different ways to set values, as well as some of the features of magiconfig.

The help printout for the arguments defined in the script:
```
usage: example1.py [-C CONFIG] [-h] [-f FOO] -b BAR [-i]

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
The script in [examples/example2.py](./examples/example3.py) is an example.

It shows how an organized schema with different categories and parameters can be defined and transmitted to the parser.
This allows the parser to use strict mode to validate input configurations, rejecting any config with unknown parameters.
The config file [examples/config3.py](./examples/config3.py) can be used with the script:
```
> python examples/example3.py -C examples/config3.py -v
MagiConfig(dataset=MagiConfig(background='background', path='/data', signal='signal'), hyper=MagiConfig(learning_rate=0.1, loss='log'), training=MagiConfig(size=0.5, weights=[1, 1]), verbose=True)
```

## Inspirations

This project owes inspiration (and in some cases code) to:
* [ConfigArgParse](https://github.com/bw2/ConfigArgParse)
* [configurati](https://github.com/duckworthd/configurati)
* [WMCore](https://github.com/dmwm/WMCore)
