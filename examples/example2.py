from magiconfig import ArgumentParser, MagiConfigOptions
import six

if __name__=="__main__":
    # parser does not need config_options if it will have subparsers
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_one = subparsers.add_parser("one",
        config_options=MagiConfigOptions(
            obj = "config.one"
        )
    )
    parser_one.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")

    parser_two = subparsers.add_parser("two",
        config_options=MagiConfigOptions(
            obj = "config.two"
        )
    )
    parser_two.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")
    
    args = parser.parse_args()
    six.print_(args)
