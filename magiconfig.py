import argparse
import os, imp, uuid
import six
from collections import defaultdict

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
    def join(self, other_config):
        for attr,val in six.iteritems(vars(other_config)):
            setattr(self,attr,val)

class ArgumentParser(argparse.ArgumentParser):
    # additional arguments:
    # config_args = arguments used to indicate config file
    # config_obj = string identifying magiconfig object in module imported from config file
    # config_required = require config_arg to be provided when parsing
    # strict = reject imported config if it has unknown keys
    def __init__(self, config_args=["-C","--config"], config_obj="config", config_required=False, strict=False, **kwargs):
        if len(config_obj)==0:
            raise ValueError("config_obj must be specified")

        self.config_args = config_args
        self.config_obj = config_obj
        self.strict = strict
        argparse.ArgumentParser.__init__(self, **kwargs)
        
        # set up config arg(s) if any
        # dest is fixed because it is only used in internal namespace
        if len(config_args)>0: self._config_action = self.add_argument(*config_args, dest="config", type=str, help="name of config file to import", required=config_required)
        else: self._config_action = None
        # keep config action separate from other actions
        self._remove_action(self._config_action)
        self._other_actions = []

    parse_known_args_orig = argparse.ArgumentParser.parse_known_args

    def parse_known_args(self, args=None, namespace=None):
        if namespace is None: namespace = MagiConfig()

        # fall back to default argparse behavior
        if self._config_action is None:
            return self.parse_known_args_orig(args=args,namespace=namespace)

        # reset known args to just config_args and parse
        self._other_actions = self._actions[:]
        self._actions = [self._config_action]
        tmpspace, remaining_args = self.parse_known_args_orig(args=args)

        # fall back to default argparse behavior
        # (config_required already checked above, when parsing for config_arg)
        if not hasattr(tmpspace,"config") or tmpspace.config is None:
            # restore known args and parse
            self._actions = self._other_actions[:]
            self._other_actions = []
            return self.parse_known_args_orig(args=args,namespace=namespace)

        # get namespace as filled by config
        namespace = self.parse_config(tmpspace.config,namespace=namespace)

        # restore known args
        self._actions = self._other_actions[:]

        # call parse_known_args_orig again (supplying namespace from above)
        tmpspace, remaining_args = self.parse_known_args_orig(args=remaining_args,namespace=namespace)

        # restore required actions
        for action in self._required:
            action.required = True

        # finish
        return tmpspace, remaining_args

    def parse_config(self, config_name, namespace=None):
        # import config as module
        module_id = str(uuid.uuid4())
        module = imp.load_source(module_id, os.path.abspath(config_name))
        config = getattr(module,self.config_obj)

        # get dict of dest:action(s) from other_actions
        dests = defaultdict(list)
        for action in self._other_actions:
            dests[action.dest].append(action)

        # loop over vars(config) to populate namespace
        known_attrs = []
        unknown_attrs = []
        self._required = []
        for attr,val in six.iteritems(vars(config)):
            if attr in dests:
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
        if self.strict and len(unknown_attrs)>0:
            raise ValueError("Imported config contained unknown attributes: "+','.join(unknown_attrs))

        return namespace

    # write namespace into file using config_obj
    def write_config(self, namespace, filename):
        namespace.write(filename,self.config_obj)

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
