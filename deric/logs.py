import logging

from rich.console import Console
from rich.logging import RichHandler


# rich console to import if needed
console = Console()


def setup_logging(logfile: str | None):
    """Setup logging, with logfile in data dir and rich console output."""
    # format = "%(asctime)s %(levelname)-1.1s %(message)s"
    format = "%(asctime)s %(message)s"
    handlers: list[logging.Handler] = [
        RichHandler(show_time=False, show_level=True),
    ]
    if logfile:
        handlers.append(logging.FileHandler(logfile))

    logging.basicConfig(
        level="NOTSET",
        format=format,
        datefmt="[%X]",
        handlers=handlers,
    )
