from magiconfig import MagiConfig

# a grid of models generated in a loop
samples = MagiConfig()
for mass in [100, 200]:
    for width in [0.1, 0.2]:
        name = f"m{mass}_w{width}".replace(".","p")
        setattr(samples, name, MagiConfig(name=name, params=dict(mass=mass, width=width)))

default = samples.m100_w0p1
