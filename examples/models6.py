from magiconfig import ConfigObject

class Optimizer(ConfigObject):
    _description = "optimizer settings"
    _arguments = dict(
        name = dict(choices=["sgd","adam"], default="sgd", help="optimizer name"),
        lr = dict(type=float, default=0.1, help="learning rate"),
    )

class Model(ConfigObject):
    """A toy model with a nested optimizer."""
    _description = "model settings"
    _arguments = dict(
        layers = dict(type=int, default=2, help="number of layers"),
        optimizer = dict(type=Optimizer, help="optimizer config"),
    )

    def describe(self):
        return f"{self.layers} layers, {self.optimizer.name} optimizer with lr={self.optimizer.lr}"
