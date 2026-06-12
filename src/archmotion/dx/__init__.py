"""Developer Experience (DX) utilities — Rich progress, error formatting, logging.

Architectural Note:
    This package provides optional DX enhancements that are activated
    automatically when `rich` is available. All components degrade
    gracefully: if `rich` is not installed, plain-text fallbacks are used.

    Components:
        - RenderProgress: Rich progress bar for frame rendering
        - format_error(): Pretty-print ArchMotion exceptions
        - setup_logging(): Structured logging configuration
"""

from __future__ import annotations

from archmotion.dx._progress import RenderProgress, create_progress_callback
from archmotion.dx._errors import format_error, print_error
from archmotion.dx._logging import setup_logging

__all__ = [
    "RenderProgress",
    "create_progress_callback",
    "format_error",
    "print_error",
    "setup_logging",
]
