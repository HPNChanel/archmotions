"""ArchMotion Global Constants.

Architectural Note:
    All magic numbers live here. No module is allowed to hardcode
    pixel values, grid sizes, or default durations inline.
    Import from this module instead.
"""

from __future__ import annotations

# ──────────────────────────────────────────────
# Canvas & Resolution
# ──────────────────────────────────────────────

RESOLUTION_MAP: dict[str, tuple[int, int]] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
}
"""Maps resolution preset names to (width, height) in pixels."""

DEFAULT_RESOLUTION: str = "1080p"
DEFAULT_FPS: int = 60

# ──────────────────────────────────────────────
# Layout Grid System
# ──────────────────────────────────────────────

GRID_UNIT: float = 80.0
"""Base unit for relative positioning (1 distance unit = 80 pixels)."""

DEFAULT_DISTANCE: float = 3.0
"""Default distance between nodes when not specified (in grid units)."""

# ──────────────────────────────────────────────
# Node Geometry
# ──────────────────────────────────────────────

NODE_PADDING_H: float = 24.0
"""Horizontal padding inside a Node (pixels). Applied to each side."""

NODE_PADDING_V: float = 16.0
"""Vertical padding inside a Node (pixels). Applied to top and bottom."""

NODE_CORNER_RADIUS: float = 8.0
"""Default corner radius for rounded rectangle Nodes (pixels)."""

NODE_BORDER_WIDTH: float = 2.0
"""Default border stroke width for Nodes (pixels)."""

# ──────────────────────────────────────────────
# Connection Geometry
# ──────────────────────────────────────────────

ARROW_SIZE: float = 10.0
"""Default arrow head size for Connection endpoints (pixels)."""

CONNECTION_STROKE_WIDTH: float = 2.0
"""Default stroke width for Connection lines (pixels)."""

ROUTING_THRESHOLD: float = 5.0
"""Pixel tolerance for 'same row/column' detection in Manhattan routing."""

# ──────────────────────────────────────────────
# Typography
# ──────────────────────────────────────────────

DEFAULT_FONT_FAMILY: str = "Fira Code"
"""Default monospace font for Node labels and payload text."""

DEFAULT_FONT_SIZE: float = 14.0
"""Default font size for Node labels (points)."""

PACKET_LABEL_FONT_SIZE: float = 10.0
"""Font size for Transfer packet labels (points)."""

# ──────────────────────────────────────────────
# Animation Defaults
# ──────────────────────────────────────────────

DEFAULT_FADE_DURATION: float = 0.5
"""Default duration for FadeIn/FadeOut animations (seconds)."""

DEFAULT_TRANSFER_DURATION: float = 1.0
"""Default duration for Transfer animations (seconds)."""

DEFAULT_PULSE_DURATION: float = 0.5
"""Default duration for Pulse animations (seconds)."""

DEFAULT_PULSE_INTENSITY: float = 0.8
"""Default glow intensity for Pulse animations (0.0-1.0)."""

DEFAULT_HIGHLIGHT_DURATION: float = 1.0
"""Default duration for Highlight animations (seconds)."""

DEFAULT_COLORSHIFT_DURATION: float = 0.8
"""Default duration for ColorShift animations (seconds)."""

DEFAULT_SCALE_DURATION: float = 0.5
"""Default duration for ScaleUp/ScaleDown animations (seconds)."""

DEFAULT_SCALE_FACTOR: float = 1.3
"""Default scale factor for ScaleUp animations."""

MIN_SCALE_FACTOR: float = 0.1
"""Minimum allowed scale factor."""

MAX_SCALE_FACTOR: float = 3.0
"""Maximum allowed scale factor."""

DEFAULT_ANNOTATION_DURATION: float = 2.0
"""Default duration for Annotation text callouts (seconds)."""

MIN_DURATION: float = 0.1
"""Minimum allowed animation duration (seconds)."""

MAX_DURATION: float = 60.0
"""Maximum allowed animation duration (seconds)."""

# ──────────────────────────────────────────────
# Packet Geometry
# ──────────────────────────────────────────────

PACKET_SIZE: float = 12.0
"""Default diameter for Packet circles (pixels)."""

# ──────────────────────────────────────────────
# Z-Index Layers (Painter's Algorithm)
# ──────────────────────────────────────────────

Z_BACKGROUND: int = 0
"""Z-index for the background layer."""

Z_CONNECTION: int = 10
"""Z-index for connection lines (drawn below nodes)."""

Z_NODE: int = 20
"""Z-index for nodes and databases."""

Z_LABEL: int = 30
"""Z-index for text labels."""

Z_EFFECT: int = 40
"""Z-index for packets, glow effects, and overlays."""

# ──────────────────────────────────────────────
# Rendering Pipeline
# ──────────────────────────────────────────────

WORKER_RATIO: float = 0.75
"""Fraction of available CPU cores to use for multiprocessing render pool."""

MAX_WORKERS: int = 14
"""Absolute cap on worker count (leave room for OS + FFmpeg)."""

FFMPEG_PIPE_TIMEOUT: int = 30
"""Timeout (seconds) when waiting for FFmpeg subprocess to finish."""

# ──────────────────────────────────────────────
# Validation Limits
# ──────────────────────────────────────────────

MAX_LABEL_LENGTH: int = 50
"""Maximum character length for Node labels."""

MAX_PAYLOAD_LENGTH: int = 20
"""Maximum character length for Transfer payload text."""

MAX_CONNECTION_LABEL_LENGTH: int = 30
"""Maximum character length for Connection labels."""

MAX_NODES: int = 50
"""Maximum number of Nodes in a single Scene (MVP limit)."""

MAX_CONNECTIONS: int = 100
"""Maximum number of Connections in a single Scene (MVP limit)."""

MIN_DISTANCE: float = 1.0
"""Minimum positioning distance (grid units)."""

MAX_DISTANCE: float = 20.0
"""Maximum positioning distance (grid units)."""
