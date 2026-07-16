"""Architecture-domain connection (Manhattan-routed link + arrowhead).

A :class:`Connection` is a :class:`~archmotion.core.vmobject.VMobject` whose
points trace a routed polyline between two graphics. Two point-generation paths:

- :meth:`generate_points` — the default L-route from the endpoints' current
  bounding boxes (used for manually-placed scenes, e.g. the fusion demo).
- :meth:`regenerate_points` — rebuilds the points from a **resolved route**
  (the A*/Manhattan polyline produced by the layout resolver) with optional
  rounded corners and an arrowhead. Called by ``resolve_architecture``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.constants import (
    ARROW_SIZE,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    Z_CONNECTION,
    Z_LABEL,
)
from archmotion.core.vmobject import VMobject

if TYPE_CHECKING:
    PointLike = tuple[float, float]

    from archmotion._types import Point


def _dist(a: Point, b: Point) -> float:
    """Euclidean distance between two points."""
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)


def _point_along(vertex: Point, other: Point, dist: float) -> Point:
    """Point ``dist`` pixels from ``vertex`` toward ``other``."""
    d = _dist(vertex, other)
    if d < 1e-9:
        return vertex
    t = dist / d
    return (vertex[0] + (other[0] - vertex[0]) * t, vertex[1] + (other[1] - vertex[1]) * t)


def _anchor(graphic: VMobject, side: str) -> Point:
    """Return the anchor point on a side of a graphic's bounding box."""
    bbox = graphic.bounding_box()
    if side == "right":
        return (bbox.x + bbox.width, bbox.y + bbox.height / 2.0)
    if side == "left":
        return (bbox.x, bbox.y + bbox.height / 2.0)
    if side == "top":
        return (bbox.x + bbox.width / 2.0, bbox.y)
    return (bbox.x + bbox.width / 2.0, bbox.y + bbox.height)  # bottom


class Connection(VMobject):
    """An orthogonal (Manhattan) link between two graphics, with an arrowhead.

    Routing is performed by the layout resolver (A* obstacle-aware when other
    nodes are present, falling back to a direct L/I-shape). User ``waypoints``
    override auto-routing entirely.
    """

    def __init__(
        self,
        source: VMobject,
        target: VMobject,
        *,
        label: str = "",
        waypoints: list[Point] | None = None,
        corner_radius: float = 0.0,
        arrow_size: float = ARROW_SIZE,
    ) -> None:
        """Store endpoints + label, then generate the initial route."""
        self.source = source
        self.target = target
        self.label = label
        self.waypoints = waypoints
        self.corner_radius = corner_radius
        self.arrow_size = arrow_size
        # The resolved route polyline (no arrowhead) — used for even-speed
        # packet traversal. Populated by regenerate_points().
        self._route: list[Point] = []
        super().__init__(z_index=Z_CONNECTION)
        self.set_fill(opacity=0.0)
        self._label_graphic = self._make_label()
        if self._label_graphic is not None:
            self.add(self._label_graphic)
            self._position_label()

    def generate_points(self) -> None:
        """Trace a default L-route from the endpoints' current boxes.

        This is the pre-resolution path for manually-placed scenes. After the
        layout resolver runs, :meth:`regenerate_points` replaces it with the
        A*/Manhattan route + rounded corners.
        """
        start = _anchor(self.source, "right")
        end = _anchor(self.target, "left")
        route: list[Point] = [start, end]
        # Same-row / diagonal → add a bend for an L-shape.
        if abs(end[1] - start[1]) > 1.0 and abs(end[0] - start[0]) > 1.0:
            route = [start, (end[0], start[1]), end]
        self.regenerate_points(route, corner_radius=0.0)

    def regenerate_points(self, route: list[Point], corner_radius: float = 0.0) -> Connection:
        """Rebuild this connection's points from a resolved polyline.

        Args:
            route: Ordered polyline (first = source anchor, last = target
                anchor) from the layout resolver.
            corner_radius: If > 0, round each interior bend with a quadratic
                Bezier inset by this many pixels (clamped to half the shorter
                adjacent leg).
        """
        # Reset the VMobject point buffers (single contour).
        self._pts = []
        self._contour_starts = []
        self._last = None
        # Remember the clean route (without arrowhead) for packet traversal.
        self._route = list(route)

        if len(route) < 2:
            return self

        self.start_new_path(route[0])
        if corner_radius <= 0.0 or len(route) <= 2:
            for pt in route[1:]:
                self.add_line_to(pt)
        else:
            for i in range(1, len(route) - 1):
                a, v, b = route[i - 1], route[i], route[i + 1]
                r = min(corner_radius, _dist(a, v) / 2.0, _dist(v, b) / 2.0)
                if r <= 0.5:
                    self.add_line_to(v)
                else:
                    back_in = _point_along(v, a, r)
                    back_out = _point_along(v, b, r)
                    self.add_line_to(back_in)
                    self.add_quadratic_bezier(v, back_out)
            self.add_line_to(route[-1])

        self._add_arrowhead(route[-2], route[-1])
        self._position_label()
        return self

    def _make_label(self) -> VMobject | None:
        """Build the connection's text label as a child VMobject."""
        if not self.label:
            return None
        try:
            from archmotion.domains.text.text import Text

            text = Text(
                self.label,
                family=DEFAULT_FONT_FAMILY,
                size=DEFAULT_FONT_SIZE,
            )
            text.set_z(Z_LABEL)
            return text
        except (ImportError, RuntimeError):
            return None

    def _position_label(self) -> None:
        """Keep the label centered on the clean routed path."""
        label = getattr(self, "_label_graphic", None)
        if label is not None and self._route:
            label.move_to(*self.point_at_progress(0.5))

    def point_at_progress(self, progress: float) -> Point:
        """Point at ``progress`` in [0, 1] along the route (arc-length even).

        Falls back to the base VMobject sampler when no resolved route is set.
        """
        route = self._route
        if not route or len(route) < 2:
            return super().point_at_progress(progress)
        p = max(0.0, min(1.0, float(progress)))
        if p <= 0.0:
            return route[0]
        if p >= 1.0:
            return route[-1]
        seg_lengths = [_dist(route[i], route[i + 1]) for i in range(len(route) - 1)]
        total = sum(seg_lengths)
        if total < 1e-9:
            return route[0]
        target = p * total
        acc = 0.0
        for i, sl in enumerate(seg_lengths):
            if acc + sl >= target:
                t = (target - acc) / sl if sl > 1e-9 else 0.0
                a, b = route[i], route[i + 1]
                return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            acc += sl
        return route[-1]

    def _add_arrowhead(self, tip_prev: Point, tip: Point) -> None:
        """Append a two-wing arrowhead pointing into ``tip``."""
        dx, dy = tip[0] - tip_prev[0], tip[1] - tip_prev[1]
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-9:
            return
        ux, uy = dx / length, dy / length
        px, py = -uy, ux  # perpendicular
        s = self.arrow_size
        wing1 = (tip[0] - ux * s + px * s * 0.5, tip[1] - uy * s + py * s * 0.5)
        wing2 = (tip[0] - ux * s - px * s * 0.5, tip[1] - uy * s - py * s * 0.5)
        self.add_line_to(wing1)
        self.add_line_to(tip)
        self.add_line_to(wing2)
