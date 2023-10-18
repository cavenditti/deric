import mock
from pydantic import ValidationError
import pytest

from deric import Command, arg
from deric.types import EnumByName


class ExampleEnum(EnumByName):
    a = 123
    b = {1: "abc"}


# define a simple app
class SimpleApp(Command):
    name = "your_simple_app"
    description = "Print a value and exit"

    Config = {
        "value1": arg(ExampleEnum, ..., "ExampleEnum required value"),
        "value2": arg(
            ExampleEnum, ExampleEnum.a, "Optional ExampleEnum value with default value"
        ),
    }

    def run(self, config):
        assert isinstance(config.value2.value, int)
        print("value1:", config.value1, config.value1.name, config.value1.value)
        print("value2:", config.value2, config.value2.name, config.value2.value)


def test_enum_by_name(capsys):
    args = "main.py --value1 b".split()
    with mock.patch("sys.argv", args):
        SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == "value1: ExampleEnum.b b {1: 'abc'}\nvalue2: ExampleEnum.a a 123\n"


def test_enum_by_name_missing():
    args = "main.py --value1 123".split()
    with mock.patch("sys.argv", args):
        with pytest.raises(ValidationError):
            SimpleApp().start()
