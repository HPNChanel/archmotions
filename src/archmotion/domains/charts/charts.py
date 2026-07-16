"""Charts domain: data-driven vector charts built as VMobject point arrays.

Each chart (BarChart, LineChart, PieChart) generates its own Bezier point array
from input data, so a chart can be ``Transform``-morphed into any other shape —
the multi-domain fusion in action.

Coordinate space is pixels, top-left origin, y-down. ``baseline_y`` is the chart
floor; positive values grow upward (toward smaller y).
"""

from __future__ import annotations

import math
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
        self.values = _validated_values(values)
        if bar_width <= 0 or gap < 0 or height <= 0:
            raise ValueError("bar_width and height must be positive; gap cannot be negative")
        self.bar_width = bar_width
        self.gap = gap
        self.height = height
        self.origin = origin
        auto_max = max((abs(value) for value in self.values), default=1.0)
        self.max_value = max_value if max_value is not None else auto_max
        if not math.isfinite(self.max_value) or self.max_value <= 0:
            raise ValueError("max_value must be a positive finite number")
        super().__init__()

    def generate_points(self) -> None:
        """Emit one closed rectangle per bar, side by side from the origin."""
        if not self.values:
            return
        ox, oy = self.origin
        step = self.bar_width + self.gap
        for i, value in enumerate(self.values):
            frac = value / self.max_value if self.max_value else 0.0
            bar_h = frac * self.height
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
        self.values = _validated_values(values)
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        self.width = width
        self.height = height
        self.origin = origin
        auto_max = max((abs(value) for value in self.values), default=1.0)
        self.max_value = max_value if max_value is not None else auto_max
        if not math.isfinite(self.max_value) or self.max_value <= 0:
            raise ValueError("max_value must be a positive finite number")
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
        self.values = _validated_values(values)
        if any(value < 0 for value in self.values):
            raise ValueError("pie chart values cannot be negative")
        if radius <= 0:
            raise ValueError("radius must be positive")
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


class ScatterPlot(VMobject):
    """A scatter plot — one dot per ``(x, y)`` data point on an implicit grid.

    The data range is auto-computed (or overridden) and mapped to pixel space.
    Each data point becomes a small filled circle contour.
    """

    def __init__(
        self,
        points: Sequence[tuple[float, float]],
        *,
        x_range: tuple[float, float] | None = None,
        y_range: tuple[float, float] | None = None,
        width: float = 200.0,
        height: float = 150.0,
        origin: Point = (0.0, 0.0),
        dot_radius: float = 5.0,
    ) -> None:
        """Store data + geometry, then generate the dot contours."""
        self.data_points = [(float(x), float(y)) for x, y in points]
        if any(not math.isfinite(value) for point in self.data_points for value in point):
            raise ValueError("scatter plot points must be finite")
        if width <= 0 or height <= 0 or dot_radius <= 0:
            raise ValueError("width, height, and dot_radius must be positive")
        self._x_range = x_range
        self._y_range = y_range
        self.width = width
        self.height = height
        self.origin = origin
        self.dot_radius = dot_radius
        super().__init__()

    def generate_points(self) -> None:
        """Map each data point to pixel space and emit a small circle."""
        if not self.data_points:
            return
        xs = [p[0] for p in self.data_points]
        ys = [p[1] for p in self.data_points]
        x_min, x_max = self._x_range or (min(xs), max(xs))
        y_min, y_max = self._y_range or (min(ys), max(ys))
        x_span = x_max - x_min if x_max > x_min else 1.0
        y_span = y_max - y_min if y_max > y_min else 1.0
        ox, oy = self.origin
        for dx, dy in self.data_points:
            px = ox + (dx - x_min) / x_span * self.width
            py = oy - (dy - y_min) / y_span * self.height
            self._emit_dot((px, py), self.dot_radius)

    def _emit_dot(self, center: Point, radius: float) -> None:
        """Append a filled circle contour at ``center``."""
        cx, cy = center
        self.start_new_path((cx + radius, cy))
        self.add_arc((cx, cy), radius, 0.0, 360.0)
        self.close_path()


def _validated_values(values: Sequence[float]) -> list[float]:
    """Coerce chart values to finite floats."""
    result = [float(value) for value in values]
    if any(not math.isfinite(value) for value in result):
        raise ValueError("chart values must be finite")
    return result
