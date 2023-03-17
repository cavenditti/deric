import logging
import os

import mock
import pytest


@pytest.mark.skip(reason="`logfile` arg breaks pytest?")
def test_logging(tmp_path):
    from deric import Command

    # define a simple app
    class SimpleApp(Command):
      name = "your_simple_app"
      description = "Print a value and exit"

      def run(self, config):
          logging.error("some log")

    logfile = os.path.join(tmp_path, "test.log")
    args = f'main.py --set-logfile {logfile}'.split()
    with mock.patch('sys.argv', args):
        SimpleApp.with_logfile(default="test.log")().start()
    with open(logfile, 'r') as file:
        logtext = file.read()
    assert logtext == ("""""")
