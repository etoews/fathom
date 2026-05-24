"""Logging setup.

Call `configure()` once from the CLI entry. Library code never configures
logging; it just uses module-level loggers and lets the application route.
"""

import logging
import sys


def configure(level: str = "INFO") -> None:
    """Configure root logging for CLI use.

    Args:
        level: Standard logging level name (DEBUG, INFO, WARNING, ERROR).
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
