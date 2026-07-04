"""Tests for the architecture domain + cross-domain fusion."""

from __future__ import annotations

import pytest

from archmotion.animation import FadeIn, Transform
from archmotion.core import Scene
from archmotion.domains.architecture import (
    Cache,
    Cloud,
    Connection,
    Database,
    Node,
    Queue,
    User,
)
from archmotion.domains.geometry import Circle, RegularPolygon, Square


def test_node_generates_rounded_rect_points():
    n = Node("API Gateway", center=(100.0, 100.0))
    bbox = n.bounding_box()
    assert bbox.width > 0
    assert bbox.height > 0
    # Rounded rectangle: at least 4 corners worth of curves.
    assert n.n_curves >= 8


def test_database_has_three_contours():
    db = Database("Postgres")
    # Body rectangle + top ellipse + bottom ellipse.
    assert len(db.contour_starts) == 3


def test_queue_is_parallelogram():
    q = Queue("Kafka")
    assert q.n_curves == 4  # four sides


def test_cache_is_diamond():
    c = Cache("Redis")
    assert c.n_curves == 4


def test_cloud_is_single_contour():
    cl = Cloud("S3")
    assert len(cl.contour_starts) == 1
    assert cl.n_curves >= 4


def test_user_has_two_contours():
    u = User("Client")
    assert len(u.contour_starts) == 2  # head + body


def test_connection_routes_between_nodes():
    a = Node("A", center=(0.0, 0.0))
    b = Node("B", center=(300.0, 0.0))
    conn = Connection(a, b)
    pts = conn.points
    assert pts.shape[0] >= 2
    # Route starts near A's right edge.
    assert pts[0][0] > 0.0


def test_node_can_transform_to_circle_fusion():
    """Cross-domain fusion: an architecture node morphs into a geometry circle."""
    sc = Scene(fps=30)
    node = Node("Service", center=(200.0, 200.0))
    sc.add(node)
    sc.play(FadeIn(node))
    sc.play(Transform(node, Circle(radius=60.0).move_to(200.0, 200.0)))
    tl = sc.compile_timeline()
    assert any(m.target_id == node.id for m in tl.morph_actions)


def test_node_can_transform_to_square():
    sc = Scene(fps=30)
    node = Node("X", center=(100.0, 100.0))
    sc.add(node)
    sc.play(Transform(node, Square(side=80.0).move_to(100.0, 100.0)))
    tl = sc.compile_timeline()
    assert any(m.target_id == node.id for m in tl.morph_actions)


def test_architecture_and_geometry_in_one_scene():
    """True fusion: architecture nodes + a geometry chart-shape coexist."""
    sc = Scene(fps=30, resolution=(640, 360))
    gw = Node("Gateway", center=(160.0, 180.0))
    db = Database("DB", center=(480.0, 180.0))
    hexagon = RegularPolygon(n=6, radius=40.0).move_to(320.0, 60.0)
    sc.add(gw, db, hexagon)
    sc.play(FadeIn(gw, db), Transform(hexagon, Circle(radius=40.0).move_to(320.0, 60.0)))
    tl = sc.compile_timeline()
    assert len(tl.morph_actions) >= 1
    # All three graphics render via the generic path renderer.
    from archmotion.render.path_render import resolve_effective

    for graphic in (gw, db, hexagon):
        state = resolve_effective(graphic, None, None, sc.camera)
        assert state.points.shape[0] >= 2
