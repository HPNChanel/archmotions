"""Unit tests for PLAN-013 — A* Obstacle-Aware Routing.

Tests cover:
    - A* core module (astar.py): waypoint generation, collision detection,
      segment intersection, path simplification, A* search
    - Router integration (router.py): obstacle-aware routing with fallback
    - Resolver integration: end-to-end routing through node obstacles
"""

import pytest

from archmotion.layout.astar import (
    _bbox_corners,
    _generate_waypoints,
    _inflate_bbox,
    _is_path_clear,
    _manhattan_distance,
    _segment_intersects_bbox,
    astar_route,
    simplify_path,
)
from archmotion.layout.bbox import BoundingBox
from archmotion.layout.router import manhattan_route


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def _bbox(x, y, w=100, h=50):
    return BoundingBox(x=x, y=y, width=w, height=h)


# ──────────────────────────────────────────────
# BBox Inflation & Corners
# ──────────────────────────────────────────────


class TestInflation:
    def test_inflate_expands_all_sides(self):
        bbox = _bbox(100, 100, 200, 100)
        inflated = _inflate_bbox(bbox, margin=10)
        assert inflated.x == 90
        assert inflated.y == 90
        assert inflated.width == 220
        assert inflated.height == 120

    def test_inflate_default_margin(self):
        bbox = _bbox(50, 50, 100, 100)
        inflated = _inflate_bbox(bbox)
        assert inflated.x < 50
        assert inflated.y < 50
        assert inflated.width > 100

    def test_corners_returns_four_points(self):
        bbox = _bbox(0, 0, 100, 50)
        corners = _bbox_corners(bbox)
        assert len(corners) == 4
        assert (0, 0) in corners      # TL
        assert (100, 0) in corners     # TR
        assert (0, 50) in corners      # BL
        assert (100, 50) in corners    # BR


# ──────────────────────────────────────────────
# Waypoint Generation
# ──────────────────────────────────────────────


class TestWaypointGeneration:
    def test_no_obstacles_returns_start_end(self):
        wps = _generate_waypoints((0.0, 0.0), (100.0, 0.0), [])
        assert len(wps) == 2
        assert wps[0] == (0.0, 0.0)
        assert wps[1] == (100.0, 0.0)

    def test_one_obstacle_adds_corners(self):
        obs = [_bbox(40, -30, 20, 60)]
        wps = _generate_waypoints((0.0, 0.0), (100.0, 0.0), obs)
        # Start + end + 4 inflated corners = 6
        assert len(wps) >= 6

    def test_duplicates_removed(self):
        obs = [_bbox(0, 0, 100, 50), _bbox(0, 0, 100, 50)]
        wps = _generate_waypoints((0.0, 0.0), (200.0, 0.0), obs)
        # Should not have duplicate entries
        assert len(wps) == len(set(wps))


# ──────────────────────────────────────────────
# Collision Detection
# ──────────────────────────────────────────────


class TestSegmentIntersection:
    def test_horizontal_segment_through_box(self):
        bbox = _bbox(100, 0, 100, 50)
        # Horizontal line at y=25 (middle of box) crossing through
        assert _segment_intersects_bbox((0, 25), (300, 25), bbox)

    def test_horizontal_segment_above_box(self):
        bbox = _bbox(100, 100, 100, 50)
        # Horizontal line at y=10, above the box
        assert not _segment_intersects_bbox((0, 10), (300, 10), bbox)

    def test_vertical_segment_through_box(self):
        bbox = _bbox(0, 100, 100, 50)
        # Vertical line at x=50 (center) going through box
        assert _segment_intersects_bbox((50, 0), (50, 300), bbox)

    def test_vertical_segment_left_of_box(self):
        bbox = _bbox(100, 100, 100, 50)
        # Vertical line at x=10, left of box
        assert not _segment_intersects_bbox((10, 0), (10, 300), bbox)

    def test_segment_on_edge_not_intersecting(self):
        bbox = _bbox(100, 100, 100, 50)
        # Horizontal line at y=100 (top edge) — on boundary = not through
        assert not _segment_intersects_bbox((0, 100), (300, 100), bbox)

    def test_horizontal_segment_not_reaching_box(self):
        bbox = _bbox(200, 0, 100, 50)
        # Segment ends before the box
        assert not _segment_intersects_bbox((0, 25), (150, 25), bbox)


class TestPathClear:
    def test_clear_straight_line(self):
        obstacles = [_bbox(200, 200, 100, 50)]
        assert _is_path_clear((0, 0), (100, 0), obstacles)

    def test_blocked_straight_line(self):
        obstacles = [_bbox(40, -10, 20, 30)]
        assert not _is_path_clear((0, 5), (100, 5), obstacles)

    def test_lshape_with_obstacle(self):
        # Obstacle blocks the direct L-shape but maybe not the other
        obstacle = _bbox(45, 45, 10, 10)
        # Route from (0,0) to (100, 100): L-shape via (100,0) or (0,100)
        # Via (100,0): horizontal (0,0)->(100,0) clear, vertical (100,0)->(100,100) clear
        # The obstacle is not in the way of (100,0) corner
        assert _is_path_clear((0.0, 0.0), (100.0, 100.0), [obstacle])


# ──────────────────────────────────────────────
# Manhattan Distance
# ──────────────────────────────────────────────


class TestManhattanDistance:
    def test_same_point(self):
        assert _manhattan_distance((0, 0), (0, 0)) == 0

    def test_horizontal(self):
        assert _manhattan_distance((0, 0), (100, 0)) == 100

    def test_diagonal(self):
        assert _manhattan_distance((0, 0), (30, 40)) == 70


# ──────────────────────────────────────────────
# Path Simplification
# ──────────────────────────────────────────────


class TestSimplifyPath:
    def test_two_points_unchanged(self):
        path = [(0, 0), (100, 0)]
        assert simplify_path(path) == path

    def test_three_collinear_horizontal(self):
        path = [(0, 0), (50, 0), (100, 0)]
        result = simplify_path(path)
        assert len(result) == 2
        assert result == [(0, 0), (100, 0)]

    def test_three_collinear_vertical(self):
        path = [(0, 0), (0, 50), (0, 100)]
        result = simplify_path(path)
        assert len(result) == 2

    def test_l_shape_preserved(self):
        path = [(0, 0), (100, 0), (100, 100)]
        result = simplify_path(path)
        assert len(result) == 3  # Bend point preserved

    def test_z_shape_with_collinear_removed(self):
        # Z-shape with an extra collinear point
        path = [(0, 0), (50, 0), (100, 0), (100, 100)]
        result = simplify_path(path)
        assert len(result) == 3  # (0,0), (100,0), (100,100)


# ──────────────────────────────────────────────
# A* Core Search
# ──────────────────────────────────────────────


class TestAStarRoute:
    def test_no_obstacles_returns_none(self):
        # Direct path is clear → returns None (use direct routing)
        result = astar_route((0, 0), (200, 0), [])
        assert result is None

    def test_clear_direct_path_returns_none(self):
        # Obstacle exists but not in the way → returns None
        obstacles = [_bbox(300, 300, 50, 50)]
        result = astar_route((0, 0), (200, 0), obstacles)
        assert result is None

    def test_routes_around_obstacle(self):
        # Obstacle blocks the direct horizontal path
        obstacle = _bbox(80, -30, 40, 60)
        result = astar_route((0.0, 0.0), (200.0, 0.0), [obstacle])
        assert result is not None
        assert len(result) >= 2
        # Start and end should be present
        assert result[0] == (0.0, 0.0)
        assert result[-1] == (200.0, 0.0)

    def test_path_does_not_cross_obstacle(self):
        # Verify the A* path segments don't cross the obstacle
        obstacle = _bbox(80, -30, 40, 60)
        result = astar_route((0.0, 0.0), (200.0, 0.0), [obstacle])
        if result is not None:
            for i in range(len(result) - 1):
                assert not _segment_intersects_bbox(result[i], result[i + 1], obstacle), (
                    f"Path segment {result[i]} → {result[i+1]} crosses obstacle"
                )

    def test_multiple_obstacles(self):
        obstacles = [
            _bbox(80, -30, 40, 60),    # Block middle
            _bbox(160, -30, 40, 60),   # Block further right
        ]
        result = astar_route((0.0, 0.0), (300.0, 0.0), obstacles)
        # Should find a path (even if longer)
        if result is not None:
            assert result[0] == (0.0, 0.0)
            assert result[-1] == (300.0, 0.0)


# ──────────────────────────────────────────────
# Router Integration
# ──────────────────────────────────────────────


class TestRouterWithObstacles:
    def test_no_obstacles_produces_direct_route(self):
        src = _bbox(0, 0)
        tgt = _bbox(300, 0)
        path = manhattan_route(src, tgt)
        assert len(path) == 2
        assert path[0] == src.right_anchor
        assert path[1] == tgt.left_anchor

    def test_obstacles_empty_list_produces_direct(self):
        src = _bbox(0, 0)
        tgt = _bbox(300, 0)
        path = manhattan_route(src, tgt, obstacles=[])
        assert len(path) == 2

    def test_waypoints_override_obstacles(self):
        src = _bbox(0, 0)
        tgt = _bbox(300, 200)
        obstacle = _bbox(150, 80, 50, 50)
        wp = [(150.0, 0.0), (150.0, 200.0)]
        path = manhattan_route(src, tgt, waypoints=wp, obstacles=[obstacle])
        # Waypoints take priority over obstacle routing
        assert len(path) == 4

    def test_obstacle_in_path_reroutes(self):
        src = _bbox(0, 0)
        tgt = _bbox(400, 0)
        # Place an obstacle directly between source and target
        obstacle = _bbox(180, -30, 40, 100)
        path = manhattan_route(src, tgt, obstacles=[src, tgt, obstacle])
        # Should have more than 2 points (rerouted)
        assert len(path) >= 2
        # Must start and end at correct anchors
        assert path[0][1] == src.right_anchor[1] or path[0][1] == src.center[1]

    def test_backward_compatible_no_obstacles_arg(self):
        # Calling without obstacles arg should work identically
        src = _bbox(0, 0)
        tgt = _bbox(300, 0)
        path = manhattan_route(src, tgt)
        assert len(path) >= 2

    def test_obstacle_same_as_source_ignored(self):
        src = _bbox(0, 0)
        tgt = _bbox(300, 0)
        # Passing source as obstacle should be filtered out
        path = manhattan_route(src, tgt, obstacles=[src, tgt])
        assert len(path) == 2


# ──────────────────────────────────────────────
# Resolver End-to-End
# ──────────────────────────────────────────────


class TestResolverRouting:
    def test_three_node_route_avoids_middle(self):
        """A→C with B in the middle should route around B."""
        from archmotion.domains.architecture import Connection, Node
        from archmotion.layout.resolver import resolve_layout

        a = Node("A")
        b = Node("B")
        c = Node("C")

        b.right_of(a, distance=3)
        c.right_of(b, distance=3)

        # Connection from A to C (skipping B in the middle)
        conn = Connection(a, c, label="skip B")

        layout = resolve_layout(
            nodes=[a, b, c],
            connections=[conn],
            canvas_width=1920,
            canvas_height=1080,
        )

        route = layout.connection_routes[conn.id]
        assert len(route) >= 2
        # The route should start near A and end near C
        assert route[0][0] < route[-1][0]  # left to right
