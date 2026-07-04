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
        self.x_range = x_range
        self.length = length
        self.center = center
        self.tick_step = tick_step if tick_step is not None else _nice_step(x_range)
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
            start = (cx, cy - self.length / 2.0)
            end = (cx, cy + self.length / 2.0)
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
        return (cx, cy - self.length / 2.0 + frac * self.length)


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
        self.x_range = x_range
        self.y_range = y_range
        self.x_length = x_length
        self.y_length = y_length
        self.center = center
        self.tick_step = tick_step
        super().__init__()
        self._x_axis = NumberLine(
            x_range, length=x_length, center=center, tick_step=tick_step, direction="x"
        )
        self._y_axis = NumberLine(
            y_range, length=y_length, center=center, tick_step=tick_step, direction="y"
        )
        self.add(self._x_axis, self._y_axis)

    def generate_points(self) -> None:
        """No own points — children carry the geometry."""

    def c2p(self, x: float, y: float) -> Point:
        """Map data coordinates (x, y) to pixel coordinates."""
        cx, cy = self.center
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        fx = (x - x0) / (x1 - x0) if x1 != x0 else 0.5
        fy = (y - y0) / (y1 - y0) if y1 != y0 else 0.5
        px = cx - self.x_length / 2.0 + fx * self.x_length
        # Data y-up -> pixel y-down.
        py = cy + self.y_length / 2.0 - fy * self.y_length
        return (px, py)


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
        pts = [self.function(t0 + (t1 - t0) * i / (self.samples - 1)) for i in range(self.samples)]
        if len(pts) < 2:
            return
        self.start_new_path(pts[0])
        for point in pts[1:]:
            self.add_line_to(point)


class FunctionGraph(ParametricFunction):
    """A function graph ``y = f(x)`` sampled over an x-interval."""

    def __init__(
        self,
        function: GraphFn,
        *,
        x_range: tuple[float, float] = (-1.0, 1.0),
        samples: int = 64,
    ) -> None:
        """Wrap ``f`` as a parametric ``(x, f(x))`` and delegate."""
        self.function_xy = function
        self.x_range = x_range
        wrapped: CoordFn = lambda t: (t, function(t))  # noqa: E731
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
