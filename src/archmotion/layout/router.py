"""Manhattan Router — computes orthogonal connection paths.

Phase 2: Given source and target bounding boxes, produces a polyline
of (x, y) points forming an L-shape, I-shape, or Z-shape path.

MVP Strategy (Lean Manhattan):
    - No obstacle avoidance (may pass through other nodes)
    - User can override with `waypoints` parameter
    - A* pathfinding deferred to v0.2.0
"""

from __future__ import annotations

from archmotion._types import Point
from archmotion.constants import ROUTING_THRESHOLD
from archmotion.layout.bbox import BoundingBox


def manhattan_route(
    source_bbox: BoundingBox,
    target_bbox: BoundingBox,
    waypoints: list[tuple[float, float]] | None = None,
) -> list[Point]:
    """Compute Manhattan routing path between two bounding boxes.

    Args:
        source_bbox: Bounding box of the source node.
        target_bbox: Bounding box of the target node.
        waypoints: User-provided override points (bypass auto-routing).

    Returns:
        List of (x, y) points forming the polyline path.
        First point is the source anchor, last is the target anchor.

    Complexity: O(1) — no pathfinding.
    """
    if waypoints:
        src_anchor = _nearest_anchor(source_bbox, waypoints[0])
        tgt_anchor = _nearest_anchor(target_bbox, waypoints[-1])
        return [src_anchor, *waypoints, tgt_anchor]

    dx = target_bbox.center[0] - source_bbox.center[0]
    dy = target_bbox.center[1] - source_bbox.center[1]

    # I-Shape: same row (horizontal line)
    if abs(dy) < ROUTING_THRESHOLD:
        if dx > 0:
            return [source_bbox.right_anchor, target_bbox.left_anchor]
        return [source_bbox.left_anchor, target_bbox.right_anchor]

    # I-Shape: same column (vertical line)
    if abs(dx) < ROUTING_THRESHOLD:
        if dy > 0:
            return [source_bbox.bottom_anchor, target_bbox.top_anchor]
        return [source_bbox.top_anchor, target_bbox.bottom_anchor]

    # L-Shape: diagonal — go horizontal first, then vertical
    if abs(dx) >= abs(dy):
        src = source_bbox.right_anchor if dx > 0 else source_bbox.left_anchor
        tgt = target_bbox.top_anchor if dy > 0 else target_bbox.bottom_anchor
        mid: Point = (tgt[0], src[1])
    else:
        src = source_bbox.bottom_anchor if dy > 0 else source_bbox.top_anchor
        tgt = target_bbox.left_anchor if dx > 0 else target_bbox.right_anchor
        mid = (src[0], tgt[1])

    return [src, mid, tgt]


def _nearest_anchor(bbox: BoundingBox, point: tuple[float, float]) -> Point:
    """Find the bbox anchor closest to a given point.

    Args:
        bbox: The bounding box with 4 anchor points.
        point: External reference point.

    Returns:
        The closest anchor point.
    """
    anchors = [
        bbox.right_anchor,
        bbox.left_anchor,
        bbox.top_anchor,
        bbox.bottom_anchor,
    ]
    return min(anchors, key=lambda a: (a[0] - point[0]) ** 2 + (a[1] - point[1]) ** 2)
