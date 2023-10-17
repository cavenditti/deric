# deric — DEclarative RIch Cli

Minimal library to build CLI apps with integrated TOML config file.

## Goals
- Minimal and useful
- Subcommand support
- Type checked arguments
- Integrated logging handling
- Reuse existing proved libraries: pydantic and rich
- Use either CLI args, environment variables or TOML configuration (or a mix of them)

## Usage
`simple_app.py`:
```python
from deric import Command, arg

# define a simple app
class SimpleApp(Command):
  name = "your_simple_app"
  description = "Print a value and exit"

  Config = {
    "string": arg(str, ..., "value to print")
    "value": arg(int, 4, "value to print")
  }

  def run(self, config):
    print(config.string, config.value * 2)

SimpleApp().start()
```

Run it with:
```sh
python simple_app.py --string "some string" --value 21
```
