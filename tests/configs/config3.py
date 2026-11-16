import os, copy
from magiconfig import import_config

config = copy.deepcopy(import_config(os.path.join(os.path.dirname(__file__), "config1.py"), "config"))
config.extra = "blah"
