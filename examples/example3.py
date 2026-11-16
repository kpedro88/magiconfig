from magiconfig import ArgumentParser, ArgumentDefaultsRawHelpFormatter

if __name__=="__main__":
    # define schema of config parameters
    config_schema = {
        "dataset": ["path","signal","background"],
        "training": ["size","weights"],
        "hyper": ["learning_rate","loss"],
    }
    config_schema_flat = {key+"."+val: {} for key,vals in config_schema.items() for val in vals}
    # specify default value, required args
    config_schema_flat["dataset.path"] = {"default": "/data"}
    config_schema_flat["dataset.background"] = {"required": True}
    config_schema_flat["dataset.signal"] = {"required": True}

    parser = ArgumentParser(formatter_class=ArgumentDefaultsRawHelpFormatter)
    parser.add_argument("-C","--config", config=True, prefix=False, strict=True)
    parser.set_default_source("config")
    # transient: used only for this run, never written to or read from configs
    parser.add_argument("-v","--verbose", dest="verbose", action="store_true", transient=True, help="enable verbose output")
    # include schema in parser
    for arg,kwargs in config_schema_flat.items():
        parser.add_argument(arg, config_only=True, **kwargs)

    args = parser.parse_args()
    if args.verbose: print(args)
