from magiconfig import MagiConfig
from layers8 import Conv, Dense

config = [
    Conv,
    (Conv, MagiConfig(channels=32)),
    (Dense, MagiConfig(units=10)),
]
