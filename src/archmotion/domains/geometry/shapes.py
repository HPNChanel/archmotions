"""Vector shape primitives for the geometry domain.

Every shape is a :class:`~archmotion.core.vmobject.VMobject` that builds its own
cubic-Bezier point array in :meth:`generate_points`. Because all shapes share
the point-array model, any two can be cross-domain ``Transform``-morphed.

Coordinate space is **pixels, top-left origin, y-down** (consistent with the
rest of ArchMotion v2.0). Shape defaults are sized for visibility. Style the
shapes with the fluent API (``.set_fill(...)``, ``.set_stroke(...)``).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from archmotion.core.pathops import arc_triplets
from archmotion.core.vmobject import VMobject

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archmotion._types import Point

DEFAULT_RADIUS = 50.0


class Circle(VMobject):
    """A circle."""

    def __init__(
        self,
        radius: float = DEFAULT_RADIUS,
        *,
        center: Point = (0.0, 0.0),
        n_segments: int | None = None,
    ) -> None:
        """Store radius/center, then generate points."""
        self.radius = radius
        self.center = center
        self._n_segments = n_segments
        super().__init__()

    def generate_points(self) -> None:
        """Trace the circle as cubic arc segments from angle 0..360."""
        cx, cy = self.center
        self.start_new_path((cx + self.radius, cy))
        self.add_arc(self.center, self.radius, 0.0, 360.0, self._n_segments)
        self.close_path()


class Arc(VMobject):
    """A circular arc (open path)."""

    def __init__(
        self,
        radius: float = DEFAULT_RADIUS,
        start_angle: float = 0.0,
        angle: float = 90.0,
        *,
        center: Point = (0.0, 0.0),
        n_segments: int | None = None,
    ) -> None:
        """Store arc parameters, then generate points."""
        self.radius = radius
        self.start_angle = start_angle
        self.angle = angle
        self.center = center
        self._n_segments = n_segments
        super().__init__()

    def generate_points(self) -> None:
        """Trace the arc from ``start_angle`` over ``angle`` degrees."""
        start_pt, triplets = arc_triplets(
            self.center, self.radius, self.start_angle, self.angle, self._n_segments
        )
        self.start_new_path(start_pt)
        for triplet in triplets:
            self._pts.extend(triplet)
            self._last = triplet[2]


class Dot(VMobject):
    """A small filled disc (a tiny circle)."""

    def __init__(self, point: Point = (0.0, 0.0), *, radius: float = 6.0) -> None:
        """Store center + radius, then generate points."""
        self.point = point
        self.radius = radius
        super().__init__()

    def generate_points(self) -> None:
        """Trace the dot as a small closed circle."""
        cx, cy = self.point
        self.start_new_path((cx + self.radius, cy))
        self.add_arc(self.point, self.radius, 0.0, 360.0)
        self.close_path()


class Rectangle(VMobject):
    """An axis-aligned rectangle."""

    def __init__(
        self,
        width: float = 120.0,
        height: float = 80.0,
        *,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store dimensions + center, then generate points."""
        self.width = width
        self.height = height
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Trace the four corners and close."""
        w, h = self.width, self.height
        cx, cy = self.center
        x0, y0 = cx - w / 2.0, cy - h / 2.0
        self.start_new_path((x0, y0))
        self.add_line_to((x0 + w, y0))
        self.add_line_to((x0 + w, y0 + h))
        self.add_line_to((x0, y0 + h))
        self.close_path()


class Square(Rectangle):
    """A rectangle with equal width and height."""

    def __init__(self, side: float = 100.0, *, center: Point = (0.0, 0.0)) -> None:
        """Delegate to Rectangle with width=height=side."""
        super().__init__(width=side, height=side, center=center)
        self.side = side


class RoundedRectangle(VMobject):
    """A rectangle with rounded corners."""

    def __init__(
        self,
        width: float = 120.0,
        height: float = 80.0,
        corner_radius: float = 12.0,
        *,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store dimensions + corner radius, then generate points."""
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Trace four straight edges joined by quarter-circle corners."""
        w, h = self.width, self.height
        r = min(self.corner_radius, self.width / 2, self.height / 2)
        cx, cy = self.center
        x0, y0 = cx - w / 2.0, cy - h / 2.0
        x1, y1 = cx + w / 2.0, cy + h / 2.0
        # Start at the top edge, just past the top-left corner.
        self.start_new_path((x0 + r, y0))
        self.add_line_to((x1 - r, y0))  # top edge
        self.add_arc((x1 - r, y0 + r), r, -90.0, 90.0)  # top-right corner
        self.add_line_to((x1, y1 - r))  # right edge
        self.add_arc((x1 - r, y1 - r), r, 0.0, 90.0)  # bottom-right corner
        self.add_line_to((x0 + r, y1))  # bottom edge
        self.add_arc((x0 + r, y1 - r), r, 90.0, 90.0)  # bottom-left corner
        self.add_line_to((x0, y0 + r))  # left edge
        self.add_arc((x0 + r, y0 + r), r, 180.0, 90.0)  # top-left corner
        self.close_path()


class Ellipse(VMobject):
    """An ellipse approximated by four cubic Bezier segments."""

    def __init__(
        self,
        width: float = 120.0,
        height: float = 80.0,
        *,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store semi-axes + center, then generate points."""
        self.width = width
        self.height = height
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Trace the ellipse with the standard 4-segment cubic approximation."""
        rx, ry = self.width / 2.0, self.height / 2.0
        cx, cy = self.center
        k = 0.5522847498  # cubic Bezier circle/ellipse constant (4*(sqrt(2)-1)/3)
        self.start_new_path((cx + rx, cy))
        self.add_cubic_bezier((cx + rx, cy - ry * k), (cx + rx * k, cy - ry), (cx, cy - ry))
        self.add_cubic_bezier((cx - rx * k, cy - ry), (cx - rx, cy - ry * k), (cx - rx, cy))
        self.add_cubic_bezier((cx - rx, cy + ry * k), (cx - rx * k, cy + ry), (cx, cy + ry))
        self.add_cubic_bezier((cx + rx * k, cy + ry), (cx + rx, cy + ry * k), (cx + rx, cy))
        self.close_path()


class Polygon(VMobject):
    """A closed polygon from explicit vertices."""

    def __init__(self, *vertices: Point) -> None:
        """Store vertices, then generate points."""
        self.vertices: list[Point] = list(vertices)
        super().__init__()

    def generate_points(self) -> None:
        """Trace the vertices and close."""
        if len(self.vertices) < 2:
            return
        self.start_new_path(self.vertices[0])
        for vertex in self.vertices[1:]:
            self.add_line_to(vertex)
        self.close_path()


class RegularPolygon(VMobject):
    """A regular polygon inscribed in a circle."""

    def __init__(
        self,
        n: int = 6,
        radius: float = DEFAULT_RADIUS,
        *,
        center: Point = (0.0, 0.0),
        start_angle: float = -90.0,
    ) -> None:
        """Store n/radius/center, then generate points."""
        if n < 3:
            msg = f"RegularPolygon needs n >= 3, got {n}"
            raise ValueError(msg)
        self.n = n
        self.radius = radius
        self.center = center
        self.start_angle = start_angle
        super().__init__()

    def generate_points(self) -> None:
        """Compute ``n`` evenly-spaced vertices and trace them."""
        cx, cy = self.center
        verts = [
            (
                cx + self.radius * math.cos(math.radians(self.start_angle + i * 360.0 / self.n)),
                cy + self.radius * math.sin(math.radians(self.start_angle + i * 360.0 / self.n)),
            )
            for i in range(self.n)
        ]
        self.start_new_path(verts[0])
        for vertex in verts[1:]:
            self.add_line_to(vertex)
        self.close_path()


class Line(VMobject):
    """A straight line segment (open path)."""

    def __init__(self, start: Point, end: Point) -> None:
        """Store endpoints, then generate points."""
        self.start = start
        self.end = end
        super().__init__()

    def generate_points(self) -> None:
        """Trace a single segment from start to end."""
        self.start_new_path(self.start)
        self.add_line_to(self.end)


class Polyline(VMobject):
    """An open polyline through a sequence of points."""

    def __init__(self, *points: Point) -> None:
        """Store points, then generate points."""
        self.points_seq: list[Point] = list(points)
        super().__init__()

    def generate_points(self) -> None:
        """Trace the points without closing."""
        if len(self.points_seq) < 2:
            return
        self.start_new_path(self.points_seq[0])
        for point in self.points_seq[1:]:
            self.add_line_to(point)


class Annulus(VMobject):
    """A ring (outer disc with an inner hole) as two contours."""

    def __init__(
        self,
        inner_radius: float = 30.0,
        outer_radius: float = DEFAULT_RADIUS,
        *,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store radii + center, then generate points."""
        self.inner_radius = inner_radius
        self.outer_radius = outer_radius
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Outer circle clockwise, inner circle counter-clockwise (even-odd hole)."""
        cx, cy = self.center
        self.start_new_path((cx + self.outer_radius, cy))
        self.add_arc(self.center, self.outer_radius, 0.0, 360.0)
        self.close_path()
        self.start_new_path((cx + self.inner_radius, cy))
        self.add_arc(self.center, self.inner_radius, 360.0, -360.0)
        self.close_path()


class ArcBetweenPoints(VMobject):
    """A circular arc from ``start`` to ``end`` subtending ``angle`` degrees.

    The arc bulges perpendicular to the chord. A positive ``angle`` produces a
    counter-clockwise bulge; negative produces clockwise.
    """

    def __init__(
        self,
        start: Point,
        end: Point,
        angle: float = 90.0,
        *,
        n_segments: int | None = None,
    ) -> None:
        """Store endpoints + subtended angle, then generate points."""
        self.start_pt = start
        self.end_pt = end
        self.angle = angle
        self._n_segments = n_segments
        super().__init__()

    def generate_points(self) -> None:
        """Compute the arc center/radius and append an arc."""
        sx, sy = self.start_pt
        ex, ey = self.end_pt
        dx = ex - sx
        dy = ey - sy
        chord = math.hypot(dx, dy)
        if chord < 1e-9:
            return

        half = math.radians(abs(self.angle) / 2)
        sin_half = math.sin(half)
        if sin_half < 1e-6:
            self.start_new_path(self.start_pt)
            self.add_line_to(self.end_pt)
            return

        radius = chord / (2 * sin_half)
        # Midpoint of chord.
        mx, my = (sx + ex) / 2, (sy + ey) / 2
        # Perpendicular unit vector to chord.
        px, py = -dy / chord, dx / chord
        # Center offset along perpendicular.
        h = radius * math.cos(half)
        if self.angle < 0:
            px, py = -px, -py
        cx = mx + px * h
        cy = my + py * h

        start_a = math.degrees(math.atan2(sy - cy, sx - cx))
        end_a = math.degrees(math.atan2(ey - cy, ex - cx))
        sweep = end_a - start_a
        sweep = (sweep + 360) % 360 if self.angle > 0 else -((-sweep + 360) % 360)

        self.add_arc((cx, cy), radius, start_a, sweep, self._n_segments)


class Bezier(VMobject):
    """A cubic Bezier curve from explicit control points.

    The first point is the path start. Each subsequent group of three points
    ``(h1, h2, end)`` defines one cubic segment.
    """

    def __init__(self, control_points: Sequence[Point]) -> None:
        """Store control points, then generate the cubic path."""
        if len(control_points) < 4 or (len(control_points) - 1) % 3 != 0:
            msg = f"Need 1 + 3k points (4, 7, 10, …); got {len(control_points)}."
            raise ValueError(msg)
        self._cps = list(control_points)
        super().__init__()

    def generate_points(self) -> None:
        """Start a new path at the first control point, add cubic segments."""
        pts = self._cps
        self.start_new_path(pts[0])
        i = 1
        while i + 2 < len(pts):
            self.add_cubic_bezier(pts[i], pts[i + 1], pts[i + 2])
            i += 3


class Brace(VMobject):
    """A curly brace ``⏝`` decorative shape (horizontal, pointing down).

    Generates a smooth brace of the given ``width`` and ``height`` (amplitude).
    Use ``move_to`` / ``shift`` to position it beside a target.
    """

    def __init__(
        self,
        width: float = 120.0,
        height: float = 16.0,
    ) -> None:
        """Store dimensions, then generate the brace outline."""
        self._width = width
        self._height = height
        super().__init__()

    def generate_points(self) -> None:
        """Build the brace from two mirrored quadratic-cubic curves."""
        w = self._width
        h = self._height
        # Left tip → center trough → right tip, with characteristic curls.
        self.start_new_path((0.0, 0.0))
        self.add_cubic_bezier((w * 0.1, h * 0.6), (w * 0.15, h), (w * 0.35, h))
        self.add_cubic_bezier((w * 0.45, h * 0.3), (w * 0.5, h * 1.4), (w * 0.5, h * 1.4))
        self.add_cubic_bezier((w * 0.5, h * 1.4), (w * 0.55, h * 0.3), (w * 0.65, h))
        self.add_cubic_bezier((w * 0.85, h), (w * 0.9, h * 0.6), (w, 0.0))


def points_on_circle(
    center: Point,
    radius: float,
    n: int,
    start_angle: float = -90.0,
) -> Sequence[Point]:
    """Helper: ``n`` evenly-spaced points around a circle (degrees)."""
    cx, cy = center
    return [
        (
            cx + radius * math.cos(math.radians(start_angle + i * 360.0 / n)),
            cy + radius * math.sin(math.radians(start_angle + i * 360.0 / n)),
        )
        for i in range(n)
    ]
