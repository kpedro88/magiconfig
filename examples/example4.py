from magiconfig import ArgumentParser, ArgumentDefaultsRawHelpFormatter, ASK

if __name__=="__main__":
    parser = ArgumentParser(formatter_class=ArgumentDefaultsRawHelpFormatter)
    # obj=ASK: the name of the object to import can be given on the command line (--obj)
    parser.add_argument("-C","--config", config=True, prefix=False, obj=ASK)
    parser.set_default_source("config")
    parser.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")
    parser.add_argument("-i","--input", dest="input", type=str, required=True, help="input arg")
    args = parser.parse_args()
    print(args)
