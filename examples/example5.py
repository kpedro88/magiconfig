from magiconfig import ArgumentParser

if __name__=="__main__":
    parser = ArgumentParser()
    # each config arg has its own section of arguments
    parser.add_argument("-D","--data", config=True, help="data config")
    parser.add_argument("--path", default="/data", help="data path", source="data")
    parser.add_argument("--signal", required=True, help="signal sample", source="data")
    parser.add_argument("-T","--train", config=True, help="training config")
    parser.add_argument("--lr", type=float, default=0.1, help="learning rate", source="train")
    parser.add_argument("--epochs", type=int, default=10, help="number of epochs", source="train")
    args = parser.parse_args()
    print(args)
    # one file per config: examples/config5_out_data.py, examples/config5_out_train.py
    parser.write_config(args,"examples/config5_out.py",separate=True)
