"""Parity + integration tests for the v2 architecture domain.

Verifies that the v2 architecture pipeline (relative positioning →
``resolve_architecture`` → A*/Manhattan routing → Packet/Transfer) reproduces
v1 layout geometry, routes connections correctly, positions packets along their
connection via PATH_PROGRESS, and raises the same layout errors as v1.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from archmotion.animation import FadeIn, Transfer
from archmotion.api.connections import Connection as V1Connection
from archmotion.api.primitives import Node as V1Node
from archmotion.core import Property, Scene
from archmotion.core.camera import Camera
from archmotion.core.transform import Transform as AffineTransform
from archmotion.domains.architecture import (
    Cache,
    Cloud,
    Connection,
    Database,
    Node,
    Packet,
    Queue,
    User,
    resolve_architecture,
)
from archmotion.errors import (
    CircularReferenceError,
    OrphanNodeError,
    OverflowCanvasError,
    TopologyError,
)
from archmotion.layout.resolver import resolve_layout
from archmotion.render.path_render import resolve_effective

CANVAS_W, CANVAS_H = 1280, 720


# ── positioning API ──────────────────────────────────────────────


def test_right_of_sets_relative_constraint():
    a = Node("A")
    b = Node("B").right_of(a, distance=4)
    assert b.position is not None
    assert b.position.anchor_id == a.id


def test_at_sets_absolute_constraint():
    n = Node("X").at(100, 200)
    assert n.position is not None
    assert (n.position.x, n.position.y) == (100.0, 200.0)


def test_double_positioning_raises():
    a = Node("A")
    b = Node("B").right_of(a)
    with pytest.raises(TopologyError):
        b.right_of(a)


def test_negative_absolute_raises():
    with pytest.raises(ValueError, match="non-negative"):
        Node("X").at(-1, 0)


def test_all_primitives_are_positionable():
    a = Node("A")
    for cls in (Database, Cloud, Queue, Cache, User):
        child = cls("c").right_of(a)
        assert child.position is not None


# ── coordinate parity vs v1 (same labels/distances → same geometry) ──


def _boxes_by_label(scene: Scene) -> dict[str, tuple[float, float, float, float]]:
    layout = resolve_architecture(scene)
    from archmotion.domains.architecture.primitives import Node as V2Node

    out: dict[str, tuple[float, float, float, float]] = {}
    for g in scene.all_graphics():
        if isinstance(g, V2Node):
            box = layout.node_boxes[g.id]
            out[g.label] = (box.x, box.y, box.width, box.height)
    return out


def test_v2_layout_matches_v1_geometry():
    # v2 scene
    v2 = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    client = Node("Client")
    server = Node("API Server").right_of(client, distance=4)
    db = Database("PostgreSQL").right_of(server, distance=3)
    v2.add(client, server, db, Connection(client, server), Connection(server, db))
    v2_boxes = _boxes_by_label(v2)

    # Equivalent v1 topology
    c1 = V1Node("Client")
    s1 = V1Node("API Server").right_of(c1, distance=4)
    d1 = V1Node("PostgreSQL").right_of(s1, distance=3)
    v1_layout = resolve_layout(
        [c1, s1, d1], [V1Connection(c1, s1), V1Connection(s1, d1)], CANVAS_W, CANVAS_H
    )
    v1_boxes = {
        n.label: (v1_layout.node_boxes[n.id].x, v1_layout.node_boxes[n.id].y,
                  v1_layout.node_boxes[n.id].width, v1_layout.node_boxes[n.id].height)
        for n in (c1, s1, d1)
    }

    assert set(v2_boxes) == set(v1_boxes)
    for label in v1_boxes:
        assert v2_boxes[label] == pytest.approx(v1_boxes[label])


def test_resolved_centers_applied_to_nodes():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    a = Node("A")
    b = Node("B").right_of(a, distance=4)
    scene.add(a, b, Connection(a, b))
    layout = resolve_architecture(scene)

    for node in (a, b):
        box = layout.node_boxes[node.id]
        cx, cy = node.bounding_box().center
        assert (cx, cy) == pytest.approx(box.center)


def test_connection_routed_after_resolve():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    a = Node("Alpha")
    b = Node("Beta").right_of(a, distance=4)
    conn = Connection(a, b)
    scene.add(a, b, conn)
    layout = resolve_architecture(scene)

    route = layout.connection_routes[conn.id]
    assert len(route) >= 2
    # The connection's sampled route endpoints match the resolved route.
    assert conn.point_at_progress(0.0) == pytest.approx(route[0])
    assert conn.point_at_progress(1.0) == pytest.approx(route[-1])


def test_rounded_corners_do_not_change_route():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    a = Node("A")
    b = Node("B").below(a, distance=3)
    conn = Connection(a, b, corner_radius=12.0)
    scene.add(a, b, conn)
    layout = resolve_architecture(scene, corner_radius=12.0)
    # Rounded corners refine the path but the resolved polyline is unchanged.
    assert len(layout.connection_routes[conn.id]) >= 2
    assert conn.point_at_progress(1.0) == pytest.approx(layout.connection_routes[conn.id][-1])


# ── Packet / Transfer / PATH_PROGRESS ────────────────────────────


def test_transfer_auto_creates_packet_bound_to_connection():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    a = Node("A")
    b = Node("B").right_of(a, distance=4)
    conn = Connection(a, b)
    scene.add(a, b, conn)
    resolve_architecture(scene)

    scene.play(Transfer(conn, run_time=1.0, payload="GET"))
    tl = scene.compile_timeline()
    progress = [act for act in tl.property_actions if act.prop == Property.PATH_PROGRESS]
    assert len(progress) == 1
    assert progress[0].start_value == pytest.approx(0.0)
    assert progress[0].end_value == pytest.approx(1.0)


def test_packet_reverse_transfer():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    a = Node("A")
    b = Node("B").right_of(a, distance=4)
    conn = Connection(a, b)
    scene.add(a, b, conn)
    resolve_architecture(scene)

    scene.play(Transfer(conn, reverse=True, run_time=1.0))
    tl = scene.compile_timeline()
    progress = next(
        act for act in tl.property_actions if act.prop == Property.PATH_PROGRESS
    )
    assert progress.start_value == pytest.approx(1.0)
    assert progress.end_value == pytest.approx(0.0)


def test_path_progress_positions_packet_along_route():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    a = Node("A")
    b = Node("B").right_of(a, distance=4)
    conn = Connection(a, b)
    packet = Packet(connection=conn)
    scene.add(a, b, conn, packet)
    resolve_architecture(scene)

    cam = Camera(CANVAS_W, CANVAS_H)
    midpoint = conn.point_at_progress(0.5)

    state = resolve_effective(packet, {Property.PATH_PROGRESS: 0.5}, None, cam)
    # Apply the resolved matrix to the packet's own center: it should land on
    # the route midpoint (PATH_PROGRESS drives the packet's position).
    pcx, pcy = packet.bounding_box().center
    placed = AffineTransform(state.matrix).apply_to_points([(pcx, pcy)])[0]
    assert (placed[0], placed[1]) == pytest.approx(midpoint, abs=1.0)


# ── error parity ─────────────────────────────────────────────────


def test_orphan_anchor_raises():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    ghost = Node("Ghost")  # not added to the scene
    b = Node("B").right_of(ghost)
    scene.add(b)
    with pytest.raises(OrphanNodeError):
        resolve_architecture(scene)


def test_cycle_raises():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    a = Node("A")
    b = Node("B").right_of(a)
    a.below(b)  # cycle: A -> B -> A
    scene.add(a, b)
    with pytest.raises(CircularReferenceError):
        resolve_architecture(scene)


def test_overflow_raises():
    scene = Scene(resolution=(320, 180), fps=30)
    nodes = [Node(f"N{i}") for i in range(8)]
    for prev, nxt in pairwise(nodes):
        nxt.right_of(prev, distance=8)
    for n in nodes:
        scene.add(n)
    with pytest.raises(OverflowCanvasError):
        resolve_architecture(scene)


# ── end-to-end smoke (compile + resolve_effective on all graphics) ──


def test_full_scene_resolves_and_renders_state():
    scene = Scene(resolution=(CANVAS_W, CANVAS_H), fps=30)
    client = Node("Client")
    server = Node("API").right_of(client, distance=4)
    db = Database("DB").right_of(server, distance=3)
    c1 = Connection(client, server)
    c2 = Connection(server, db)
    scene.add(client, server, db, c1, c2)
    resolve_architecture(scene, corner_radius=12.0)

    scene.play(FadeIn(client, server, db, c1, c2, run_time=0.5))
    scene.play(Transfer(c1, run_time=1.0, payload="GET"))
    tl = scene.compile_timeline()
    assert tl.total_frames > 0

    # Every graphic resolves to a paintable state at frame 0.
    cam = Camera(CANVAS_W, CANVAS_H)
    snap = tl.snapshot_at_frame(0)
    for g in scene.all_graphics():
        state = resolve_effective(
            g, snap.scalars.get(g.id), snap.morphs.get(g.id), cam
        )
        assert state.points.shape[0] >= 2
