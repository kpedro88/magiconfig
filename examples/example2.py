from magiconfig import ArgumentParser

if __name__=="__main__":
    # the top-level parser does not need a config arg if it will have subparsers
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_one = subparsers.add_parser("one")
    parser_one.add_argument("-C","--config", config=True, prefix=False, obj="config.one")
    parser_one.set_default_source("config")
    parser_one.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")

    parser_two = subparsers.add_parser("two")
    parser_two.add_argument("-C","--config", config=True, prefix=False, obj="config.two")
    parser_two.set_default_source("config")
    parser_two.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")

    args = parser.parse_args()
    print(args)
