import os
import mock
from pydantic import ValidationError
import pytest

from deric import Command, arg


def test_config_extra(capsys, tmp_path):
    config_file = os.path.join(tmp_path, "config.toml")

    # define a simple app
    class SimpleApp(Command):
        name = "your_simple_app"
        description = "Print a value and exit"

        Config = {
            "string": arg(str, ..., "value to print"),
            "config_file": arg(str, ..., "config file path"),
        }

        def run(self, config):
            # value is not specified in config but it's passed in the config
            print(
                config.string, config.value + 2
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
    assert captured.out == "aaa 5\n"




def test_config_extra_forbid(capsys, tmp_path):
    config_file = os.path.join(tmp_path, "config.toml")

    # define a simple app
    class SimpleApp(Command):
        name = "your_simple_app"
        description = "Print a value and exit"
        extra = "forbid"

        Config = {
            "string": arg(str, ..., "value to print"),
            "config_file": arg(str, ..., "config file path"),
        }

        def run(self, config):
            # value is not specified in config but it's passed in the config
            print(
                config.string, config.value + 2
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
        with pytest.raises(ValidationError):
            SimpleApp().start()
