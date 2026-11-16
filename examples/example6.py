from magiconfig import ArgumentParser
from models6 import Model

if __name__=="__main__":
    parser = ArgumentParser()
    parser.add_argument("-M","--model", type=Model, help="model config")
    args = parser.parse_args()
    print(args.model.describe())
