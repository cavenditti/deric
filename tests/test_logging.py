import logging
import os

import mock
import pytest


@pytest.mark.skip(reason="Not implemented yet")
def test_simple_app(tmp_path):
    from deric import Command, arg

    # define a simple app
    class SimpleApp(Command):
      name = "your_simple_app"
      description = "Print a value and exit"

      class Config:
        logfile: str = arg(..., "value to print")

      def run(self, config):
          logging.error("some log")

    logfile = os.path.join(tmp_path, "test.log")
    args = f'main.py --logfile {logfile}'.split()
    with mock.patch('sys.argv', args):
        SimpleApp().start()
    with open(logfile) as file:
        logtext = file.read()
    assert logtext == (
"""
"""
    )
