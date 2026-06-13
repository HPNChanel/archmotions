"""Manhattan Router — computes orthogonal connection paths.

Phase 2: Given source and target bounding boxes, produces a polyline
of (x, y) points forming an L-shape, I-shape, or Z-shape path.

v0.2.0 Routing Strategy:
    1. If user provides ``waypoints``, use them directly (manual override).
    2. If ``obstacles`` are provided, attempt A* obstacle-aware routing.
    3. Fallback to direct Manhattan routing (L/I-shape) if A* finds no path
       or if no obstacles are given.

    The A* router is invoked when ``_route_connections()`` in resolver.py
    passes all other nodes' BoundingBoxes as obstacles, enabling automatic
    collision avoidance for connection lines.
"""

from __future__ import annotations

from archmotion._types import Point
from archmotion.constants import ROUTING_THRESHOLD
from archmotion.layout.astar import astar_route, simplify_path
from archmotion.layout.bbox import BoundingBox


def manhattan_route(
    source_bbox: BoundingBox,
    target_bbox: BoundingBox,
    waypoints: list[tuple[float, float]] | None = None,
    obstacles: list[BoundingBox] | None = None,
) -> list[Point]:
    """Compute Manhattan routing path between two bounding boxes.

    Args:
        source_bbox: Bounding box of the source node.
        target_bbox: Bounding box of the target node.
        waypoints: User-provided override points (bypass auto-routing).
        obstacles: Other nodes' BoundingBoxes to route around (A* mode).

    Returns:
        List of (x, y) points forming the polyline path.
        First point is the source anchor, last is the target anchor.

    Complexity:
        - Without obstacles: O(1) (direct Manhattan).
        - With obstacles: O(N³) where N = number of obstacles (A* search).
    """
    # Priority 1: User waypoints override all routing
    if waypoints:
        src_anchor = _nearest_anchor(source_bbox, waypoints[0])
        tgt_anchor = _nearest_anchor(target_bbox, waypoints[-1])
        return [src_anchor, *waypoints, tgt_anchor]

    # Priority 2: A* obstacle-aware routing
    if obstacles:
        route = _try_astar_route(source_bbox, target_bbox, obstacles)
        if route is not None:
            return route

    # Priority 3: Direct Manhattan routing (fallback)
    return _direct_manhattan(source_bbox, target_bbox)


def _try_astar_route(
    source_bbox: BoundingBox,
    target_bbox: BoundingBox,
    obstacles: list[BoundingBox],
) -> list[Point] | None:
    """Attempt A* obstacle-aware routing between two nodes.

    Selects the best source/target anchors based on relative position,
    then invokes A* pathfinding. Returns None if A* cannot find a path
    (signals fallback to direct routing).

    Args:
        source_bbox: Source node BoundingBox.
        target_bbox: Target node BoundingBox.
        obstacles: Other nodes' BoundingBoxes (excludes source and target).

    Returns:
        Simplified polyline path, or None if A* fails.
    """
    # Choose anchors based on relative position
    src_anchor, tgt_anchor = _select_anchors(source_bbox, target_bbox)

    # Filter obstacles: exclude source and target themselves
    filtered = [
        obs for obs in obstacles
        if obs is not source_bbox and obs is not target_bbox
    ]

    if not filtered:
        return None  # No obstacles to route around

    astar_path = astar_route(src_anchor, tgt_anchor, filtered)

    if astar_path is None:
        return None  # A* found no path or direct path is clear

    # Simplify the path (remove collinear intermediate points)
    return simplify_path(astar_path)


def _select_anchors(
    source_bbox: BoundingBox,
    target_bbox: BoundingBox,
) -> tuple[Point, Point]:
    """Select the best anchor pair based on relative node positions.

    Args:
        source_bbox: Source node BoundingBox.
        target_bbox: Target node BoundingBox.

    Returns:
        Tuple of (source_anchor, target_anchor).
    """
    dx = target_bbox.center[0] - source_bbox.center[0]
    dy = target_bbox.center[1] - source_bbox.center[1]

    # Primarily horizontal
    if abs(dx) >= abs(dy):
        if dx > 0:
            return source_bbox.right_anchor, target_bbox.left_anchor
        return source_bbox.left_anchor, target_bbox.right_anchor

    # Primarily vertical
    if dy > 0:
        return source_bbox.bottom_anchor, target_bbox.top_anchor
    return source_bbox.top_anchor, target_bbox.bottom_anchor


def _direct_manhattan(
    source_bbox: BoundingBox,
    target_bbox: BoundingBox,
) -> list[Point]:
    """Direct Manhattan routing without obstacle avoidance.

    Produces I-shape (straight) or L-shape (one bend) paths.

    Args:
        source_bbox: Source node BoundingBox.
        target_bbox: Target node BoundingBox.

    Returns:
        Polyline path (2 or 3 points).
    """
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
