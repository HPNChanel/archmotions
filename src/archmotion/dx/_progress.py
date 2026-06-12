"""Rich progress bar for render pipeline.

Architectural Note:
    RenderProgress wraps ``rich.progress.Progress`` into a context manager
    that plugs into the ``ProgressCallback`` protocol already used by
    ``export_video(on_progress=...)``.

    When ``rich`` is unavailable, a plain-text fallback prints percentage
    milestones to stderr (every 10%).

Usage:
    >>> with RenderProgress() as cb:
    ...     export_video(..., on_progress=cb)
"""

from __future__ import annotations

import sys
from typing import Protocol

try:
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


class ProgressCallback(Protocol):
    """Protocol for progress reporting callbacks."""

    def __call__(self, frames_done: int, total_frames: int) -> None: ...


class RenderProgress:
    """Context-managed Rich progress bar for frame rendering.

    Displays a live progress bar with:
        - Spinner + phase label
        - Progress bar with percentage
        - Frame counter (e.g., 120/300)
        - Elapsed time + ETA

    Falls back to plain-text milestones if ``rich`` is not installed.

    Example:
        >>> with RenderProgress() as callback:
        ...     scene.render(output="out.mp4", on_progress=callback)
    """

    def __init__(self, description: str = "Rendering") -> None:
        self._description = description
        self._progress: Progress | None = None
        self._task_id: object | None = None
        self._last_milestone: int = -1

    def __enter__(self) -> "ProgressCallback":
        """Start the progress display and return a callback function."""
        if _HAS_RICH:
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(bar_width=40),
                TaskProgressColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
            )
            self._progress.start()
            self._task_id = self._progress.add_task(
                self._description, total=None,
            )
        return self._callback

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Stop the progress display."""
        if self._progress is not None:
            self._progress.stop()
            self._progress = None

    def _callback(self, frames_done: int, total_frames: int) -> None:
        """Progress callback — updates the bar or prints milestones."""
        if self._progress is not None and self._task_id is not None:
            # Rich mode: update the live bar
            self._progress.update(
                self._task_id,
                completed=frames_done,
                total=total_frames,
            )
        else:
            # Fallback: print milestones every 10%
            if total_frames <= 0:
                return
            pct = int(frames_done / total_frames * 100)
            milestone = pct // 10
            if milestone > self._last_milestone:
                self._last_milestone = milestone
                print(
                    f"  Rendering: {pct}% ({frames_done}/{total_frames} frames)",
                    file=sys.stderr,
                )


def create_progress_callback(
    description: str = "Rendering",
) -> tuple["RenderProgress", "ProgressCallback"]:
    """Create a progress bar and its callback without context manager.

    Useful when you need to manually control the lifecycle.

    Returns:
        (progress_instance, callback_function)

    Example:
        >>> progress, cb = create_progress_callback()
        >>> progress.__enter__()  # start
        >>> export_video(..., on_progress=cb)
        >>> progress.__exit__(None, None, None)  # stop
    """
    rp = RenderProgress(description=description)
    return rp, rp._callback
