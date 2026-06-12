"""Bounding Box calculation using font metrics.

Phase 2 responsibility: Given a Node's label text and font config,
compute the minimum bounding rectangle in pixels.
"""

from __future__ import annotations

from dataclasses import dataclass

from archmotion.constants import (
    DEFAULT_FONT_SIZE,
    NODE_PADDING_H,
    NODE_PADDING_V,
)


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned bounding rectangle in absolute pixel coordinates.

    Attributes:
        x: Left edge X coordinate.
        y: Top edge Y coordinate.
        width: Box width in pixels.
        height: Box height in pixels.
    """

    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> tuple[float, float]:
        """Center point of the bounding box."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def right_anchor(self) -> tuple[float, float]:
        """Midpoint of the right edge (for outgoing horizontal connections)."""
        return (self.x + self.width, self.y + self.height / 2)

    @property
    def left_anchor(self) -> tuple[float, float]:
        """Midpoint of the left edge (for incoming horizontal connections)."""
        return (self.x, self.y + self.height / 2)

    @property
    def top_anchor(self) -> tuple[float, float]:
        """Midpoint of the top edge (for incoming vertical connections)."""
        return (self.x + self.width / 2, self.y)

    @property
    def bottom_anchor(self) -> tuple[float, float]:
        """Midpoint of the bottom edge (for outgoing vertical connections)."""
        return (self.x + self.width / 2, self.y + self.height)


def estimate_text_bbox(
    text: str,
    font_size: float = DEFAULT_FONT_SIZE,
    padding_h: float = NODE_PADDING_H,
    padding_v: float = NODE_PADDING_V,
) -> tuple[float, float]:
    """Estimate the bounding box size for a text label.

    Uses a monospace font metric approximation (0.6 × font_size per character).
    Phase 4 (Skia) will compute exact metrics; this is for layout estimation.

    Args:
        text: The label text.
        font_size: Font size in points.
        padding_h: Horizontal padding (each side).
        padding_v: Vertical padding (top and bottom).

    Returns:
        Tuple of (width, height) in pixels.
    """
    char_width = font_size * 0.6  # Monospace approximation
    text_width = len(text) * char_width
    text_height = font_size * 1.2  # Line height

    box_width = text_width + 2 * padding_h
    box_height = text_height + 2 * padding_v

    return (box_width, box_height)
