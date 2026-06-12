"""Structured logging configuration for ArchMotion.

Architectural Note:
    Uses Python's standard ``logging`` module with Rich handler when
    available. Log levels are mapped to pipeline phases:

        DEBUG   — Internal rendering details (frame-by-frame)
        INFO    — Phase transitions, completion summaries
        WARNING — Recoverable issues (font fallback, encoder fallback)
        ERROR   — Non-recoverable failures

    Logging is opt-in: call ``setup_logging()`` once at program start.
    If never called, ArchMotion produces no log output (zero noise).

Usage:
    >>> from archmotion.dx import setup_logging
    >>> setup_logging(level="DEBUG")  # Enable verbose logging
"""

from __future__ import annotations

import logging
import sys

try:
    from rich.logging import RichHandler

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

# Package-level logger name
_LOGGER_NAME = "archmotion"


def setup_logging(
    level: str = "INFO",
    *,
    use_rich: bool = True,
    log_file: str | None = None,
) -> logging.Logger:
    """Configure structured logging for the ArchMotion library.

    This should be called once at application startup. Subsequent calls
    will reconfigure the existing logger.

    Args:
        level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR').
        use_rich: If True and ``rich`` is installed, use RichHandler.
        log_file: Optional file path for log output (in addition to stderr).

    Returns:
        The configured root logger for ``archmotion``.

    Example:
        >>> logger = setup_logging(level="DEBUG")
        >>> logger.info("ArchMotion initialized")
    """
    logger = logging.getLogger(_LOGGER_NAME)

    # Clear existing handlers to allow reconfiguration
    logger.handlers.clear()

    # Set level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Console handler
    if use_rich and _HAS_RICH:
        console_handler = RichHandler(
            level=numeric_level,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
        console_handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        console_handler = logging.StreamHandler(sys.stderr)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(fmt)

    console_handler.setLevel(numeric_level)
    logger.addHandler(console_handler)

    # Optional file handler
    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        file_handler.setLevel(numeric_level)
        logger.addHandler(file_handler)

    # Don't propagate to root logger
    logger.propagate = False

    return logger


def get_logger(name: str = "") -> logging.Logger:
    """Get a child logger within the ``archmotion`` namespace.

    Args:
        name: Optional sub-name (e.g., 'renderer', 'exporter').

    Returns:
        A Logger instance under ``archmotion.{name}``.

    Example:
        >>> log = get_logger("renderer")
        >>> log.debug("Rendering frame %d", frame_idx)
    """
    if name:
        return logging.getLogger(f"{_LOGGER_NAME}.{name}")
    return logging.getLogger(_LOGGER_NAME)
