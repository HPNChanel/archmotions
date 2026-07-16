"""Coordinate systems + function plotting for the geometry domain."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from archmotion.core.vmobject import VMobject

if TYPE_CHECKING:
    from archmotion._types import Point

    CoordFn = Callable[[float], Point]

GraphFn = Callable[[float], float]


class NumberLine(VMobject):
    """A horizontal number line with evenly-spaced ticks."""

    def __init__(
        self,
        x_range: tuple[float, float] = (-1.0, 1.0),
        *,
        length: float = 200.0,
        center: Point = (0.0, 0.0),
        tick_step: float | None = None,
        tick_size: float = 5.0,
        direction: str = "x",
    ) -> None:
        """Store range/geometry, then generate points."""
        _validate_range(x_range, "x_range")
        if length <= 0:
            raise ValueError("length must be positive")
        if tick_size < 0:
            raise ValueError("tick_size must be non-negative")
        if direction not in {"x", "y"}:
            raise ValueError("direction must be 'x' or 'y'")
        self.x_range = x_range
        self.length = length
        self.center = center
        self.tick_step = tick_step if tick_step is not None else _nice_step(x_range)
        if self.tick_step <= 0:
            raise ValueError("tick_step must be positive")
        self.tick_size = tick_size
        self.direction = direction
        super().__init__()

    def generate_points(self) -> None:
        """Draw the main segment plus perpendicular tick marks."""
        cx, cy = self.center
        x0, x1 = self.x_range
        span = x1 - x0
        if span == 0:
            return
        if self.direction == "x":
            start = (cx - self.length / 2.0, cy)
            end = (cx + self.length / 2.0, cy)
            tick_axis = (0.0, 1.0)
        else:
            # Data y increases upward while canvas y increases downward.
            start = (cx, cy + self.length / 2.0)
            end = (cx, cy - self.length / 2.0)
            tick_axis = (1.0, 0.0)
        self.start_new_path(start)
        self.add_line_to(end)
        # Ticks.
        t = math.ceil(x0 / self.tick_step) * self.tick_step
        while t <= x1 + 1e-9:
            frac = (t - x0) / span
            if self.direction == "x":
                px = start[0] + frac * (end[0] - start[0])
                py = cy
            else:
                px = cx
                py = start[1] + frac * (end[1] - start[1])
            tx = tick_axis[0] * self.tick_size
            ty = tick_axis[1] * self.tick_size
            self.start_new_path((px - tx, py - ty))
            self.add_line_to((px + tx, py + ty))
            t += self.tick_step

    def number_to_point(self, value: float) -> Point:
        """Map a data value to its pixel position on the line."""
        cx, cy = self.center
        x0, x1 = self.x_range
        frac = (value - x0) / (x1 - x0) if x1 != x0 else 0.0
        if self.direction == "x":
            return (cx - self.length / 2.0 + frac * self.length, cy)
        return (cx, cy + self.length / 2.0 - frac * self.length)


class Axes(VMobject):
    """A pair of perpendicular number lines forming a coordinate frame."""

    def __init__(
        self,
        x_range: tuple[float, float] = (-1.0, 1.0),
        y_range: tuple[float, float] = (-1.0, 1.0),
        *,
        x_length: float = 300.0,
        y_length: float = 300.0,
        center: Point = (0.0, 0.0),
        tick_step: float | None = None,
    ) -> None:
        """Store ranges/lengths, then generate the two axes as children."""
        _validate_range(x_range, "x_range")
        _validate_range(y_range, "y_range")
        if x_length <= 0 or y_length <= 0:
            raise ValueError("axis lengths must be positive")
        self.x_range = x_range
        self.y_range = y_range
        self.x_length = x_length
        self.y_length = y_length
        self.center = center
        self.tick_step = tick_step
        super().__init__()
        zero_x = min(max(0.0, x_range[0]), x_range[1])
        zero_y = min(max(0.0, y_range[0]), y_range[1])
        y_axis_x, x_axis_y = self._c2p_local(zero_x, zero_y)
        self._x_axis = NumberLine(
            x_range,
            length=x_length,
            center=(center[0], x_axis_y),
            tick_step=tick_step,
            direction="x",
        )
        self._y_axis = NumberLine(
            y_range,
            length=y_length,
            center=(y_axis_x, center[1]),
            tick_step=tick_step,
            direction="y",
        )
        self.add(self._x_axis, self._y_axis)

    def generate_points(self) -> None:
        """No own points — children carry the geometry."""

    def c2p(self, x: float, y: float) -> Point:
        """Map data coordinates (x, y) to pixel coordinates."""
        return self.world_transform().apply_to_point(self._c2p_local(x, y))

    def _c2p_local(self, x: float, y: float) -> Point:
        """Map data coordinates into this axes' untransformed local space."""
        cx, cy = self.center
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        fx = (x - x0) / (x1 - x0) if x1 != x0 else 0.5
        fy = (y - y0) / (y1 - y0) if y1 != y0 else 0.5
        px = cx - self.x_length / 2.0 + fx * self.x_length
        # Data y-up -> pixel y-down.
        py = cy + self.y_length / 2.0 - fy * self.y_length
        return (px, py)

    coords_to_point = c2p

    def p2c(self, point: Point) -> tuple[float, float]:
        """Map a canvas point back into data coordinates."""
        px, py = self.world_transform().invert().apply_to_point(point)
        cx, cy = self.center
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        fx = (px - (cx - self.x_length / 2.0)) / self.x_length
        fy = ((cy + self.y_length / 2.0) - py) / self.y_length
        return (x0 + fx * (x1 - x0), y0 + fy * (y1 - y0))

    point_to_coords = p2c

    def plot(
        self,
        function: GraphFn,
        *,
        x_range: tuple[float, float] | None = None,
        samples: int = 128,
    ) -> FunctionGraph:
        """Sample ``y=f(x)`` and map it through this coordinate system."""
        return FunctionGraph(
            function,
            x_range=x_range or self.x_range,
            samples=samples,
            axes=self,
        )

    get_graph = plot

    def get_axis_labels(self, x_label: str = "x", y_label: str = "y") -> object:
        """Return labels positioned at the positive ends of both axes."""
        from archmotion.core.vgroup import VGroup
        from archmotion.domains.text import Text

        zero_x = min(max(0.0, self.x_range[0]), self.x_range[1])
        zero_y = min(max(0.0, self.y_range[0]), self.y_range[1])
        x_text = Text(x_label, size=24.0).move_to(*self.c2p(self.x_range[1], zero_y))
        x_text.shift(16.0, 18.0)
        y_text = Text(y_label, size=24.0).move_to(*self.c2p(zero_x, self.y_range[1]))
        y_text.shift(-16.0, -18.0)
        return VGroup(x_text, y_text)


class ParametricFunction(VMobject):
    """A curve sampled from a parametric function ``t -> (x, y)``."""

    def __init__(
        self,
        function: CoordFn,
        *,
        t_range: tuple[float, float] = (0.0, 1.0),
        samples: int = 64,
    ) -> None:
        """Store the function + sampling config, then generate points."""
        self.function = function
        self.t_range = t_range
        self.samples = max(2, samples)
        super().__init__()

    def generate_points(self) -> None:
        """Sample the curve and trace a polyline through the points."""
        t0, t1 = self.t_range
        tracing = False
        for i in range(self.samples):
            t = t0 + (t1 - t0) * i / (self.samples - 1)
            try:
                point = self.function(t)
                valid = len(point) == 2 and all(math.isfinite(float(v)) for v in point)
            except (ArithmeticError, TypeError, ValueError):
                valid = False
            if not valid:
                tracing = False
                continue
            normalized = (float(point[0]), float(point[1]))
            if tracing:
                self.add_line_to(normalized)
            else:
                self.start_new_path(normalized)
                tracing = True


class FunctionGraph(ParametricFunction):
    """A function graph ``y = f(x)`` sampled over an x-interval."""

    def __init__(
        self,
        function: GraphFn,
        *,
        x_range: tuple[float, float] = (-1.0, 1.0),
        samples: int = 64,
        axes: Axes | None = None,
    ) -> None:
        """Wrap ``f`` as a parametric ``(x, f(x))`` and delegate."""
        self.function_xy = function
        self.x_range = x_range
        self.axes = axes
        wrapped: CoordFn = (
            (lambda t: axes.c2p(t, function(t)))
            if axes is not None
            else (lambda t: (t, function(t)))
        )
        super().__init__(wrapped, t_range=x_range, samples=samples)


def _nice_step(rng: tuple[float, float]) -> float:
    """Pick a round tick step for a range (about 5-10 ticks)."""
    span = abs(rng[1] - rng[0])
    if span == 0:
        return 1.0
    raw = span / 6.0
    mag = 10 ** math.floor(math.log10(raw))
    norm = raw / mag
    if norm < 1.5:
        step = 1.0
    elif norm < 3.0:
        step = 2.0
    elif norm < 7.0:
        step = 5.0
    else:
        step = 10.0
    return float(step * mag)


def _validate_range(rng: tuple[float, float], name: str) -> None:
    """Require a finite, strictly increasing numeric range."""
    if len(rng) != 2 or not all(math.isfinite(float(value)) for value in rng):
        raise ValueError(f"{name} must contain two finite values")
    if rng[1] <= rng[0]:
        raise ValueError(f"{name} must be strictly increasing")


class NumberPlane(VMobject):
    """A 2D number plane (grid + axes) with evenly-spaced grid lines.

    The grid spans ``x_range`` x ``y_range`` in scene units, rendered as
    horizontal + vertical ``Line`` segments at each tick. Axes (the central
    x=0 and y=0 lines) are emphasized with a thicker stroke.
    """

    def __init__(
        self,
        x_range: tuple[float, float] = (-5.0, 5.0),
        y_range: tuple[float, float] = (-3.0, 3.0),
        *,
        unit_size: float = 40.0,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store ranges + unit size, then generate the grid."""
        _validate_range(x_range, "x_range")
        _validate_range(y_range, "y_range")
        if unit_size <= 0:
            raise ValueError("unit_size must be positive")
        self.x_range = x_range
        self.y_range = y_range
        self.unit_size = unit_size
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Build the grid as a single VMobject with line segments."""
        from archmotion.domains.geometry.shapes import Line

        cx, cy = self.center
        us = self.unit_size
        x0, x1 = self.x_range
        y0, y1 = self.y_range

        # Pixel bounds of the plane.
        px0 = cx + x0 * us
        px1 = cx + x1 * us
        py0 = cy - y0 * us
        py1 = cy - y1 * us

        x_step = _nice_step(self.x_range)
        y_step = _nice_step(self.y_range)

        # Vertical grid lines (constant x).
        x = math.ceil(x0 / x_step) * x_step
        while x <= x1 + 1e-9:
            px = cx + x * us
            line = Line((px, py0), (px, py1))
            is_axis = abs(x) < 1e-9
            line.set_stroke(
                "#888888" if is_axis else "#444444",
                width=2.0 if is_axis else 1.0,
            )
            self._append_line_points(line)
            x += x_step

        # Horizontal grid lines (constant y).
        y = math.ceil(y0 / y_step) * y_step
        while y <= y1 + 1e-9:
            py = cy - y * us
            line = Line((px0, py), (px1, py))
            is_axis = abs(y) < 1e-9
            line.set_stroke(
                "#888888" if is_axis else "#444444",
                width=2.0 if is_axis else 1.0,
            )
            self._append_line_points(line)
            y += y_step

    def _append_line_points(self, line: VMobject) -> None:
        """Copy a line's points/contours into this plane's point array."""
        pts = line.points
        starts = line.contour_starts
        if not self._contour_starts:
            self._contour_starts = list(starts)
            self._pts = [(float(p[0]), float(p[1])) for p in pts]
        else:
            offset = len(self._pts)
            self._contour_starts.extend(s + offset for s in starts)
            self._pts.extend((float(p[0]), float(p[1])) for p in pts)
        if self._pts:
            self._last = self._pts[-1]

    def c2p(self, x: float, y: float) -> Point:
        """Map plane coordinates into canvas coordinates."""
        cx, cy = self.center
        return self.world_transform().apply_to_point(
            (cx + x * self.unit_size, cy - y * self.unit_size)
        )

    coords_to_point = c2p

    def p2c(self, point: Point) -> tuple[float, float]:
        """Map a canvas point back into plane coordinates."""
        px, py = self.world_transform().invert().apply_to_point(point)
        cx, cy = self.center
        return ((px - cx) / self.unit_size, (cy - py) / self.unit_size)

    point_to_coords = p2c
