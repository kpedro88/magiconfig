from magiconfig import ArgumentParser

if __name__=="__main__":
    parser = ArgumentParser(basic=True)
    parser.add_argument("-f","--foo", dest="foo", type=str, default="lorem", help="foo arg")
    parser.add_argument("-b","--bar", dest="bar", type=float, required=True, help="bar arg")
    parser.add_argument("-i","--ipsum", dest="ipsum", action="store_true", help="ipsum arg")
    args = parser.parse_args()
    print(args)
    parser.write_config(args,"examples/config1_out.py")
