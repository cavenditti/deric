import logging
import os

import mock


def test_logging(tmp_path):
    from deric import Command

    # define a simple app
    class SimpleApp(Command):
        name = "your_simple_app"
        description = "Print a value and exit"

        def run(self, config):
            logging.error("some log")

    log_file = os.path.join(tmp_path, "test.log")
    args = f"main.py --log-file {log_file}".split()
    with mock.patch("sys.argv", args):
        SimpleApp.with_log_file(default="test.log")().start()
    with open(log_file, "r") as file:
        logtext = file.read()
    assert logtext == ("""""")
