from magiconfig import MagiConfig

config = MagiConfig(
    dataset = MagiConfig(),
    training = MagiConfig(),
    hyper = MagiConfig(),
)

config.dataset.path = "/data"
config.dataset.signal = "signal"
config.dataset.background = "background"

config.training.size = 0.5
config.training.weights = [1,1]

config.hyper.learning_rate = 0.1
config.hyper.loss = "log"