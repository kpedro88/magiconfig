from magiconfig import MagiConfig

# common settings
common = MagiConfig()
common.foo = "foo"
common.bar = 3.0

# generate new configs for each input
config = MagiConfig()
for input in ["a","b","c"]:
    setattr(config,input,MagiConfig())
    cfg = getattr(config,input)
    cfg.input = input
    cfg.join(common)
