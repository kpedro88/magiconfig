from magiconfig import ConfigObject

class Conv(ConfigObject):
    _description = "convolutional layer"
    _arguments = dict(
        channels = dict(type=int, default=16, help="number of channels"),
        kernel = dict(type=int, default=3, help="kernel size"),
    )

class Dense(ConfigObject):
    _description = "fully connected layer"
    _arguments = dict(
        units = dict(type=int, default=32, help="number of units"),
    )

class SGD(ConfigObject):
    _arguments = dict(lr = dict(type=float, default=0.1, help="learning rate"))

class Adam(ConfigObject):
    _arguments = dict(
        lr = dict(type=float, default=0.001, help="learning rate"),
        betas = dict(type=float, nargs=2, default=[0.9, 0.999], help="beta parameters"),
    )
