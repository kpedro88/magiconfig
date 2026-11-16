from magiconfig import MagiConfig

config = MagiConfig()
config.layers = 8
config.optimizer = MagiConfig(name="adam", lr=0.001)
