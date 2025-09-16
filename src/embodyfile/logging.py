"""Logging utilities for the embodyfile library."""

import logging
from collections.abc import Callable

# Library root logger name
LIBRARY_LOGGER_NAME = "embodyfile"


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger for the library."""
    if name:
        return logging.getLogger(f"{LIBRARY_LOGGER_NAME}.{name}")
    return logging.getLogger(LIBRARY_LOGGER_NAME)


def configure_library_logging(
    level: int = logging.INFO, format_string: str | None = None, datefmt: str | None = None
) -> None:
    """Configure library logging (primarily for CLI use)."""
    logger = logging.getLogger(LIBRARY_LOGGER_NAME)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()

        if format_string:
            formatter = logging.Formatter(format_string, datefmt=datefmt)
            handler.setFormatter(formatter)

        logger.addHandler(handler)

    logger.propagate = False


def log_debug_lazy(logger: logging.Logger, msg_func: Callable[[], str]) -> None:
    """Log debug message with lazy evaluation."""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(msg_func())


def log_info_lazy(logger: logging.Logger, msg_func: Callable[[], str]) -> None:
    """Log info message with lazy evaluation."""
    if logger.isEnabledFor(logging.INFO):
        logger.info(msg_func())


def log_warning_lazy(logger: logging.Logger, msg_func: Callable[[], str]) -> None:
    """Log warning message with lazy evaluation."""
    if logger.isEnabledFor(logging.WARNING):
        logger.warning(msg_func())
