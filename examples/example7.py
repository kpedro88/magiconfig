from magiconfig import ArgumentParser, ConfigObject

# existing classes that are not ConfigObjects
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def __repr__(self):
        return f"{type(self).__name__}({self.width}x{self.height})"

class ColoredRectangle(Rectangle):
    def __init__(self, width, height, color):
        super().__init__(width, height)
        self.color = color

    def __repr__(self):
        return f"{super().__repr__()}[{self.color}]"

# proxies: build the existing classes instead of the ConfigObjects
class RectangleConfig(ConfigObject):
    _description = "a rectangle"
    _arguments = dict(
        width = dict(type=float, default=1.0, help="width"),
        height = dict(type=float, default=1.0, help="height"),
    )
    _principal = Rectangle

# inheritance: extend (or modify) the parent's arguments
class ColoredRectangleConfig(RectangleConfig):
    _description = "a colored rectangle"
    _arguments = RectangleConfig._arguments | dict(
        color = dict(default="red", help="color"),
    )
    _principal = ColoredRectangle

if __name__=="__main__":
    parser = ArgumentParser(basic=True)
    parser.add_argument("--rect", type=RectangleConfig, help="rectangle config")
    parser.add_argument("--colored", type=ColoredRectangleConfig, help="colored rectangle config")
    args = parser.parse_args()
    print(args.rect, args.colored)
    parser.write_config(args,"examples/config7_out.py")
