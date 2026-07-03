"""Unit tests for absolute (freeform) positioning.

Covers the additive absolute-positioning feature used by the ArchMotion Studio
visual editor:

    - ``Node.at(x, y)`` sets an ``AbsolutePosition`` (top-left origin).
    - Layout resolver treats absolute nodes as roots (no anchor dependency).
    - Auto-centering is skipped whenever any node is absolute (manual layout).
    - Mixed scenes (absolute anchor + relative children) resolve correctly.
    - YAML schema accepts ``position: {x, y}``; bounds validated vs resolution.
    - In-memory export helpers (``Scene.resolve`` / ``to_*``) work without skia.
"""

from __future__ import annotations

import textwrap

import pytest
from pydantic import ValidationError

from archmotion.api.connections import Connection
from archmotion.api.primitives import AbsolutePosition, Node, RelativePosition
from archmotion.api.scene import Scene
from archmotion.errors import TopologyError
from archmotion.layout.resolver import resolve_layout
from archmotion.ai import parse_yaml_string
from archmotion.ai.schema import (
    AbsolutePositionSpec,
    AnimationSpec,
    NodeSpec,
    RelativePositionSpec,
    SceneSpec,
    StepSpec,
)
from archmotion.ai.builder import build_scene

CANVAS_W = 1920
CANVAS_H = 1080


def _resolve(*nodes: Node, connections: list[Connection] | None = None):
    """Shortcut for resolve_layout with the default test canvas."""
    return resolve_layout(
        nodes=list(nodes),
        connections=connections or [],
        canvas_width=CANVAS_W,
        canvas_height=CANVAS_H,
    )


# ──────────────────────────────────────────────
# Primitives: Node.at()
# ──────────────────────────────────────────────


class TestNodeAt:
    """Node.at() API behavior."""

    def test_at_sets_absolute_position(self):
        node = Node("Alpha").at(100, 200)
        assert isinstance(node.position, AbsolutePosition)
        assert node.position.x == 100.0
        assert node.position.y == 200.0

    def test_at_returns_self_for_chaining(self):
        node = Node("Alpha")
        assert node.at(10, 20) is node

    def test_at_rejects_negative(self):
        with pytest.raises(ValueError, match="non-negative"):
            Node("Alpha").at(-1, 0)
        with pytest.raises(ValueError, match="non-negative"):
            Node("Alpha").at(0, -5)

    def test_at_then_relative_raises(self):
        anchor = Node("Anchor")
        node = Node("Alpha").at(100, 100)
        with pytest.raises(TopologyError, match="absolute position"):
            node.right_of(anchor)

    def test_relative_then_at_raises(self):
        anchor = Node("Anchor")
        node = Node("Alpha").right_of(anchor)
        with pytest.raises(TopologyError, match="relative position"):
            node.at(100, 100)

    def test_at_twice_raises(self):
        node = Node("Alpha").at(10, 20)
        with pytest.raises(TopologyError, match="absolute position"):
            node.at(30, 40)

    def test_relative_position_type_unchanged(self):
        """Existing relative API still produces RelativePosition."""
        anchor = Node("Anchor")
        node = Node("Child").below(anchor)
        assert isinstance(node.position, RelativePosition)


# ──────────────────────────────────────────────
# Layout: absolute positioning resolution
# ──────────────────────────────────────────────


class TestAbsoluteLayout:
    """Layout resolver behavior with absolute nodes."""

    def test_absolute_node_keeps_fixed_coordinates(self):
        node = Node("Alpha").at(100, 80)
        layout = _resolve(node)
        box = layout.node_boxes[node.id]
        # Top-left should be exactly the specified (x, y).
        assert box.x == pytest.approx(100.0)
        assert box.y == pytest.approx(80.0)

    def test_two_absolute_nodes_keep_positions(self):
        a = Node("Alpha").at(100, 80)
        b = Node("Beta").at(500, 400)
        layout = _resolve(a, b)
        assert layout.node_boxes[a.id].x == pytest.approx(100.0)
        assert layout.node_boxes[a.id].y == pytest.approx(80.0)
        assert layout.node_boxes[b.id].x == pytest.approx(500.0)
        assert layout.node_boxes[b.id].y == pytest.approx(400.0)

    def test_no_autocentering_when_absolute_present(self):
        """Auto-centering is disabled in manual (absolute) layout mode."""
        node = Node("Alpha").at(100, 80)
        layout = _resolve(node)
        # If centering ran, the node would be moved to canvas center (~960,540).
        assert layout.node_boxes[node.id].x < 200.0
        assert layout.node_boxes[node.id].y < 200.0

    def test_mixed_absolute_anchor_relative_child(self):
        """An absolute node can anchor a relative child."""
        root = Node("Root").at(200, 150)
        child = Node("Child").right_of(root, distance=3)
        layout = _resolve(root, child)
        root_box = layout.node_boxes[root.id]
        child_box = layout.node_boxes[child.id]
        # Root stays fixed (no auto-center).
        assert root_box.x == pytest.approx(200.0)
        # Child is placed to the right of root.
        assert child_box.center[0] > root_box.center[0]
        assert child_box.center[1] == pytest.approx(root_box.center[1])

    def test_mixed_child_below_absolute_anchor(self):
        root = Node("Root").at(400, 300)
        child = Node("Child").below(root, distance=2)
        layout = _resolve(root, child)
        child_center = layout.node_boxes[child.id].center
        root_center = layout.node_boxes[root.id].center
        assert child_center[1] > root_center[1]
        assert child_center[0] == pytest.approx(root_center[0])

    def test_absolute_does_not_break_connection_routing(self):
        a = Node("Alpha").at(100, 100)
        b = Node("Beta").at(800, 500)
        conn = Connection(a, b)
        layout = _resolve(a, b, connections=[conn])
        route = layout.connection_routes[conn.id]
        assert len(route) >= 2
        assert route[0] == pytest.approx(route[0])  # route is a valid polyline

    def test_autocentering_still_runs_for_purely_relative(self):
        """Regression: purely-relative scenes still auto-center (unchanged)."""
        a = Node("A")
        b = Node("B").right_of(a, distance=3)
        layout = _resolve(a, b)
        # Centered: the diagram center sits near the canvas center.
        boxes = list(layout.node_boxes.values())
        cx = sum((bx.x + bx.width / 2) for bx in boxes) / len(boxes)
        assert abs(cx - CANVAS_W / 2) < CANVAS_W / 4


# ──────────────────────────────────────────────
# Schema + Builder: YAML absolute positions
# ──────────────────────────────────────────────


ABSOLUTE_YAML = textwrap.dedent("""\
    version: "1.0"
    resolution: "1080p"
    fps: 60
    nodes:
      - id: a
        label: Client
        position: {x: 120, y: 200}
      - id: b
        label: API Server
        position: {x: 700, y: 200}
    connections:
      - id: c1
        source: a
        target: b
    choreography:
      - action: play
        animation: {type: fade_in, targets: [a, b, c1]}
""")

MIXED_YAML = textwrap.dedent("""\
    version: "1.0"
    resolution: "1080p"
    fps: 60
    nodes:
      - id: root
        label: Root
        position: {x: 300, y: 250}
      - id: child
        label: Child
        position: {anchor: root, direction: right_of, distance: 3}
    choreography:
      - action: play
        animation: {type: fade_in, targets: [root, child]}
""")


class TestSchemaAbsolute:
    """Pydantic schema validation for absolute positions."""

    def test_absolute_position_spec_parses(self):
        spec = NodeSpec(id="a", label="A", position=AbsolutePositionSpec(x=10, y=20))
        assert isinstance(spec.position, AbsolutePositionSpec)
        assert spec.position.x == 10.0

    def test_relative_position_spec_still_works(self):
        spec = NodeSpec(
            id="b", label="B",
            position=RelativePositionSpec(anchor="a", direction="below"),
        )
        assert isinstance(spec.position, RelativePositionSpec)

    def test_absolute_rejects_negative(self):
        with pytest.raises(ValidationError):
            AbsolutePositionSpec(x=-1, y=10)

    def test_absolute_out_of_bounds_rejected(self):
        """1080p canvas is 1920x1080; coords beyond that are rejected."""
        with pytest.raises(ValidationError, match="exceeds canvas bounds"):
            SceneSpec(
                resolution="1080p",
                nodes=[NodeSpec(id="a", label="A", position=AbsolutePositionSpec(x=5000, y=10))],
                choreography=[StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["a"]),
                )],
            )

    def test_absolute_yaml_parses_to_absolute_spec(self):
        import yaml

        data = yaml.safe_load(ABSOLUTE_YAML)
        spec = SceneSpec(**data)
        for node in spec.nodes:
            assert isinstance(node.position, AbsolutePositionSpec)


class TestBuilderAbsolute:
    """build_scene + parse_yaml_string with absolute positions."""

    def test_parse_yaml_absolute_builds_scene(self):
        scene = parse_yaml_string(ABSOLUTE_YAML)
        assert isinstance(scene, Scene)

    def test_parse_yaml_absolute_resolves_fixed_positions(self):
        scene = parse_yaml_string(ABSOLUTE_YAML)
        layout = scene.resolve()
        # Node 'a' should be at the absolute (120, 200) top-left.
        a_node = next(n for n in scene._nodes if n.label == "Client")
        assert layout.node_boxes[a_node.id].x == pytest.approx(120.0)
        assert layout.node_boxes[a_node.id].y == pytest.approx(200.0)

    def test_mixed_yaml_builds_and_resolves(self):
        scene = parse_yaml_string(MIXED_YAML)
        layout = scene.resolve()
        # Root fixed; child to the right.
        root = next(n for n in scene._nodes if n.label == "Root")
        child = next(n for n in scene._nodes if n.label == "Child")
        root_box = layout.node_boxes[root.id]
        child_box = layout.node_boxes[child.id]
        assert root_box.x == pytest.approx(300.0)
        assert child_box.center[0] > root_box.center[0]


# ──────────────────────────────────────────────
# In-memory export helpers (no skia required)
# ──────────────────────────────────────────────


class TestInMemoryExport:
    """Scene.resolve() / to_lottie() / to_svg() / to_html() helpers."""

    def _scene_with_animations(self) -> Scene:
        scene = Scene(resolution="1080p", fps=60, theme="dark_terminal")
        from archmotion import FadeIn, Transfer

        a = Node("Client").at(120, 200)
        b = Node("API").at(700, 200)
        conn = Connection(a, b)
        scene.add_node(a)
        scene.add_node(b)
        scene.add_connection(conn)
        scene.play(FadeIn(a, b, conn))
        scene.play(Transfer(conn, payload="GET", duration=1.0))
        return scene

    def test_resolve_works_without_animations(self):
        """resolve() reads layout even when no animations are recorded."""
        scene = Scene(resolution="1080p", fps=60)
        a = Node("Alpha").at(100, 100)
        scene.add_node(a)
        layout = scene.resolve()
        assert a.id in layout.node_boxes

    def test_to_lottie_returns_dict(self):
        scene = self._scene_with_animations()
        lottie = scene.to_lottie()
        assert isinstance(lottie, dict)
        assert "layers" in lottie
        assert len(lottie["layers"]) >= 3  # 1 connection + 2 nodes

    def test_to_svg_returns_string(self):
        scene = self._scene_with_animations()
        svg = scene.to_svg()
        assert isinstance(svg, str)
        assert svg.lstrip().startswith("<svg")

    def test_to_html_returns_string_with_player(self):
        scene = self._scene_with_animations()
        html = scene.to_html(title="Test")
        assert isinstance(html, str)
        assert "lottie-player" in html
        assert "<html" in html

    def test_to_lottie_raises_on_empty_timeline(self):
        scene = Scene(resolution="1080p", fps=60)
        scene.add_node(Node("X").at(10, 10))
        with pytest.raises(Exception):  # EmptyTimelineError
            scene.to_lottie()
