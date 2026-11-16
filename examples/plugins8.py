from magiconfig import ConfigObject

# a layer class that the script does not know about
class Pool(ConfigObject):
    _description = "pooling layer"
    _arguments = dict(size = dict(type=int, default=2, help="pool size"))
