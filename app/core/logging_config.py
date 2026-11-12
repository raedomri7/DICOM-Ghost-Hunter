"""Structured logging configuration for DICOM Ghost Hunter.

Patient identifiers are never written to logs. Logs are written to a rotating
file under data/logs/ and to the console.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from config.settings import settings

_LOGGER_NAME = "dicom_ghost_hunter"


def configure_logging(log_level: str | None = None, log_file: Path | None = None) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        log_level: Logging level name (e.g. "INFO", "DEBUG"). Defaults to settings.
        log_file: Path to the log file. Defaults to settings.log_file.

    Returns:
        The configured application logger.
    """
    level = getattr(logging, (log_level or settings.log_level).upper(), logging.INFO)
    log_file = log_file or settings.log_file

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Logging to file is best-effort; console logging remains available.
        logger.warning("Could not configure file logging at %s", log_file)

    return logger


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Return a logger for the given module name."""
    return logging.getLogger(name)
