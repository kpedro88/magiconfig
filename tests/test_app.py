"""Decorator app layer: arguments(), shared(), app()."""
import pytest

import magiconfig
from conftest import help_heading, make_config

common = magiconfig.shared(
    verbose=dict(action="store_true", help="verbose output"),
    seed=dict(type=int, default=0, help="random seed"),
)


@magiconfig.app(prog="train")
@magiconfig.arguments(
    _parents=[common],
    lr=dict(type=float, default=0.1, help="learning rate"),
    epochs=dict(type=int, required=True, help="number of epochs"),
)
def train(lr, epochs, verbose, seed):
    """Train a model."""
    return dict(lr=lr, epochs=epochs, verbose=verbose, seed=seed)


def test_direct_call():
    assert train(lr=1, epochs=2, verbose=False, seed=3) == dict(lr=1, epochs=2, verbose=False, seed=3)
    assert train.Config._arguments.keys() == {"verbose", "seed", "lr", "epochs"}
    assert train.Config.__doc__.startswith("Train a model.\n\nArguments:\n    verbose: verbose output\n")


def test_main(tmp_path):
    assert train.main(["--epochs", "5"]) == dict(lr=0.1, epochs=5, verbose=False, seed=0)
    config = make_config(tmp_path / "cfg.py", epochs=3, lr=0.5, seed=7)
    assert train.main(["-C", str(config), "--seed", "1", "--verbose"]) == dict(lr=0.5, epochs=3, verbose=True, seed=1)
    named = make_config(tmp_path / "named.py", obj="run1", epochs=4)
    assert train.main(["-C", str(named), "--obj", "run1"])["epochs"] == 4
    with pytest.raises(SystemExit):
        train.main([])


def test_build_standalone():
    assert train.Config.build(magiconfig.MagiConfig(epochs=2)) == dict(lr=0.1, epochs=2, verbose=False, seed=0)


def test_help():
    help_text = train.parser.format_help()
    assert help_text.startswith(f"usage: train [-h] [-C CONFIG] [--obj OBJ]\n\nTrain a model.\n\n{help_heading()}\n")
    # the description is not repeated in the config section
    assert help_text.count("Train a model.") == 1
    for text in ("--lr LR", "learning rate", "--epochs EPOCHS", "--verbose", "--seed SEED", "--obj OBJ"):
        assert text in help_text


def test_app_without_arguments():
    @magiconfig.app()
    def hello():
        """Say hello."""
        return "hello"
    assert hello.main([]) == "hello"
