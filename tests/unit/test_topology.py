"""Unit tests for Phase 1 — Topology Builder (Nodes, Connections, Scene)."""

from __future__ import annotations

import pytest

from archmotion.api.connections import Connection
from archmotion.api.primitives import Database, Node
from archmotion.api.scene import Scene
from archmotion.errors import InvalidConnectionError, TopologyError


class TestNode:
    """Tests for Node construction and positioning."""

    def test_create_node_with_label(self):
        node = Node("API Gateway")
        assert node.label == "API Gateway"
        assert node.position is None
        assert len(node.id) == 8

    def test_create_node_with_icon(self):
        node = Node("Client", icon="smartphone")
        assert node.icon == "smartphone"

    def test_node_label_stripped(self):
        node = Node("  API Gateway  ")
        assert node.label == "API Gateway"

    def test_node_empty_label_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            Node("")

    def test_node_whitespace_label_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            Node("   ")

    def test_node_label_too_long_raises(self):
        with pytest.raises(ValueError, match="exceeds 50 characters"):
            Node("x" * 51)

    def test_right_of_sets_position(self):
        anchor = Node("A")
        child = Node("B").right_of(anchor, distance=4)
        assert child.position is not None
        assert child.position.anchor_id == anchor.id
        assert child.position.distance == 4

    def test_below_sets_position(self):
        anchor = Node("A")
        child = Node("B").below(anchor, distance=2)
        assert child.position is not None
        assert child.position.distance == 2

    def test_left_of_sets_position(self):
        anchor = Node("A")
        child = Node("B").left_of(anchor, distance=3)
        assert child.position is not None

    def test_above_sets_position(self):
        anchor = Node("A")
        child = Node("B").above(anchor, distance=3)
        assert child.position is not None

    def test_double_positioning_raises(self):
        anchor = Node("A")
        child = Node("B").right_of(anchor)
        with pytest.raises(TopologyError, match="already has a position"):
            child.below(anchor)

    def test_chaining_returns_self(self):
        anchor = Node("A")
        child = Node("B")
        result = child.right_of(anchor)
        assert result is child

    def test_invalid_distance_raises(self):
        anchor = Node("A")
        with pytest.raises(ValueError, match="between"):
            Node("B").right_of(anchor, distance=0)

    def test_distance_too_large_raises(self):
        anchor = Node("A")
        with pytest.raises(ValueError, match="between"):
            Node("B").right_of(anchor, distance=25)


class TestDatabase:
    """Tests for Database (inherits Node)."""

    def test_database_is_node(self):
        db = Database("PostgreSQL")
        assert isinstance(db, Node)

    def test_database_positioning(self):
        server = Node("Server")
        db = Database("Users DB").below(server, distance=2)
        assert db.position is not None


class TestConnection:
    """Tests for Connection construction and validation."""

    def test_create_connection(self):
        a = Node("A")
        b = Node("B")
        conn = Connection(a, b)
        assert conn.source is a
        assert conn.target is b

    def test_self_loop_raises(self):
        a = Node("A")
        with pytest.raises(InvalidConnectionError, match="Self-loop"):
            Connection(a, a)

    def test_connection_with_label(self):
        a, b = Node("A"), Node("B")
        conn = Connection(a, b, label="HTTP")
        assert conn.label == "HTTP"

    def test_connection_label_too_long_raises(self):
        a, b = Node("A"), Node("B")
        with pytest.raises(ValueError, match="exceeds"):
            Connection(a, b, label="x" * 31)

    def test_non_node_source_raises(self):
        with pytest.raises(TypeError, match="must be a Node"):
            Connection("not_a_node", Node("B"))  # type: ignore[arg-type]


class TestScene:
    """Tests for Scene timeline management."""

    def test_scene_defaults(self):
        scene = Scene()
        assert scene.resolution == "1080p"
        assert scene.fps == 60
        assert scene.canvas_size == (1920, 1080)

    def test_scene_720p(self):
        scene = Scene(resolution="720p")
        assert scene.canvas_size == (1280, 720)

    def test_invalid_resolution_raises(self):
        with pytest.raises(ValueError, match="Invalid resolution"):
            Scene(resolution="480p")  # type: ignore[arg-type]

    def test_wait_advances_clock(self):
        scene = Scene()
        scene.wait(2.0)
        assert scene.total_duration == 2.0

    def test_wait_negative_raises(self):
        scene = Scene()
        with pytest.raises(ValueError, match="positive"):
            scene.wait(-1)
