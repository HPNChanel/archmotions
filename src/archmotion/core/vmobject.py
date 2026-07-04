"""VMobject — the point-array (vector) graphic base.

Every vector shape in ArchMotion is a :class:`VMobject`: an ordered list of 2D
points describing one or more cubic-Bezier contours, plus a :class:`Style`,
:class:`~archmotion.core.transform.Transform`, opacity and z-order.

Point layout
------------
``points`` is a flat ``(N, 2)`` array. Each contour begins with an **anchor**
(the ``moveTo``), followed by cubic-Bezier triplets ``[h1, h2, end]`` where the
cubic's start is the previous point. ``contour_starts`` records the index of
each contour's anchor (default ``[0]``).

This shared geometry is what makes cross-domain ``Transform`` possible: two
shapes with aligned point counts interpolate their points directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from archmotion._types import Point
from archmotion.core.graphic import Graphic
from archmotion.core.pathops import (
    arc_triplets,
    bezier_length,
    line_triplet,
    quad_to_cubic,
    resample_array,
)
from archmotion.layout.bbox import BoundingBox

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from archmotion._types import Point
    from archmotion.core.style import Style
    from archmotion.core.transform import Transform


class VMobject(Graphic):
    """A vector graphic defined by cubic-Bezier control points."""

    def __init__(
        self,
        *,
        style: Style | None = None,
        transform: Transform | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        id: str | None = None,
    ) -> None:
        """Initialize empty points/contours, then call :meth:`generate_points`."""
        super().__init__(
            id=id, z_index=z_index, transform=transform, style=style, opacity=opacity
        )
        self._pts: list[Point] = []
        self._contour_starts: list[int] = []
        self._last: Point | None = None
        self.generate_points()

    # ── override hook ────────────────────────────────────────────

    def generate_points(self) -> None:
        """Build this shape's points. Override in subclasses."""

    # ── point access ─────────────────────────────────────────────

    @property
    def points(self) -> NDArray[np.float64]:
        """All control points as an ``(N, 2)`` array."""
        if not self._pts:
            return np.empty((0, 2), dtype=np.float64)
        return np.asarray(self._pts, dtype=np.float64)

    @points.setter
    def points(self, value: object) -> None:
        arr = np.asarray(value, dtype=np.float64).reshape(-1, 2)
        self._pts = [(float(p[0]), float(p[1])) for p in arr]
        self._last = self._pts[-1] if self._pts else None

    @property
    def contour_starts(self) -> list[int]:
        """Indices into ``points`` where each contour's anchor lives."""
        return list(self._contour_starts)

    @property
    def n_curves(self) -> int:
        """Total cubic-curve count across all contours."""
        return (len(self._pts) - len(self._contour_starts)) // 3

    def set_points_array(self, arr: object) -> VMobject:
        """Replace points from an ``(N, 2)`` array, preserving contour_starts."""
        self.points = arr
        return self

    # ── path builders ────────────────────────────────────────────

    def start_new_path(self, point: Point) -> VMobject:
        """Begin a new contour with a ``moveTo`` at ``point``."""
        pt = (float(point[0]), float(point[1]))
        self._contour_starts.append(len(self._pts))
        self._pts.append(pt)
        self._last = pt
        return self

    def add_cubic_bezier(self, h1: Point, h2: Point, end: Point) -> VMobject:
        """Append a cubic curve (handles ``h1``, ``h2``; ends at ``end``)."""
        self._require_open()
        self._pts.append((float(h1[0]), float(h1[1])))
        self._pts.append((float(h2[0]), float(h2[1])))
        end_pt = (float(end[0]), float(end[1]))
        self._pts.append(end_pt)
        self._last = end_pt
        return self

    def add_line_to(self, point: Point) -> VMobject:
        """Append a straight line to ``point`` (as a degenerate cubic)."""
        self._require_open()
        last = self._current_end()
        triplet = line_triplet(last, point)
        self._pts.extend(triplet)
        self._last = triplet[2]
        return self

    def add_quadratic_bezier(self, control: Point, end: Point) -> VMobject:
        """Append a quadratic curve (converted to a cubic triplet)."""
        self._require_open()
        last = self._current_end()
        triplet = quad_to_cubic(last, control, end)
        self._pts.extend(triplet)
        self._last = triplet[2]
        return self

    def add_arc(
        self,
        center: Point,
        radius: float,
        start_angle: float,
        sweep_angle: float,
        n_segments: int | None = None,
    ) -> VMobject:
        """Append a circular arc (as cubic triplets).

        Continues from the current endpoint; if no contour is open, starts one
        at the arc's first point.
        """
        start_pt, triplets = arc_triplets(center, radius, start_angle, sweep_angle, n_segments)
        if not self._contour_starts:
            self.start_new_path(start_pt)
        else:
            last = self._current_end()
            if _dist(last, start_pt) > 1e-6:
                self.add_line_to(start_pt)
        for triplet in triplets:
            self._pts.extend(triplet)
            self._last = triplet[2]
        return self

    def close_path(self) -> VMobject:
        """Line back to the current contour's anchor."""
        self._require_open()
        anchor = self._pts[self._contour_starts[-1]]
        last = self._current_end()
        if _dist(last, anchor) > 1e-6:
            self.add_line_to(anchor)
        return self

    def _require_open(self) -> None:
        if not self._contour_starts:
            msg = "No open contour — call start_new_path() before adding curves."
            raise RuntimeError(msg)

    def _current_end(self) -> Point:
        """Return the current contour endpoint (raises if no contour open)."""
        self._require_open()
        if self._last is None:
            msg = "Open contour has no endpoint."
            raise RuntimeError(msg)
        return self._last

    # ── convenience builders ─────────────────────────────────────

    def set_points_as_corners(self, corners: list[Point]) -> VMobject:
        """Build a polygon/outline from corner points (closed if it loops)."""
        if len(corners) < 2:
            return self
        self.start_new_path(corners[0])
        for corner in corners[1:]:
            self.add_line_to(corner)
        return self

    # ── geometry ─────────────────────────────────────────────────

    def bounding_box(self) -> BoundingBox:
        """Axis-aligned bbox of the transformed points (or children)."""
        if self._pts:
            transformed = self.transform.apply_to_points(self.points)
            xs = transformed[:, 0]
            ys = transformed[:, 1]
            x0 = float(xs.min())
            y0 = float(ys.min())
            return BoundingBox(x0, y0, float(xs.max()) - x0, float(ys.max()) - y0)
        return super().bounding_box()

    def total_length(self) -> float:
        """Approximate total path length across all cubics."""
        total = 0.0
        pts = self._pts
        for ci in range(len(self._contour_starts)):
            start = self._contour_starts[ci]
            end = self._contour_starts[ci + 1] if ci + 1 < len(self._contour_starts) else len(pts)
            p0 = pts[start]
            j = start + 1
            while j + 2 < end:
                total += bezier_length(p0, pts[j], pts[j + 1], pts[j + 2])
                p0 = pts[j + 2]
                j += 3
        return total

    # ── morphing ─────────────────────────────────────────────────

    def align_with(self, other: VMobject) -> tuple[object, object]:
        """Return ``(self_points, other_points)`` padded to a common count.

        Does not mutate either graphic. Padding repeats the last triplet so
        contour-start indices stay valid.
        """
        a = self.points
        b = other.points
        target = max(a.shape[0], b.shape[0])
        # Round up to the next valid count (1 + 3*k) so triplets stay whole.
        target = _round_to_triplet(target)
        return resample_array(a, target), resample_array(b, target)

    def interpolate_points(
        self, src: object, tgt: object, alpha: float
    ) -> VMobject:
        """Set points to ``lerp(src, tgt, alpha)`` from two aligned arrays."""
        src_arr = np.asarray(src, dtype=np.float64)
        tgt_arr = np.asarray(tgt, dtype=np.float64)
        if src_arr.shape != tgt_arr.shape:
            target = _round_to_triplet(max(src_arr.shape[0], tgt_arr.shape[0]))
            src_arr = resample_array(src_arr, target)
            tgt_arr = resample_array(tgt_arr, target)
        self.points = src_arr + (tgt_arr - src_arr) * alpha
        return self

    def point_at_progress(self, progress: float) -> Point:
        """A representative point at ``progress`` in [0, 1] along the path."""
        pts = self._pts
        if not pts:
            return (0.0, 0.0)
        if progress <= 0.0:
            return pts[0]
        if progress >= 1.0:
            return pts[-1]
        idx = int(progress * (len(pts) - 1))
        return pts[idx]

    # ── skia path (lazy) ─────────────────────────────────────────

    def to_skia_path(self) -> object:
        """Build a ``skia.Path`` from the points (lazy skia import)."""
        import skia

        path = skia.Path()
        pts = self._pts
        starts = [*self._contour_starts, len(pts)]
        for ci in range(len(self._contour_starts)):
            start = self._contour_starts[ci]
            end = starts[ci + 1]
            path.moveTo(*pts[start])
            j = start + 1
            while j + 2 < end:
                p1 = pts[j]
                p2 = pts[j + 1]
                p3 = pts[j + 2]
                path.cubicTo(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
                j += 3
            if j < end:
                path.lineTo(*pts[j])
        return path

    # ── copy ─────────────────────────────────────────────────────

    def copy(self) -> VMobject:
        """Deep copy preserving points, contours, style, transform."""
        from typing import cast

        clone = cast("VMobject", super().copy())
        clone._pts = list(self._pts)
        clone._contour_starts = list(self._contour_starts)
        clone._last = self._last
        return clone


def _dist(a: Point, b: Point) -> float:
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)


def _round_to_triplet(count: int) -> int:
    """Round a point count up to ``1 + 3*k`` (anchor + whole triplets)."""
    if count <= 1:
        return 1
    remainder = (count - 1) % 3
    return count if remainder == 0 else count + (3 - remainder)
