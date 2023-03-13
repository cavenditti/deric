from deric import Command, arg

# define a simple app
class SimpleApp(Command):
  name = "your simple app"
  description = "Print a value and exit"

  class Config:
    string: str = arg(..., "value to print")
    value: int = arg(4, "value to print")

  def run(self, config):
    print(config.string, config.value * 2)

# then run it
SimpleApp().start()
