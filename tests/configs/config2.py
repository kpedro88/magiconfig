import os
from magiconfig import import_config

cfg = import_config(os.path.join(os.path.dirname(__file__), "config1.py"), "config")
