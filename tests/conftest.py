"""Shared pytest fixtures for ArchMotion tests."""

from __future__ import annotations

import pytest

from archmotion.api.connections import Connection
from archmotion.api.primitives import Database, Node
from archmotion.api.scene import Scene


@pytest.fixture
def simple_node() -> Node:
    """A basic Node fixture."""
    return Node("API Gateway")


@pytest.fixture
def simple_db() -> Database:
    """A basic Database fixture."""
    return Database("PostgreSQL")


@pytest.fixture
def two_nodes() -> tuple[Node, Node]:
    """Two connected nodes: client → server."""
    client = Node("Client")
    server = Node("Server").right_of(client, distance=4)
    return (client, server)


@pytest.fixture
def scene_with_topology() -> Scene:
    """Scene with a basic 3-node topology pre-configured."""
    scene = Scene(resolution="1080p", fps=60)
    client = Node("Client")
    server = Node("API Server").right_of(client, distance=4)
    db = Database("PostgreSQL").below(server, distance=2)
    Connection(client, server)
    Connection(server, db)
    return scene
