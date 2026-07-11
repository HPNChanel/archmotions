"""ArchMotion Exception Hierarchy.

Architectural Note:
    Every Phase in the 4-Phase Pipeline has its own exception subtree.
    Exceptions are designed for **graceful degradation**: recoverable errors
    are caught and retried internally; non-recoverable errors propagate
    with clear, actionable messages pointing the user to the exact object
    that caused the failure.

Exception Tree:
    ArchMotionError
    ├── TopologyError          (Phase 1)
    │   ├── DuplicateIdError
    │   ├── CircularReferenceError
    │   └── InvalidConnectionError
    ├── LayoutError            (Phase 2)
    │   ├── OverflowCanvasError
    │   └── OrphanNodeError
    ├── TimelineError          (Phase 3)
    │   └── EmptyTimelineError
    └── RenderError            (Phase 4)
        ├── FFmpegNotFoundError
        ├── FFmpegCrashError
        └── SkiaAllocationError
"""

from __future__ import annotations


class ArchMotionError(Exception):
    """Base exception for all ArchMotion errors.

    All framework-specific exceptions inherit from this class,
    allowing users to catch any ArchMotion error with a single handler.
    """


# ──────────────────────────────────────────────
# Phase 1: Topology Builder Errors
# ──────────────────────────────────────────────


class TopologyError(ArchMotionError):
    """Error in Phase 1 — SceneGraph construction is invalid."""


class DuplicateIdError(TopologyError):
    """Two SceneObjects share the same ID.

    Args:
        object_id: The duplicated identifier.
    """

    def __init__(self, object_id: str) -> None:
        self.object_id = object_id
        super().__init__(f"Duplicate object ID: '{object_id}'")


class CircularReferenceError(TopologyError):
    """Positional relationships form a cycle (A.right_of(B), B.right_of(A)).

    Args:
        cycle_path: List of node IDs forming the cycle.
    """

    def __init__(self, cycle_path: list[str]) -> None:
        self.cycle_path = cycle_path
        chain = " → ".join(cycle_path)
        super().__init__(f"Circular positioning reference detected: {chain}")


class InvalidConnectionError(TopologyError):
    """Connection references a non-existent node or is a self-loop."""


# ──────────────────────────────────────────────
# Phase 2: Layout Resolver Errors
# ──────────────────────────────────────────────


class LayoutError(ArchMotionError):
    """Error in Phase 2 — cannot compute absolute coordinates."""


class OverflowCanvasError(LayoutError):
    """The diagram exceeds canvas dimensions after layout resolution.

    Args:
        required_width: Computed width of the diagram (pixels).
        required_height: Computed height of the diagram (pixels).
        canvas_width: Available canvas width (pixels).
        canvas_height: Available canvas height (pixels).
    """

    def __init__(
        self,
        required_width: float,
        required_height: float,
        canvas_width: int,
        canvas_height: int,
    ) -> None:
        self.required_width = required_width
        self.required_height = required_height
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        super().__init__(
            f"Diagram ({required_width:.0f}×{required_height:.0f}px) exceeds "
            f"canvas ({canvas_width}×{canvas_height}px). "
            "Reduce node count or distance values."
        )


class OrphanNodeError(LayoutError):
    """Node has no anchor and is not a root — position cannot be determined.

    Args:
        node_label: Label of the orphaned node.
    """

    def __init__(self, node_label: str) -> None:
        self.node_label = node_label
        super().__init__(
            f"Node '{node_label}' has no position and is not a root anchor. "
            "Call .right_of(), .below(), .left_of(), or .above() to set its position."
        )


# ──────────────────────────────────────────────
# Phase 3: Timeline Compiler Errors
# ──────────────────────────────────────────────


class TimelineError(ArchMotionError):
    """Error in Phase 3 — timeline construction is invalid."""


class EmptyTimelineError(TimelineError):
    """No animations were recorded before render() was called."""

    def __init__(self) -> None:
        super().__init__(
            "No animations recorded. Call scene.play() at least once before scene.render()."
        )


# ──────────────────────────────────────────────
# Phase 4: Renderer & Exporter Errors
# ──────────────────────────────────────────────


class RenderError(ArchMotionError):
    """Error in Phase 4 — rendering or video export failed."""


class FFmpegNotFoundError(RenderError):
    """FFmpeg binary could not be located.

    The user needs to install imageio-ffmpeg or add FFmpeg to PATH.
    """

    def __init__(self) -> None:
        super().__init__(
            "FFmpeg not found. Install it with: pip install imageio-ffmpeg\n"
            "Or set the FFMPEG_BINARY environment variable."
        )


class FFmpegCrashError(RenderError):
    """FFmpeg subprocess exited with a non-zero return code.

    Args:
        returncode: The exit code from FFmpeg.
        stderr_output: Captured stderr from FFmpeg process.
    """

    def __init__(self, returncode: int, stderr_output: str) -> None:
        self.returncode = returncode
        self.stderr_output = stderr_output
        super().__init__(
            f"FFmpeg crashed with exit code {returncode}.\n"
            f"stderr: {stderr_output[:500]}"
        )


class SkiaAllocationError(RenderError):
    """Failed to allocate Skia Canvas or Surface (insufficient RAM or GPU resources).

    Args:
        width: Requested canvas width.
        height: Requested canvas height.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        super().__init__(
            f"Failed to allocate Skia Surface ({width}×{height}). "
            "Reduce resolution or free system memory."
        )
