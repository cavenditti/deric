import mock
from pydantic import ValidationError
import pytest

from deric import Command, arg

# define a simple app
class SimpleApp(Command):
  name = "your_simple_app"
  description = "Print a value and exit"

  class Config:
    string: str = arg(..., "value to print")
    value: int = arg(7, "value to double and print")
    minus: bool = arg(False, "boolean to print")
    no_cli: int = arg(20, "not accessible from the cli", cli=False)

  def run(self, config):
    print(config.no_cli, config.string, config.value * (-2 if config.minus else 2))


def test_simple_app(capsys):
    args = 'main.py --string abc --value 4 --minus'.split()
    with mock.patch('sys.argv', args):
        SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == "20 abc -8\n"


def test_simple_app_missing_arg():
    args = 'main.py --value 4 --minus'.split()
    with mock.patch('sys.argv', args):
        with pytest.raises(ValidationError):
            SimpleApp().start()


def test_simple_app_default(capsys):
    args = 'main.py --string abc'.split()
    with mock.patch('sys.argv', args):
        SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == "20 abc 14\n"


def test_simple_app_invalid(capsys):
    args = 'main.py --no-cli 32 --string abc'.split()
    with mock.patch('sys.argv', args):
        with pytest.raises(SystemExit):
            SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.err == (
"""usage: your_simple_app [-h] [--string STRING] [--value VALUE] [--minus]
your_simple_app: error: unrecognized arguments: --no-cli 32
"""
)


# define a simple app with no configuration
class SimpleAppNoConfig(Command):
  name = "your_simple_app"
  description = "Print a value and exit"

  def run(self, config):
    print("whatever")


def test_simple_app_no_config(capsys):
    args = 'main.py'.split()
    with mock.patch('sys.argv', args):
        SimpleAppNoConfig().start()
    captured = capsys.readouterr()
    assert captured.out == "whatever\n"