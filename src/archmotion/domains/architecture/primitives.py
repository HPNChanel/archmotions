"""Architecture-domain primitives as point-generating VMobjects (v2.0).

Each primitive (Node, Database, Cloud, Queue, Cache, User) generates a Bezier
point array matching its classic architecture shape. Because they share the
:class:`~archmotion.core.vmobject.VMobject` model, an architecture node can
``Transform`` into a geometry shape or chart — the core "multi-domain fusion".

Coordinate space is pixels, top-left origin, y-down. The ``label`` is stored for
later text rendering (text domain). Size is estimated from the label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.core.vmobject import VMobject
from archmotion.layout.bbox import estimate_text_bbox

if TYPE_CHECKING:
    from archmotion._types import Point

NODE_CORNER_RADIUS = 10.0
CLOUD_PADDING = 1.15


def _node_size(label: str) -> tuple[float, float]:
    """Estimate (width, height) for a node from its label."""
    w, h = estimate_text_bbox(label)
    return (w, h)


class Node(VMobject):
    """A rectangular box (service/component) — a rounded rectangle outline."""

    def __init__(
        self,
        label: str = "",
        *,
        width: float | None = None,
        height: float | None = None,
        center: Point = (0.0, 0.0),
        corner_radius: float = NODE_CORNER_RADIUS,
    ) -> None:
        """Store label/size/center, then generate the rounded-rect outline."""
        self.label = label
        ew, eh = _node_size(label) if (width is None or height is None) else (width, height)
        self.width = width if width is not None else ew
        self.height = height if height is not None else eh
        self.center = center
        self.corner_radius = corner_radius
        super().__init__()

    def generate_points(self) -> None:
        """Trace a rounded rectangle (four edges + four corner arcs)."""
        w, h = self.width, self.height
        r = min(self.corner_radius, w / 2, h / 2)
        cx, cy = self.center
        x0, y0 = cx - w / 2.0, cy - h / 2.0
        x1, y1 = cx + w / 2.0, cy + h / 2.0
        self.start_new_path((x0 + r, y0))
        self.add_line_to((x1 - r, y0))
        self.add_arc((x1 - r, y0 + r), r, -90.0, 90.0)
        self.add_line_to((x1, y1 - r))
        self.add_arc((x1 - r, y1 - r), r, 0.0, 90.0)
        self.add_line_to((x0 + r, y1))
        self.add_arc((x0 + r, y1 - r), r, 90.0, 90.0)
        self.add_line_to((x0, y0 + r))
        self.add_arc((x0 + r, y0 + r), r, 180.0, 90.0)
        self.close_path()


class Database(VMobject):
    """A cylinder (storage) — a body rectangle capped by two ellipses."""

    def __init__(
        self,
        label: str = "",
        *,
        width: float | None = None,
        height: float | None = None,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store label/size/center, then generate the cylinder outline."""
        self.label = label
        ew, eh = _node_size(label) if (width is None or height is None) else (width, height)
        self.width = width if width is not None else ew
        self.height = height if height is not None else eh
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Body rectangle + top ellipse + bottom ellipse (three contours)."""
        w, h = self.width, self.height
        cx, cy = self.center
        x0, y0 = cx - w / 2.0, cy - h / 2.0
        cap = h * 0.15
        # Body rectangle (between the cap centers).
        self.start_new_path((x0, y0 + cap))
        self.add_line_to((x0 + w, y0 + cap))
        self.add_line_to((x0 + w, y0 + h - cap))
        self.add_line_to((x0, y0 + h - cap))
        self.close_path()
        # Top ellipse (full).
        _ellipse_contour(self, cx, y0 + cap, w / 2.0, cap)
        # Bottom ellipse (full).
        _ellipse_contour(self, cx, y0 + h - cap, w / 2.0, cap)


class Queue(VMobject):
    """A parallelogram (message queue)."""

    def __init__(
        self,
        label: str = "",
        *,
        width: float | None = None,
        height: float | None = None,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store label/size/center, then generate the parallelogram outline."""
        self.label = label
        ew, eh = _node_size(label) if (width is None or height is None) else (width, height)
        self.width = width if width is not None else ew
        self.height = height if height is not None else eh
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Trace the four skewed corners and close."""
        w, h = self.width, self.height
        cx, cy = self.center
        x0, y0 = cx - w / 2.0, cy - h / 2.0
        skew = w * 0.12
        self.start_new_path((x0 + skew, y0))
        self.add_line_to((x0 + w, y0))
        self.add_line_to((x0 + w - skew, y0 + h))
        self.add_line_to((x0, y0 + h))
        self.close_path()


class Cache(VMobject):
    """A diamond (cache layer)."""

    def __init__(
        self,
        label: str = "",
        *,
        width: float | None = None,
        height: float | None = None,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store label/size/center, then generate the diamond outline."""
        self.label = label
        ew, eh = _node_size(label) if (width is None or height is None) else (width, height)
        self.width = width if width is not None else ew
        self.height = height if height is not None else eh
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Trace the four diamond vertices and close."""
        w, h = self.width, self.height
        cx, cy = self.center
        self.start_new_path((cx, cy - h / 2.0))
        self.add_line_to((cx + w / 2.0, cy))
        self.add_line_to((cx, cy + h / 2.0))
        self.add_line_to((cx - w / 2.0, cy))
        self.close_path()


class Cloud(VMobject):
    """A cloud contour (external service) — four cubic Bezier humps."""

    def __init__(
        self,
        label: str = "",
        *,
        width: float | None = None,
        height: float | None = None,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store label/size/center, then generate the cloud outline."""
        self.label = label
        ew, eh = _node_size(label) if (width is None or height is None) else (width, height)
        self.width = (width if width is not None else ew) * CLOUD_PADDING
        self.height = (height if height is not None else eh) * CLOUD_PADDING
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Trace the classic 4-hump cloud silhouette with cubic Beziers."""
        x, y = self.center[0] - self.width / 2.0, self.center[1] - self.height / 2.0
        w, h = self.width, self.height
        bottom_y = y + h * 0.75
        top_y = y + h * 0.20
        self.start_new_path((x + w * 0.15, bottom_y))
        self.add_cubic_bezier(
            (x - w * 0.05, bottom_y - h * 0.15),
            (x - w * 0.05, top_y + h * 0.15),
            (x + w * 0.20, top_y),
        )
        self.add_cubic_bezier(
            (x + w * 0.20, y - h * 0.05),
            (x + w * 0.40, y - h * 0.05),
            (x + w * 0.50, top_y - h * 0.05),
        )
        self.add_cubic_bezier(
            (x + w * 0.60, y - h * 0.10),
            (x + w * 0.85, y + h * 0.05),
            (x + w * 0.85, top_y + h * 0.10),
        )
        self.add_cubic_bezier(
            (x + w * 1.05, top_y + h * 0.20),
            (x + w * 1.05, bottom_y - h * 0.10),
            (x + w * 0.85, bottom_y),
        )
        self.add_line_to((x + w * 0.15, bottom_y))
        self.close_path()


class User(VMobject):
    """A person icon (head circle + body trapezoid)."""

    def __init__(
        self,
        label: str = "",
        *,
        width: float | None = None,
        height: float | None = None,
        center: Point = (0.0, 0.0),
    ) -> None:
        """Store label/size/center, then generate the person silhouette."""
        self.label = label
        ew, eh = _node_size(label) if (width is None or height is None) else (width, height)
        self.width = width if width is not None else ew
        self.height = height if height is not None else eh
        self.center = center
        super().__init__()

    def generate_points(self) -> None:
        """Head circle (contour 1) + body trapezoid (contour 2)."""
        w, h = self.width, self.height
        cx, cy = self.center
        head_r = min(w * 0.22, h * 0.18)
        head_cy = cy - h / 2.0 + head_r + 2.0
        # Head.
        self.start_new_path((cx + head_r, head_cy))
        self.add_arc((cx, head_cy), head_r, 0.0, 360.0)
        self.close_path()
        # Body trapezoid.
        body_top = head_cy + head_r + 3.0
        body_bottom = cy + h / 2.0 - h * 0.05
        half_top = head_r * 0.8
        half_bottom = min(w * 0.35, head_r * 1.6)
        self.start_new_path((cx - half_top, body_top))
        self.add_line_to((cx + half_top, body_top))
        self.add_line_to((cx + half_bottom, body_bottom))
        self.add_line_to((cx - half_bottom, body_bottom))
        self.close_path()


def _ellipse_contour(obj: VMobject, cx: float, cy: float, rx: float, ry: float) -> None:
    """Append a closed ellipse contour to ``obj`` (4-segment cubic approximation)."""
    k = 0.5522847498
    obj.start_new_path((cx + rx, cy))
    obj.add_cubic_bezier((cx + rx, cy - ry * k), (cx + rx * k, cy - ry), (cx, cy - ry))
    obj.add_cubic_bezier((cx - rx * k, cy - ry), (cx - rx, cy - ry * k), (cx - rx, cy))
    obj.add_cubic_bezier((cx - rx, cy + ry * k), (cx - rx * k, cy + ry), (cx, cy + ry))
    obj.add_cubic_bezier((cx + rx * k, cy + ry), (cx + rx, cy + ry * k), (cx + rx, cy))
    obj.close_path()
