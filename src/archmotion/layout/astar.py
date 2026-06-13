"""A* Pathfinding for obstacle-aware Manhattan routing.

Architectural Note:
    Replaces the Lean Manhattan router's direct L/I/Z-shape approach
    with an obstacle-aware A* search that produces orthogonal (Manhattan-
    constrained) paths avoiding other nodes' BoundingBoxes.

    The algorithm works on a **visibility graph** rather than a dense
    pixel grid, keeping complexity proportional to O(N²) where N is
    the number of nodes (not canvas pixels). Key waypoint candidates
    are generated from inflated BoundingBox corners of all obstacles.

    Fallback: If A* cannot find a path (e.g., tightly packed nodes),
    it gracefully degrades to direct Manhattan routing (L/I-shape).

Performance Budget:
    - Typical case (5-15 nodes): < 1ms per connection
    - Worst case (50 nodes): < 10ms per connection
    - Memory: O(N²) for the visibility graph edges
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from archmotion._types import Point
from archmotion.layout.bbox import BoundingBox

# Inflation margin around obstacles (pixels).
# Routes will keep at least this distance from any node edge.
_OBSTACLE_MARGIN: float = 16.0

# Maximum number of waypoint candidates to prevent combinatorial explosion.
_MAX_WAYPOINTS: int = 200


# ──────────────────────────────────────────────
# Waypoint Candidate Generation
# ──────────────────────────────────────────────


def _inflate_bbox(bbox: BoundingBox, margin: float = _OBSTACLE_MARGIN) -> BoundingBox:
    """Expand a BoundingBox outward by ``margin`` on all sides.

    The inflated box is used as the collision boundary, while
    its corners serve as routing waypoint candidates.

    Args:
        bbox: Original BoundingBox.
        margin: Inflation margin in pixels.

    Returns:
        A new BoundingBox expanded by ``margin``.
    """
    return BoundingBox(
        x=bbox.x - margin,
        y=bbox.y - margin,
        width=bbox.width + 2 * margin,
        height=bbox.height + 2 * margin,
    )


def _bbox_corners(bbox: BoundingBox) -> list[Point]:
    """Extract the 4 corners of a BoundingBox as routing waypoints.

    Args:
        bbox: BoundingBox to extract corners from.

    Returns:
        List of 4 corner (x, y) tuples: TL, TR, BL, BR.
    """
    return [
        (bbox.x, bbox.y),                                 # Top-left
        (bbox.x + bbox.width, bbox.y),                     # Top-right
        (bbox.x, bbox.y + bbox.height),                    # Bottom-left
        (bbox.x + bbox.width, bbox.y + bbox.height),       # Bottom-right
    ]


def _generate_waypoints(
    start: Point,
    end: Point,
    obstacles: list[BoundingBox],
) -> list[Point]:
    """Generate candidate waypoints for A* pathfinding.

    Candidates include:
        1. Start and end points
        2. All 4 corners of each inflated obstacle BoundingBox

    Args:
        start: Source connection anchor point.
        end: Target connection anchor point.
        obstacles: BoundingBoxes of all OTHER nodes (excluding source/target).

    Returns:
        Deduplicated list of candidate waypoints.
    """
    candidates: list[Point] = [start, end]

    for obs in obstacles:
        inflated = _inflate_bbox(obs)
        candidates.extend(_bbox_corners(inflated))

    # Deduplicate (floating point exact match is fine for our pixel coords)
    seen: set[Point] = set()
    unique: list[Point] = []
    for pt in candidates:
        if pt not in seen:
            seen.add(pt)
            unique.append(pt)

    # Safety cap against combinatorial explosion
    if len(unique) > _MAX_WAYPOINTS:
        # Keep start/end + closest waypoints by distance to midpoint
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        scored = sorted(
            unique[2:],  # Skip start and end
            key=lambda p: abs(p[0] - mid[0]) + abs(p[1] - mid[1]),
        )
        unique = [start, end] + scored[: _MAX_WAYPOINTS - 2]

    return unique


# ──────────────────────────────────────────────
# Collision Detection
# ──────────────────────────────────────────────


def _segment_intersects_bbox(
    p1: Point,
    p2: Point,
    bbox: BoundingBox,
) -> bool:
    """Check if an axis-aligned line segment intersects a BoundingBox.

    Only handles horizontal and vertical segments (Manhattan constraint).
    Diagonal segments are treated as non-intersecting (they shouldn't
    exist in our orthogonal routing).

    Args:
        p1: Segment start point.
        p2: Segment end point.
        bbox: Obstacle BoundingBox to test against.

    Returns:
        True if the segment passes through the interior of the bbox.
    """
    x1, y1 = p1
    x2, y2 = p2

    bx1 = bbox.x
    by1 = bbox.y
    bx2 = bbox.x + bbox.width
    by2 = bbox.y + bbox.height

    # Horizontal segment (same Y)
    if abs(y1 - y2) < 0.01:
        y = y1
        if y <= by1 or y >= by2:
            return False
        seg_left = min(x1, x2)
        seg_right = max(x1, x2)
        # Segment overlaps bbox horizontally while inside vertically
        return seg_left < bx2 and seg_right > bx1

    # Vertical segment (same X)
    if abs(x1 - x2) < 0.01:
        x = x1
        if x <= bx1 or x >= bx2:
            return False
        seg_top = min(y1, y2)
        seg_bottom = max(y1, y2)
        return seg_top < by2 and seg_bottom > by1

    # Non-axis-aligned segment (shouldn't happen in Manhattan routing)
    return False


def _is_path_clear(
    p1: Point,
    p2: Point,
    obstacles: list[BoundingBox],
) -> bool:
    """Check if a Manhattan path between two points avoids all obstacles.

    A Manhattan path from p1 to p2 goes either:
        - Horizontal first, then vertical (via corner (p2[0], p1[1]))
        - Vertical first, then horizontal (via corner (p1[0], p2[1]))

    We test if EITHER route is clear (at least one valid path exists).
    For direct line (same row/column), we test the single segment.

    Args:
        p1: Start point.
        p2: End point.
        obstacles: Obstacle BoundingBoxes.

    Returns:
        True if at least one L-shape path from p1 to p2 avoids all obstacles.
    """
    # Direct horizontal or vertical line
    if abs(p1[0] - p2[0]) < 0.01 or abs(p1[1] - p2[1]) < 0.01:
        return all(not _segment_intersects_bbox(p1, p2, obs) for obs in obstacles)

    # L-shape option 1: horizontal then vertical (via corner1)
    corner1: Point = (p2[0], p1[1])
    path1_clear = all(
        not _segment_intersects_bbox(p1, corner1, obs)
        and not _segment_intersects_bbox(corner1, p2, obs)
        for obs in obstacles
    )
    if path1_clear:
        return True

    # L-shape option 2: vertical then horizontal (via corner2)
    corner2: Point = (p1[0], p2[1])
    path2_clear = all(
        not _segment_intersects_bbox(p1, corner2, obs)
        and not _segment_intersects_bbox(corner2, p2, obs)
        for obs in obstacles
    )
    return path2_clear


# ──────────────────────────────────────────────
# A* Search
# ──────────────────────────────────────────────


def _manhattan_distance(a: Point, b: Point) -> float:
    """Manhattan distance heuristic (admissible for orthogonal routing).

    Args:
        a: Point A.
        b: Point B.

    Returns:
        Manhattan distance (|dx| + |dy|).
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass
class _AStarNode:
    """Priority queue node for A* search.

    Attributes:
        f_score: g + h (total estimated cost).
        g_score: Actual cost from start.
        point: Current waypoint.
        parent_idx: Index of parent in the waypoints list (-1 for start).
    """

    f_score: float
    g_score: float
    point: Point
    parent_idx: int

    def __lt__(self, other: "_AStarNode") -> bool:
        """Compare by f_score for heapq ordering."""
        return self.f_score < other.f_score


def astar_route(
    start: Point,
    end: Point,
    obstacles: list[BoundingBox],
) -> list[Point] | None:
    """Find an obstacle-aware Manhattan route using A* pathfinding.

    The algorithm searches over a visibility graph of waypoint candidates
    (inflated obstacle corners + start/end points). Edges connect pairs
    of waypoints that have a clear Manhattan L-shape path between them.

    Args:
        start: Connection source anchor point.
        end: Connection target anchor point.
        obstacles: BoundingBoxes of all nodes to route around.

    Returns:
        List of waypoints forming the Manhattan route, or None if
        no valid path exists (fallback to direct routing needed).

    Complexity:
        O(W² × N) where W = number of waypoints, N = number of obstacles.
        Typical W ≤ 4N + 2, so effectively O(N³). With the _MAX_WAYPOINTS
        cap and typical scene sizes (5-50 nodes), this is well under 10ms.
    """
    waypoints = _generate_waypoints(start, end, obstacles)
    n = len(waypoints)

    if n < 2:
        return None

    # Build point -> index mapping
    pt_to_idx: dict[Point, int] = {wp: i for i, wp in enumerate(waypoints)}
    start_idx = pt_to_idx[start]
    end_idx = pt_to_idx[end]

    # Check direct path first (no obstacles in the way)
    if _is_path_clear(start, end, obstacles):
        return None  # Signal: direct routing is fine, no A* needed

    # A* search
    open_heap: list[_AStarNode] = []
    g_scores: dict[int, float] = {start_idx: 0.0}
    parent_map: dict[int, int] = {}
    closed: set[int] = set()

    h = _manhattan_distance(start, end)
    heapq.heappush(open_heap, _AStarNode(
        f_score=h, g_score=0.0, point=start, parent_idx=-1,
    ))

    while open_heap:
        current = heapq.heappop(open_heap)
        curr_idx = pt_to_idx.get(current.point)

        if curr_idx is None:
            continue

        if curr_idx in closed:
            continue
        closed.add(curr_idx)

        # Goal reached — reconstruct path
        if curr_idx == end_idx:
            path: list[Point] = []
            idx = end_idx
            while idx != -1:
                path.append(waypoints[idx])
                idx = parent_map.get(idx, -1)
            path.reverse()
            return path

        # Explore neighbors: all waypoints with clear Manhattan paths
        for i, wp in enumerate(waypoints):
            if i in closed:
                continue
            if not _is_path_clear(current.point, wp, obstacles):
                continue

            # Cost = Manhattan distance (actual path length)
            tentative_g = current.g_score + _manhattan_distance(current.point, wp)

            if tentative_g < g_scores.get(i, float("inf")):
                g_scores[i] = tentative_g
                parent_map[i] = curr_idx
                f = tentative_g + _manhattan_distance(wp, end)
                heapq.heappush(open_heap, _AStarNode(
                    f_score=f, g_score=tentative_g, point=wp, parent_idx=curr_idx,
                ))

    # No path found — return None to signal fallback
    return None


# ──────────────────────────────────────────────
# Path Simplification
# ──────────────────────────────────────────────


def simplify_path(path: list[Point]) -> list[Point]:
    """Remove redundant collinear waypoints from a Manhattan path.

    Three consecutive points on the same horizontal or vertical line
    can be simplified to just the first and last.

    Args:
        path: Raw A* output path.

    Returns:
        Simplified path with collinear intermediate points removed.
    """
    if len(path) <= 2:
        return path

    result: list[Point] = [path[0]]

    for i in range(1, len(path) - 1):
        prev = result[-1]
        curr = path[i]
        nxt = path[i + 1]

        # Keep point if direction changes
        same_x = abs(prev[0] - curr[0]) < 0.01 and abs(curr[0] - nxt[0]) < 0.01
        same_y = abs(prev[1] - curr[1]) < 0.01 and abs(curr[1] - nxt[1]) < 0.01

        if not (same_x or same_y):
            result.append(curr)

    result.append(path[-1])
    return result
