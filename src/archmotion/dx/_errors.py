"""Rich error formatting for ArchMotion exceptions.

Architectural Note:
    Errors in ArchMotion carry structured context (phase, object IDs,
    suggested fixes). This module formats them into beautiful Rich panels
    with color-coded severity, location breadcrumbs, and actionable hints.

    When ``rich`` is unavailable, falls back to plain-text formatting.

Usage:
    >>> try:
    ...     scene.render()
    ... except ArchMotionError as exc:
    ...     print_error(exc)
"""

from __future__ import annotations

import sys
import traceback
from typing import TextIO

from archmotion.errors import (
    ArchMotionError,
    CircularReferenceError,
    DuplicateIdError,
    EmptyTimelineError,
    FFmpegCrashError,
    FFmpegNotFoundError,
    InvalidConnectionError,
    LayoutError,
    OrphanNodeError,
    OverflowCanvasError,
    RenderError,
    SkiaAllocationError,
    TimelineError,
    TopologyError,
)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


# ──────────────────────────────────────────────
# Phase Detection
# ──────────────────────────────────────────────

_PHASE_MAP: dict[type, tuple[str, str, str]] = {
    # (phase_label, color, emoji)
    TopologyError: ("Phase 1 — Topology", "red", "🔴"),
    DuplicateIdError: ("Phase 1 — Topology", "red", "🔴"),
    CircularReferenceError: ("Phase 1 — Topology", "red", "🔴"),
    InvalidConnectionError: ("Phase 1 — Topology", "red", "🔴"),
    LayoutError: ("Phase 2 — Layout", "yellow", "🟡"),
    OverflowCanvasError: ("Phase 2 — Layout", "yellow", "🟡"),
    OrphanNodeError: ("Phase 2 — Layout", "yellow", "🟡"),
    TimelineError: ("Phase 3 — Timeline", "blue", "🔵"),
    EmptyTimelineError: ("Phase 3 — Timeline", "blue", "🔵"),
    RenderError: ("Phase 4 — Render", "magenta", "🟣"),
    FFmpegNotFoundError: ("Phase 4 — Render", "magenta", "🟣"),
    FFmpegCrashError: ("Phase 4 — Render", "magenta", "🟣"),
    SkiaAllocationError: ("Phase 4 — Render", "magenta", "🟣"),
}

# ──────────────────────────────────────────────
# Suggested Fixes
# ──────────────────────────────────────────────

_FIX_SUGGESTIONS: dict[type, str] = {
    DuplicateIdError: "Ensure all Node and Connection IDs are unique.",
    CircularReferenceError: (
        "Break the positioning cycle by removing one .right_of()/.below() call."
    ),
    InvalidConnectionError: "Check that connection source and target are valid Node instances.",
    OverflowCanvasError: "Reduce node count, decrease distances, or use a higher resolution.",
    OrphanNodeError: (
        "Position all nodes using .right_of()/.below() etc., or let auto-layout handle it."
    ),
    EmptyTimelineError: "Add at least one scene.play() call before scene.render().",
    FFmpegNotFoundError: "Install FFmpeg: https://ffmpeg.org/download.html — ensure it's on PATH.",
    FFmpegCrashError: "Check FFmpeg logs. Try a different encoder or reduce resolution.",
    SkiaAllocationError: "Reduce canvas resolution or close other applications to free memory.",
}


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def format_error(exc: Exception) -> str:
    """Format an exception into a structured error report.

    Returns a multi-line string with:
        - Error type and phase identification
        - Error message
        - Suggested fix (if available)
        - Traceback (condensed)

    Args:
        exc: The exception to format.

    Returns:
        Formatted error string (plain-text, suitable for logging).
    """
    exc_type = type(exc)
    phase_label, _, emoji = _PHASE_MAP.get(exc_type, ("Unknown Phase", "white", "⚪"))

    lines: list[str] = []
    lines.append(f"{emoji} ArchMotion Error — {phase_label}")
    lines.append(f"   Type: {exc_type.__name__}")
    lines.append(f"   Message: {exc}")

    # Object-specific context
    if isinstance(exc, DuplicateIdError):
        lines.append(f"   Object ID: {exc.object_id}")

    # Suggested fix
    fix = _FIX_SUGGESTIONS.get(exc_type)
    if fix:
        lines.append(f"   💡 Fix: {fix}")

    return "\n".join(lines)


def print_error(
    exc: Exception,
    file: TextIO = sys.stderr,
    show_traceback: bool = False,
) -> None:
    """Pretty-print an exception using Rich (or plain-text fallback).

    Args:
        exc: The exception to display.
        file: Output stream (default: stderr).
        show_traceback: If True, include the full traceback.
    """
    if _HAS_RICH and isinstance(exc, ArchMotionError):
        _print_rich_error(exc, show_traceback=show_traceback)
    else:
        # Plain-text fallback
        report = format_error(exc)
        print(report, file=file)
        if show_traceback:
            traceback.print_exc(file=file)


def _print_rich_error(exc: ArchMotionError, show_traceback: bool = False) -> None:
    """Render a Rich-formatted error panel to stderr."""
    console = Console(stderr=True)
    exc_type = type(exc)
    phase_label, color, emoji = _PHASE_MAP.get(exc_type, ("Unknown", "white", "⚪"))

    # Build title
    title = f"{emoji} {phase_label}"

    # Build body
    body = Text()
    body.append("Error: ", style="bold red")
    body.append(f"{exc_type.__name__}\n", style="bold")
    body.append("Message: ", style="bold")
    body.append(f"{exc}\n", style="dim")

    # Object context
    if isinstance(exc, DuplicateIdError):
        body.append("Object ID: ", style="bold")
        body.append(f"{exc.object_id}\n", style="cyan")

    # Suggested fix
    fix = _FIX_SUGGESTIONS.get(exc_type)
    if fix:
        body.append("\n💡 Suggested Fix: ", style="bold green")
        body.append(fix, style="green")

    panel = Panel(
        body,
        title=title,
        title_align="left",
        border_style=color,
        padding=(1, 2),
    )
    console.print(panel)

    if show_traceback:
        console.print_exception()
