from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    numeric = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric)
    h = logging.StreamHandler(sys.stderr)
    h.setLevel(numeric)
    h.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(h)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
