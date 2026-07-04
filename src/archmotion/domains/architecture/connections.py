"""Architecture-domain connection (Manhattan-routed link + arrowhead)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.core.vmobject import VMobject

if TYPE_CHECKING:
    from archmotion._types import Point

    PointLike = tuple[float, float]


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

    The route goes horizontally from the source's right anchor, then vertically
    to the target's left anchor (an L-shape). For same-row links it is a straight
    segment.
    """

    def __init__(
        self,
        source: _VM,
        target: _VM,
        *,
        label: str = "",
        arrow_size: float = 12.0,
    ) -> None:
        """Store endpoints + label, then generate the routed polyline."""
        self.source = source
        self.target = target
        self.label = label
        self.arrow_size = arrow_size
        super().__init__()

    def generate_points(self) -> None:
        """Trace an L-route from source to target and add an arrowhead."""
        start = _anchor(self.source, "right")
        end = _anchor(self.target, "left")
        # L-route: horizontal to end.x, then vertical to end.y.
        bend = (end[0], start[1])
        self.start_new_path(start)
        if abs(bend[0] - start[0]) > 1.0:
            self.add_line_to(bend)
        self.add_line_to(end)
        # Arrowhead wings.
        dx, dy = end[0] - bend[0], end[1] - bend[1]
        length = (dx * dx + dy * dy) ** 0.5
        if length > 1e-9:
            ux, uy = dx / length, dy / length
            px, py = -uy, ux
            s = self.arrow_size
            wing1 = (end[0] - ux * s + px * s * 0.5, end[1] - uy * s + py * s * 0.5)
            wing2 = (end[0] - ux * s - px * s * 0.5, end[1] - uy * s - py * s * 0.5)
            self.add_line_to(wing1)
            self.add_line_to(end)
            self.add_line_to(wing2)
