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
  * `MagiConfig` is used both as the input object in config files and as the output object of the parser
* options related to the Python config file and object are contained in the class `MagiConfigOptions`:
  * `args`: the command-line arguments to indicate the config file (default: "-C", "--config")
  * `obj`: name of the `MagiConfig` object to be imported from the config file (default: "config")
  * `required`: if the config arg is required when parsing (default: False)
  * `default`: default value for the config file name (default: None)
  * `strict`: reject imported config object if it has unknown attributes (default: False)
* precedence of parameter values: command line > config file > defaults
* values provided in a config file satisfy the "required" attribute of any such arguments specified in the parser
* types specified for dests in argparse arguments are enforced for attributes imported from a config file
  * exception: if multiple types are specified for a single dest, types are ignored in imported attributes

## Examples

## Inspirations

This project owes inspiration (and in some cases code) to:
* [ConfigArgParse](https://github.com/bw2/ConfigArgParse)
* [configurati](https://github.com/duckworthd/configurati)
* [WMCore](https://github.com/dmwm/WMCore)
