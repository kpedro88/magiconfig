from magiconfig import ArgumentParser, MagiConfigOptions, ArgumentDefaultsRawHelpFormatter
import six

if __name__=="__main__":
    parser = ArgumentParser(
        config_options=MagiConfigOptions(
            obj_args = ["-O","--obj"],
        ),
        formatter_class=ArgumentDefaultsRawHelpFormatter,
    )
    parser.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")
    parser.add_argument("-i","--input", dest="input", type=str, required=True, help="input arg")
    args = parser.parse_args()
    six.print_(args)
