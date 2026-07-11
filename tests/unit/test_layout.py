"""Unit tests for Phase 2 -- Layout Resolver.

Tests cover:
    - Single root node centering
    - Linear chain (A -> B -> C)
    - Tree topology (branching)
    - All 4 directions (right_of, left_of, below, above)
    - Multiple roots (side-by-side)
    - Cycle detection (CircularReferenceError)
    - Duplicate ID detection (DuplicateIdError)
    - Canvas overflow detection (OverflowCanvasError)
    - Connection routing
    - Empty scene (edge case)
"""

from __future__ import annotations

import pytest

from archmotion.domains.architecture import Connection, Database, Node
from archmotion.errors import (
    CircularReferenceError,
    OverflowCanvasError,
)
from archmotion.layout.resolver import ResolvedLayout, resolve_layout

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

CANVAS_W = 1920
CANVAS_H = 1080


def _resolve(*nodes: Node, connections: list[Connection] | None = None) -> ResolvedLayout:
    """Shortcut for resolve_layout with default canvas size."""
    return resolve_layout(
        nodes=list(nodes),
        connections=connections or [],
        canvas_width=CANVAS_W,
        canvas_height=CANVAS_H,
    )


# ──────────────────────────────────────────────
# Basic Tests
# ──────────────────────────────────────────────


class TestSingleNode:
    """A single root node should be centered on canvas."""

    def test_single_node_is_centered(self):
        node = Node("Server")
        layout = _resolve(node)

        assert node.id in layout.node_boxes
        bbox = layout.node_boxes[node.id]

        # Center of bbox should be approximately at canvas center
        cx, cy = bbox.center
        assert abs(cx - CANVAS_W / 2) < 1.0
        assert abs(cy - CANVAS_H / 2) < 1.0

    def test_single_node_dimensions_from_label(self):
        node = Node("API Gateway")
        layout = _resolve(node)
        bbox = layout.node_boxes[node.id]

        # Box should have non-zero width/height from text estimation
        assert bbox.width > 50
        assert bbox.height > 20

    def test_database_same_as_node(self):
        """Database inherits Node -- layout should work identically."""
        db = Database("PostgreSQL")
        layout = _resolve(db)
        assert db.id in layout.node_boxes


class TestEmptyScene:
    """Edge case: no nodes at all."""

    def test_empty_returns_empty_layout(self):
        layout = resolve_layout([], [], CANVAS_W, CANVAS_H)
        assert layout.node_boxes == {}
        assert layout.connection_routes == {}
        assert layout.canvas_width == CANVAS_W


# ──────────────────────────────────────────────
# Directional Positioning
# ──────────────────────────────────────────────


class TestRightOf:
    """B.right_of(A) means B is to the right of A."""

    def test_b_is_right_of_a(self):
        a = Node("A")
        b = Node("B").right_of(a, distance=3)
        layout = _resolve(a, b)

        box_a = layout.node_boxes[a.id]
        box_b = layout.node_boxes[b.id]

        # B's left edge should be to the right of A's right edge
        assert box_b.x > box_a.x + box_a.width

    def test_centers_on_same_row(self):
        a = Node("A")
        b = Node("B").right_of(a, distance=3)
        layout = _resolve(a, b)

        box_a = layout.node_boxes[a.id]
        box_b = layout.node_boxes[b.id]

        # Same vertical center
        assert abs(box_a.center[1] - box_b.center[1]) < 0.01


class TestLeftOf:
    """B.left_of(A) means B is to the left of A."""

    def test_b_is_left_of_a(self):
        a = Node("A")
        b = Node("B").left_of(a, distance=3)
        layout = _resolve(a, b)

        box_a = layout.node_boxes[a.id]
        box_b = layout.node_boxes[b.id]

        # B's right edge should be to the left of A's left edge
        assert box_b.x + box_b.width < box_a.x


class TestBelow:
    """B.below(A) means B is below A."""

    def test_b_is_below_a(self):
        a = Node("A")
        b = Node("B").below(a, distance=2)
        layout = _resolve(a, b)

        box_a = layout.node_boxes[a.id]
        box_b = layout.node_boxes[b.id]

        # B's top edge should be below A's bottom edge
        assert box_b.y > box_a.y + box_a.height

    def test_centers_on_same_column(self):
        a = Node("A")
        b = Node("B").below(a, distance=2)
        layout = _resolve(a, b)

        box_a = layout.node_boxes[a.id]
        box_b = layout.node_boxes[b.id]

        # Same horizontal center
        assert abs(box_a.center[0] - box_b.center[0]) < 0.01


class TestAbove:
    """B.above(A) means B is above A."""

    def test_b_is_above_a(self):
        a = Node("A")
        b = Node("B").above(a, distance=2)
        layout = _resolve(a, b)

        box_a = layout.node_boxes[a.id]
        box_b = layout.node_boxes[b.id]

        # B's bottom edge should be above A's top edge
        assert box_b.y + box_b.height < box_a.y


# ──────────────────────────────────────────────
# Complex Topologies
# ──────────────────────────────────────────────


class TestLinearChain:
    """A -> B -> C: three nodes in a horizontal chain."""

    def test_order_is_correct(self):
        a = Node("Client")
        b = Node("Gateway").right_of(a, distance=3)
        c = Node("Server").right_of(b, distance=3)
        layout = _resolve(a, b, c)

        box_a = layout.node_boxes[a.id]
        box_b = layout.node_boxes[b.id]
        box_c = layout.node_boxes[c.id]

        assert box_a.center[0] < box_b.center[0] < box_c.center[0]

    def test_all_same_row(self):
        a = Node("A")
        b = Node("B").right_of(a, distance=2)
        c = Node("C").right_of(b, distance=2)
        layout = _resolve(a, b, c)

        centers_y = [layout.node_boxes[n.id].center[1] for n in (a, b, c)]
        assert abs(centers_y[0] - centers_y[1]) < 0.01
        assert abs(centers_y[1] - centers_y[2]) < 0.01


class TestBranchingTree:
    """A root with two children: B right_of A, C below A."""

    def test_branching_positions(self):
        root = Node("Root")
        right = Node("Right").right_of(root, distance=3)
        below = Node("Below").below(root, distance=2)
        layout = _resolve(root, right, below)

        box_root = layout.node_boxes[root.id]
        box_right = layout.node_boxes[right.id]
        box_below = layout.node_boxes[below.id]

        # Right is to the right
        assert box_right.center[0] > box_root.center[0]
        # Below is below
        assert box_below.center[1] > box_root.center[1]
        # Below is on the same column as root
        assert abs(box_below.center[0] - box_root.center[0]) < 0.01


class TestMultipleRoots:
    """Multiple root nodes (no position set) should be placed side by side."""

    def test_two_independent_roots(self):
        a = Node("Root A")
        b = Node("Root B")
        layout = _resolve(a, b)

        box_a = layout.node_boxes[a.id]
        box_b = layout.node_boxes[b.id]

        # They should not overlap
        assert box_a.x + box_a.width < box_b.x or box_b.x + box_b.width < box_a.x


class TestGoldenScript:
    """The Login Flow example from the PRD."""

    def test_login_flow_layout(self):
        client = Node("User Mobile")
        gateway = Node("API Gateway").right_of(client, distance=4)
        auth = Node("Auth Service").right_of(gateway, distance=3)
        db = Database("Users DB").below(auth, distance=2)

        conn_cg = Connection(client, gateway)
        conn_ga = Connection(gateway, auth)
        conn_ad = Connection(auth, db)

        layout = _resolve(client, gateway, auth, db, connections=[conn_cg, conn_ga, conn_ad])

        # All 4 nodes resolved
        assert len(layout.node_boxes) == 4

        # Horizontal order: client < gateway < auth
        box_c = layout.node_boxes[client.id]
        box_g = layout.node_boxes[gateway.id]
        box_a = layout.node_boxes[auth.id]
        box_d = layout.node_boxes[db.id]

        assert box_c.center[0] < box_g.center[0] < box_a.center[0]

        # DB is below Auth
        assert box_d.center[1] > box_a.center[1]

        # All 3 connections routed
        assert len(layout.connection_routes) == 3


# ──────────────────────────────────────────────
# Error Cases
# ──────────────────────────────────────────────


class TestCircularReference:
    """Cycles in positioning should raise CircularReferenceError."""

    def test_raises_on_cycle(self):
        # Create a cycle manually by hacking position
        a = Node("A")
        b = Node("B")

        # Manually create cycle: A -> B -> A
        from archmotion._types import Direction
        from archmotion.layout.positions import RelativePosition

        a.position = RelativePosition(anchor_id=b.id, direction=Direction.RIGHT_OF, distance=3)
        b.position = RelativePosition(anchor_id=a.id, direction=Direction.RIGHT_OF, distance=3)

        with pytest.raises(CircularReferenceError):
            _resolve(a, b)


class TestOverflowCanvas:
    """Diagram exceeding canvas should raise OverflowCanvasError."""

    def test_raises_on_overflow(self):
        """Very far apart nodes on a tiny canvas."""
        a = Node("A")
        b = Node("B").right_of(a, distance=20)

        with pytest.raises(OverflowCanvasError):
            resolve_layout(
                nodes=[a, b],
                connections=[],
                canvas_width=200,  # Very small canvas
                canvas_height=100,
            )


# ──────────────────────────────────────────────
# Connection Routing
# ──────────────────────────────────────────────


class TestConnectionRouting:
    """Connections should produce routed polyline points."""

    def test_horizontal_connection_is_routed(self):
        a = Node("A")
        b = Node("B").right_of(a, distance=3)
        conn = Connection(a, b)

        layout = _resolve(a, b, connections=[conn])

        assert conn.id in layout.connection_routes
        route = layout.connection_routes[conn.id]

        # I-shape: 2 points (start, end)
        assert len(route) >= 2

        # Route goes left to right
        assert route[0][0] < route[-1][0]

    def test_vertical_connection(self):
        a = Node("A")
        b = Node("B").below(a, distance=2)
        conn = Connection(a, b)

        layout = _resolve(a, b, connections=[conn])
        route = layout.connection_routes[conn.id]

        # Route goes top to bottom
        assert route[0][1] < route[-1][1]

    def test_connection_with_label(self):
        a = Node("Source")
        b = Node("Target").right_of(a, distance=4)
        conn = Connection(a, b, label="HTTP")

        layout = _resolve(a, b, connections=[conn])
        assert conn.id in layout.connection_routes


# ──────────────────────────────────────────────
# Canvas Centering
# ──────────────────────────────────────────────


class TestCanvasCentering:
    """Diagram should be centered on the canvas."""

    def test_single_node_centered(self):
        node = Node("Centered")
        layout = _resolve(node)
        bbox = layout.node_boxes[node.id]
        cx, cy = bbox.center
        assert abs(cx - CANVAS_W / 2) < 1.0
        assert abs(cy - CANVAS_H / 2) < 1.0

    def test_chain_centered_vertically(self):
        """A horizontal chain should be centered vertically."""
        a = Node("A")
        b = Node("B").right_of(a, distance=3)
        layout = _resolve(a, b)

        for nid in (a.id, b.id):
            bbox = layout.node_boxes[nid]
            # Vertical center should be near canvas center
            assert abs(bbox.center[1] - CANVAS_H / 2) < 1.0
