import mock
import pytest

from deric import Command, arg


class Greet(Command):
    name = "greet"
    description = "Print 'Hello'"

    def run(self, config):
        print("Hello")


class Print(Command):
    name = "print"
    description = "Print a value"

    class Config:
        string: str = arg(..., "value to print")

    def run(self, config):
        print(config.print_string)


class Subsub(Command):
    name = "subsub"
    description = "Print 'I'm nested'"

    def run(self, config):
        print("I'm nested")


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

    subcommands = [Greet, Print, Nested]

    class Config:
        string: str = arg(..., "some value")

    def run(self, config):
        print("Runnig your_simple_app", config.string)


def test_subcommand_help(capsys):
    args = "main.py -h".split()
    with mock.patch("sys.argv", args):
        with pytest.raises(SystemExit):
            SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == (
"""usage: your_simple_app [-h] [--string STRING] {greet,print,nested} ...

Print a value and exit

options:
  -h, --help            show this help message and exit
  --string STRING       some value

your_simple_app_subcommand:
  valid subcommands

  {greet,print,nested}  addtional help
    greet               Print 'Hello'
    print               Print a value
    nested              Print 'nested'
"""
)


def test_subcommand(capsys):
    args = "main.py --string abc greet".split()
    with mock.patch("sys.argv", args):
        SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == "Runnig your_simple_app abc\nHello\n"


def test_subcommand_duplicated_arg(capsys):
    args = "main.py --string abc print --string 22".split()
    with mock.patch("sys.argv", args):
        SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == "Runnig your_simple_app abc\n22\n"


def test_subcommand_prevent_run():
    with pytest.raises(RuntimeError):
        Greet(is_subcommand=True).start()


def test_nested_subcommands(capsys):
    args = "main.py --string abc nested subsub".split()
    with mock.patch("sys.argv", args):
        SimpleApp().start()
    captured = capsys.readouterr()
    assert captured.out == "Runnig your_simple_app abc\nnested\nI'm nested\n"


