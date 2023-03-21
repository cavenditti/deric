import os
import mock
import pytest

from deric import Command, RuntimeConfig, arg


def test_simple_app_config(capsys, tmp_path):
    config_file = os.path.join(tmp_path, "config.toml")

    # define a simple app
    class SimpleApp(Command):
        name = "your_simple_app"
        description = "Print a value and exit"

        class Config:
            string: str = arg(..., "value to print")
            value: int = arg(7, "value to double and print")
            minus: bool = arg(False, "boolean to print")
            no_cli: int = arg(20, "not accessible from the cli", cli=False)
            config_file: str = arg(..., "config file path")

        def run(self, config):
            print(
                config.no_cli, config.string, config.value * (-2 if config.minus else 2)
            )

    with open(os.path.join(tmp_path, "config.toml"), "w") as file:
        file.write(
            """
string = "aaa"
value = 3
"""
        )

    args = f"main.py --config-file {config_file}".split()
    with mock.patch("sys.argv", args):
        SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == "20 aaa 6\n"


def test_runtime_config_to_dict():
    config = RuntimeConfig(
        x="2", y=23, z=RuntimeConfig(b="abc", c=RuntimeConfig(a="a"))
    )
    assert config.to_dict() == {
        "x": "2",
        "y": 23,
        "z": {
            "b": "abc",
            "c": {
                "a": "a",
            },
        },
    }


def test_subcommands_file_config(capsys, tmp_path):
    config_file = os.path.join(tmp_path, "config.toml")
    with open(os.path.join(tmp_path, "config.toml"), "w") as file:
        file.write(
            """
string = "wasd"

[nested.subsub]
nested_arg = "q"
"""
        )

    class Subsub(Command):
        name = "subsub"
        description = "Print 'I'm nested'"

        class Config:
            nested_arg: str = arg(..., "nested arg to print")
            unused: int = arg(12, "unused int", cli=False)

        def run(self, config):
            print("I'm nested,", config.nested.subsub.nested_arg)


    class Nested(Command):
        name = "nested"
        description = "Print 'nested'"

        subcommands = [Subsub]

        def run(self, config):
            print("nested")


    # define a simple app with a subcommand
    class SimpleApp(Command):
        name = "your_simple_app"
        description = "Print a value and exit"

        subcommands = [Nested]

        class Config:
            string: str = arg(..., "some value")
            unused: int = arg(99, "unused int", cli=False)
            config_file: str = arg("", "config file path")

        def run(self, config):
            print("Runnig your_simple_app", config.string)

    args = f"main.py --config-file {config_file} nested subsub".split()
    with mock.patch("sys.argv", args):
        SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == "Runnig your_simple_app wasd\nnested\nI'm nested, q\n"
