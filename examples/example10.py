import magiconfig

common = magiconfig.shared(
    verbose = dict(action="store_true", help="verbose output"),
)

@magiconfig.app()
@magiconfig.arguments(
    _parents = [common],
    name = dict(default="world", help="who to greet"),
    times = dict(type=int, default=1, help="number of greetings"),
)
def greet(name, times, verbose):
    """Greet someone."""
    if verbose: print(f"greeting {name} {times} time(s)")
    for _ in range(times):
        print(f"hello, {name}!")

if __name__=="__main__":
    greet.main()
