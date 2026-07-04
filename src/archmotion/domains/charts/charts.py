"""Charts domain: data-driven vector charts built as VMobject point arrays.

Each chart (BarChart, LineChart, PieChart) generates its own Bezier point array
from input data, so a chart can be ``Transform``-morphed into any other shape —
the multi-domain fusion in action.

Coordinate space is pixels, top-left origin, y-down. ``baseline_y`` is the chart
floor; positive values grow upward (toward smaller y).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.core.pathops import arc_triplets
from archmotion.core.vmobject import VMobject

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archmotion._types import Point


class BarChart(VMobject):
    """A vertical bar chart — one rectangle contour per value."""

    def __init__(
        self,
        values: Sequence[float],
        *,
        bar_width: float = 30.0,
        gap: float = 12.0,
        height: float = 150.0,
        origin: Point = (0.0, 0.0),
        max_value: float | None = None,
    ) -> None:
        """Store data + geometry, then generate the bar contours."""
        self.values = list(values)
        self.bar_width = bar_width
        self.gap = gap
        self.height = height
        self.origin = origin
        auto_max = max(self.values) if self.values else 1.0
        self.max_value = max_value if max_value is not None else auto_max
        super().__init__()

    def generate_points(self) -> None:
        """Emit one closed rectangle per bar, side by side from the origin."""
        if not self.values:
            return
        ox, oy = self.origin
        step = self.bar_width + self.gap
        for i, value in enumerate(self.values):
            frac = value / self.max_value if self.max_value else 0.0
            bar_h = max(0.0, frac) * self.height
            x = ox + i * step
            top = oy - bar_h
            self.start_new_path((x, oy))
            self.add_line_to((x + self.bar_width, oy))
            self.add_line_to((x + self.bar_width, top))
            self.add_line_to((x, top))
            self.close_path()


class LineChart(VMobject):
    """A line chart — a polyline through (index, value) sample points."""

    def __init__(
        self,
        values: Sequence[float],
        *,
        width: float = 200.0,
        height: float = 150.0,
        origin: Point = (0.0, 0.0),
        max_value: float | None = None,
    ) -> None:
        """Store data + geometry, then generate the polyline."""
        self.values = list(values)
        self.width = width
        self.height = height
        self.origin = origin
        auto_max = max(self.values) if self.values else 1.0
        self.max_value = max_value if max_value is not None else auto_max
        super().__init__()

    def generate_points(self) -> None:
        """Trace the data points left-to-right."""
        if len(self.values) < 2:
            return
        ox, oy = self.origin
        n = len(self.values)
        span = self.max_value or 1.0
        pts: list[Point] = []
        for i, value in enumerate(self.values):
            x = ox + (i / (n - 1)) * self.width
            y = oy - (value / span) * self.height
            pts.append((x, y))
        self.start_new_path(pts[0])
        for point in pts[1:]:
            self.add_line_to(point)


class PieChart(VMobject):
    """A pie chart — one wedge contour per value (proportional slices)."""

    def __init__(
        self,
        values: Sequence[float],
        *,
        radius: float = 60.0,
        center: Point = (0.0, 0.0),
        start_angle: float = -90.0,
    ) -> None:
        """Store data + geometry, then generate the wedge contours."""
        self.values = list(values)
        self.radius = radius
        self.center = center
        self.start_angle = start_angle
        super().__init__()

    def generate_points(self) -> None:
        """Emit one closed wedge per slice (center -> arc -> center)."""
        total = sum(self.values)
        if total <= 0:
            return
        cx, cy = self.center
        angle = self.start_angle
        for value in self.values:
            sweep = 360.0 * value / total
            start_pt, triplets = arc_triplets(self.center, self.radius, angle, sweep)
            # Move to center, line to arc start, arc, close back to center.
            self.start_new_path((cx, cy))
            self.add_line_to(start_pt)
            for triplet in triplets:
                self._pts.extend(triplet)
                self._last = triplet[2]
            self.add_line_to((cx, cy))
            self.close_path()
            angle += sweep
