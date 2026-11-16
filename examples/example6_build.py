from models6 import Model

if __name__=="__main__":
    # no command-line parsing: just use a colleague's config file
    model = Model.build("examples/colleague_config.py")
    print(model.describe())
    print(Model.__doc__)
