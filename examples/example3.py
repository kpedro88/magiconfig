from magiconfig import ArgumentParser, MagiConfigOptions
import six

if __name__=="__main__":
    # define schema of config parameters
    config_schema = {
        "dataset": ["path","signal","background"],
        "training": ["size","weights"],
        "hyper": ["learning_rate","loss"],
    }
    config_schema_flat = [key+"."+val for key,vals in six.iteritems(config_schema) for val in vals]

    parser = ArgumentParser(
        config_options=MagiConfigOptions(
            strict = True,
        )
    )
    parser.add_argument("-v","--verbose", dest="verbose", action="store_true", help="enable verbose output")
    # include schema in parser
    parser.set_defaults(*config_schema_flat)
    args = parser.parse_args()
    if args.verbose: six.print_(args)
