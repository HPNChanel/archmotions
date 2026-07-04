"""Line + arrow primitives for the geometry domain."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from archmotion.core.vmobject import VMobject

if TYPE_CHECKING:
    from archmotion._types import Point

DEFAULT_ARROW_SIZE = 14.0


def _direction(start: Point, end: Point) -> tuple[float, float, float]:
    """Return (ux, uy, length) unit vector + length from start to end."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return 1.0, 0.0, 0.0
    return dx / length, dy / length, length


class Arrow(VMobject):
    """A line segment ending in a V-shaped arrowhead."""

    def __init__(
        self,
        start: Point,
        end: Point,
        *,
        tip_size: float = DEFAULT_ARROW_SIZE,
    ) -> None:
        """Store endpoints + tip size, then generate points."""
        self.start = start
        self.end = end
        self.tip_size = tip_size
        super().__init__()

    def generate_points(self) -> None:
        """Trace the shaft then a two-wing arrowhead (single open path)."""
        start, end = self.start, self.end
        ux, uy, _ = _direction(start, end)
        size = self.tip_size
        # The shaft stops short of the tip so the head sits cleanly.
        base = (end[0] - ux * size, end[1] - uy * size)
        # Perpendicular direction for the wings.
        px, py = -uy, ux
        wing1 = (base[0] + px * size * 0.5, base[1] + py * size * 0.5)
        wing2 = (base[0] - px * size * 0.5, base[1] - py * size * 0.5)
        self.start_new_path(start)
        self.add_line_to(end)
        self.add_line_to(wing1)
        self.add_line_to(end)
        self.add_line_to(wing2)


class DoubleArrow(Arrow):
    """A line with arrowheads at both ends."""

    def generate_points(self) -> None:
        """Trace shaft + heads at both ends."""
        Arrow.generate_points(self)
        start, end = self.start, self.end
        ux, uy, _ = _direction(end, start)  # direction toward start
        size = self.tip_size
        base = (start[0] - ux * size, start[1] - uy * size)
        px, py = -uy, ux
        wing1 = (base[0] + px * size * 0.5, base[1] + py * size * 0.5)
        wing2 = (base[0] - px * size * 0.5, base[1] - py * size * 0.5)
        self.add_line_to(start)
        self.add_line_to(wing1)
        self.add_line_to(start)
        self.add_line_to(wing2)


class DashedLine(VMobject):
    """A line rendered as alternating dash/gap segments."""

    def __init__(
        self,
        start: Point,
        end: Point,
        *,
        dash_length: float = 10.0,
        gap: float = 6.0,
    ) -> None:
        """Store endpoints + dash pattern, then generate points."""
        self.start = start
        self.end = end
        self.dash_length = dash_length
        self.gap = gap
        super().__init__()

    def generate_points(self) -> None:
        """Emit one open contour per dash along the segment."""
        start, end = self.start, self.end
        ux, uy, length = _direction(start, end)
        if length < 1e-9:
            return
        step = self.dash_length + self.gap
        traveled = 0.0
        while traveled < length:
            dash_start = traveled
            dash_end = min(traveled + self.dash_length, length)
            p0 = (start[0] + ux * dash_start, start[1] + uy * dash_start)
            p1 = (start[0] + ux * dash_end, start[1] + uy * dash_end)
            self.start_new_path(p0)
            self.add_line_to(p1)
            traveled += step
