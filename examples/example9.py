from magiconfig import ArgumentParser, DictAction, ASK

if __name__=="__main__":
    parser = ArgumentParser()
    parser.add_argument("-C","--config", config=True, prefix=False, obj=ASK)
    parser.set_default_source("config")
    parser.add_argument("-n","--name", default="", help="sample name")
    parser.add_argument("-p","--params", action=DictAction, value_type=float, default={}, help="model parameters")
    args = parser.parse_args()
    print(args)
