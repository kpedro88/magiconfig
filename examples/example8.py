from magiconfig import ArgumentParser, ASK
from layers8 import SGD, Adam

if __name__=="__main__":
    parser = ArgumentParser()
    # the class is chosen on the command line: --optimizer TYPE [CONFIG ...]
    parser.add_argument("-O","--optimizer", action="specify_type", default=SGD, choices=[SGD, Adam], help="optimizer class and config")
    # a list of layers with a class per element: --layers.N TYPE [CONFIG ...]
    parser.add_argument("-L","--layers", action="specify_type", container=list, src=ASK, help="layer configs")
    args = parser.parse_args()
    print(args.optimizer)
    for layer in args.layers:
        print(type(layer).__name__, layer)
    parser.write_config(args,"examples/config8_out.py",separate=True)
