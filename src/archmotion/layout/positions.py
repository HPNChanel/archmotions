"""Position constraint types shared by the (generic) layout resolver.

These describe *how* a node wants to be placed — relative to an anchor or at an
absolute pixel coordinate. They are deliberately decoupled from any concrete
node class (v1 ``api.primitives`` and v2 ``domains.architecture`` primitives both
use them) so the resolver can operate on either via the
:class:`~archmotion.layout.resolver.LayoutNode` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archmotion._types import Direction


@dataclass
class RelativePosition:
    """Records a spatial relationship between two nodes.

    Attributes:
        anchor_id: ID of the reference node.
        direction: Which side of the anchor this node sits on.
        distance: Distance in grid units (converted to pixels during layout).
    """

    anchor_id: str
    direction: Direction
    distance: float


@dataclass
class AbsolutePosition:
    """Records an absolute (freeform) pixel position for a node.

    Used by the visual editor (ArchMotion Studio) where nodes are placed by
    dragging rather than relative to an anchor. The coordinate origin is the
    top-left corner of the canvas (y grows downward), matching the SVG/Canvas
    coordinate space used throughout the layout + render pipeline.

    Attributes:
        x: Left edge X coordinate (pixels).
        y: Top edge Y coordinate (pixels).
    """

    x: float
    y: float
