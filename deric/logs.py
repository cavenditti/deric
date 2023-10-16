import logging

from rich.console import Console
from rich.logging import RichHandler


# rich console to import if needed
console = Console()


def setup_logging(logfile: str):
    """Setup logging, with logfile in data dir and rich console output."""
    # format = "%(asctime)s %(levelname)-1.1s %(message)s"
    format = "%(asctime)s %(message)s"
    logging.basicConfig(
        level="NOTSET",
        format=format,
        datefmt="[%X]",
        handlers=[
            RichHandler(show_time=False, show_level=True),
            logging.FileHandler(logfile),
        ],
    )
