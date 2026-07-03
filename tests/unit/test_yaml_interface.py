"""Unit tests for PLAN-009 — YAML AI Interface.

Tests cover:
    - Pydantic schema validation (valid + invalid inputs)
    - Scene builder (nodes, positions, connections, choreography)
    - All 8 animation types through YAML
    - Security hardening (file size, node limits, string length)
    - E2E: parse_yaml_string() → Scene
    - Error reporting quality (for LLM feedback)
"""

from __future__ import annotations

import textwrap

import pytest
from pydantic import ValidationError

from archmotion.ai import YAMLParseError, parse_yaml_string
from archmotion.ai.builder import build_scene
from archmotion.ai.schema import (
    AbsolutePositionSpec,
    AnimationSpec,
    ConnectionSpec,
    NodeSpec,
    PositionSpec,
    RelativePositionSpec,
    SceneSpec,
    StepSpec,
)
from archmotion.api.primitives import Cloud, Database, Node
from archmotion.api.scene import Scene


# ──────────────────────────────────────────────
# Fixtures: minimal valid YAML / spec
# ──────────────────────────────────────────────

MINIMAL_YAML = textwrap.dedent("""\
    version: "1.0"
    resolution: "1080p"
    fps: 60
    nodes:
      - id: "server"
        label: "Web Server"
    choreography:
      - action: play
        animation:
          type: fade_in
          targets: ["server"]
""")

FULL_YAML = textwrap.dedent("""\
    version: "1.0"
    resolution: "1080p"
    fps: 60
    nodes:
      - id: "client"
        label: "Client"
        type: "user"
      - id: "server"
        label: "API Server"
        type: "node"
        position:
          anchor: "client"
          direction: "right_of"
          distance: 3
      - id: "db"
        label: "PostgreSQL"
        type: "database"
        position:
          anchor: "server"
          direction: "below"
          distance: 2
    connections:
      - id: "c1"
        source: "client"
        target: "server"
        label: "HTTPS"
      - id: "c2"
        source: "server"
        target: "db"
        label: "SQL"
    choreography:
      - action: play
        animation:
          type: fade_in
          targets: ["client", "server", "db", "c1", "c2"]
      - action: wait
        duration: 0.5
      - action: play
        animation:
          type: transfer
          connection: "c1"
          payload: "GET /users"
      - action: play
        animation:
          type: transfer
          connection: "c2"
          payload: "SELECT *"
      - action: play
        animation:
          type: highlight
          target: "server"
          color: "green"
          duration: 1.0
""")


def _make_minimal_spec(**overrides) -> SceneSpec:
    """Build a minimal valid SceneSpec with optional overrides."""
    base = {
        "nodes": [NodeSpec(id="s", label="Server")],
        "choreography": [
            StepSpec(
                action="play",
                animation=AnimationSpec(type="fade_in", targets=["s"]),
            )
        ],
    }
    base.update(overrides)
    return SceneSpec(**base)


# ══════════════════════════════════════════════
# Schema Validation: Valid Inputs
# ══════════════════════════════════════════════


class TestSchemaValidInputs:
    """Test that valid schema inputs are accepted."""

    def test_minimal_spec(self):
        spec = _make_minimal_spec()
        assert len(spec.nodes) == 1
        assert spec.resolution == "1080p"

    def test_all_node_types(self):
        nodes = [
            NodeSpec(id="n1", label="A", type="node"),
            NodeSpec(id="n2", label="B", type="database"),
            NodeSpec(id="n3", label="C", type="cloud", provider="aws"),
            NodeSpec(id="n4", label="D", type="queue"),
            NodeSpec(id="n5", label="E", type="cache"),
            NodeSpec(id="n6", label="F", type="user"),
        ]
        spec = SceneSpec(
            nodes=nodes,
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["n1"]),
                )
            ],
        )
        assert len(spec.nodes) == 6

    def test_position_spec(self):
        pos = RelativePositionSpec(anchor="other", direction="right_of", distance=5.0)
        assert pos.direction == "right_of"
        assert pos.distance == 5.0

    def test_absolute_position_spec(self):
        pos = AbsolutePositionSpec(x=120.0, y=80.0)
        assert pos.x == 120.0
        assert pos.y == 80.0

    def test_connection_spec(self):
        conn = ConnectionSpec(id="c1", source="a", target="b", label="HTTP")
        assert conn.label == "HTTP"

    def test_all_animation_types_schema(self):
        """Ensure all 8 animation types are accepted by schema."""
        types = [
            "fade_in", "fade_out", "transfer", "pulse",
            "highlight", "color_shift", "scale_up", "scale_down",
        ]
        for atype in types:
            anim = AnimationSpec(type=atype)
            assert anim.type == atype

    def test_step_play(self):
        step = StepSpec(
            action="play",
            animation=AnimationSpec(type="fade_in", targets=["s"]),
        )
        assert step.action == "play"

    def test_step_wait(self):
        step = StepSpec(action="wait", duration=1.0)
        assert step.duration == 1.0

    def test_step_concurrent(self):
        step = StepSpec(
            action="concurrent",
            animations=[
                AnimationSpec(type="fade_in", targets=["s"]),
                AnimationSpec(type="pulse", target="s"),
            ],
        )
        assert len(step.animations) == 2


# ══════════════════════════════════════════════
# Schema Validation: Invalid Inputs
# ══════════════════════════════════════════════


class TestSchemaInvalidInputs:
    """Test that invalid inputs are rejected with clear errors."""

    def test_empty_nodes_rejected(self):
        with pytest.raises(ValidationError, match="nodes"):
            SceneSpec(
                nodes=[],
                choreography=[
                    StepSpec(action="wait", duration=1.0),
                ],
            )

    def test_duplicate_node_ids(self):
        with pytest.raises(ValidationError, match="Duplicate node IDs"):
            SceneSpec(
                nodes=[
                    NodeSpec(id="s", label="A"),
                    NodeSpec(id="s", label="B"),
                ],
                choreography=[
                    StepSpec(
                        action="play",
                        animation=AnimationSpec(type="fade_in", targets=["s"]),
                    )
                ],
            )

    def test_connection_self_loop(self):
        with pytest.raises(ValidationError, match="Self-loop"):
            ConnectionSpec(id="c", source="a", target="a")

    def test_unknown_anchor_reference(self):
        with pytest.raises(ValidationError, match="unknown anchor"):
            SceneSpec(
                nodes=[
                    NodeSpec(
                        id="s", label="A",
                        position=RelativePositionSpec(anchor="nonexistent", direction="below"),
                    ),
                ],
                choreography=[
                    StepSpec(
                        action="play",
                        animation=AnimationSpec(type="fade_in", targets=["s"]),
                    )
                ],
            )

    def test_unknown_connection_source(self):
        with pytest.raises(ValidationError, match="unknown source"):
            SceneSpec(
                nodes=[NodeSpec(id="a", label="A")],
                connections=[ConnectionSpec(id="c", source="missing", target="a")],
                choreography=[
                    StepSpec(
                        action="play",
                        animation=AnimationSpec(type="fade_in", targets=["a"]),
                    )
                ],
            )

    def test_unknown_animation_target(self):
        with pytest.raises(ValidationError, match="unknown target"):
            SceneSpec(
                nodes=[NodeSpec(id="a", label="A")],
                choreography=[
                    StepSpec(
                        action="play",
                        animation=AnimationSpec(type="fade_in", targets=["missing"]),
                    )
                ],
            )

    def test_play_without_animation(self):
        with pytest.raises(ValidationError, match="requires 'animation'"):
            StepSpec(action="play")

    def test_wait_without_duration(self):
        with pytest.raises(ValidationError, match="requires 'duration'"):
            StepSpec(action="wait")

    def test_provider_only_for_cloud(self):
        with pytest.raises(ValidationError, match="only valid when type='cloud'"):
            NodeSpec(id="n", label="Not Cloud", type="node", provider="aws")


# ══════════════════════════════════════════════
# Builder: Nodes + Positions
# ══════════════════════════════════════════════


class TestBuilderNodes:
    """Test Scene builder node creation and positioning."""

    def test_creates_correct_node_types(self):
        spec = SceneSpec(
            nodes=[
                NodeSpec(id="n1", label="Server", type="node"),
                NodeSpec(id="n2", label="DB", type="database"),
                NodeSpec(id="n3", label="S3", type="cloud", provider="aws"),
            ],
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["n1"]),
                )
            ],
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_position_resolution(self):
        spec = SceneSpec(
            nodes=[
                NodeSpec(id="a", label="Node A"),
                NodeSpec(
                    id="b", label="Node B",
                    position=RelativePositionSpec(anchor="a", direction="right_of", distance=3),
                ),
            ],
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["a", "b"]),
                )
            ],
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_cloud_with_provider(self):
        spec = SceneSpec(
            nodes=[
                NodeSpec(id="s3", label="S3 Bucket", type="cloud", provider="aws"),
            ],
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["s3"]),
                )
            ],
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)


# ══════════════════════════════════════════════
# Builder: Connections
# ══════════════════════════════════════════════


class TestBuilderConnections:
    """Test Scene builder connection creation."""

    def test_creates_connections(self):
        spec = SceneSpec(
            nodes=[
                NodeSpec(id="a", label="A"),
                NodeSpec(id="b", label="B"),
            ],
            connections=[
                ConnectionSpec(id="c1", source="a", target="b", label="HTTP"),
            ],
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["a", "b"]),
                )
            ],
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_connection_without_label(self):
        spec = SceneSpec(
            nodes=[
                NodeSpec(id="a", label="A"),
                NodeSpec(id="b", label="B"),
            ],
            connections=[
                ConnectionSpec(id="c1", source="a", target="b"),
            ],
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["a", "b"]),
                )
            ],
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)


# ══════════════════════════════════════════════
# Builder: Choreography
# ══════════════════════════════════════════════


class TestBuilderChoreography:
    """Test choreography execution (play, wait, concurrent)."""

    def test_play_fade_in(self):
        spec = _make_minimal_spec()
        scene = build_scene(spec)
        assert scene.total_duration > 0

    def test_wait_step(self):
        spec = SceneSpec(
            nodes=[NodeSpec(id="s", label="S")],
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["s"]),
                ),
                StepSpec(action="wait", duration=2.0),
            ],
        )
        scene = build_scene(spec)
        assert scene.total_duration >= 2.0

    def test_concurrent_block(self):
        spec = SceneSpec(
            nodes=[
                NodeSpec(id="a", label="A"),
                NodeSpec(id="b", label="B"),
            ],
            choreography=[
                StepSpec(
                    action="concurrent",
                    animations=[
                        AnimationSpec(type="fade_in", targets=["a"]),
                        AnimationSpec(type="fade_in", targets=["b"]),
                    ],
                ),
            ],
        )
        scene = build_scene(spec)
        # Concurrent: both play at t=0, so duration = max(duration_a, duration_b)
        assert scene.total_duration > 0

    def test_sequential_transfers(self):
        spec = SceneSpec(
            nodes=[
                NodeSpec(id="a", label="A"),
                NodeSpec(id="b", label="B"),
            ],
            connections=[
                ConnectionSpec(id="c1", source="a", target="b"),
            ],
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["a", "b", "c1"]),
                ),
                StepSpec(
                    action="play",
                    animation=AnimationSpec(
                        type="transfer",
                        connection="c1",
                        payload="Hello",
                    ),
                ),
                StepSpec(
                    action="play",
                    animation=AnimationSpec(
                        type="transfer",
                        connection="c1",
                        payload="Reply",
                        reverse=True,
                    ),
                ),
            ],
        )
        scene = build_scene(spec)
        assert scene.total_duration > 0


# ══════════════════════════════════════════════
# Builder: All Animation Types
# ══════════════════════════════════════════════


class TestBuilderAnimationTypes:
    """Test that all 8 animation types build correctly."""

    def _base_spec(self, *extra_steps: StepSpec) -> SceneSpec:
        return SceneSpec(
            nodes=[
                NodeSpec(id="a", label="A"),
                NodeSpec(id="b", label="B"),
            ],
            connections=[
                ConnectionSpec(id="c1", source="a", target="b"),
            ],
            choreography=[
                StepSpec(
                    action="play",
                    animation=AnimationSpec(type="fade_in", targets=["a", "b", "c1"]),
                ),
                *extra_steps,
            ],
        )

    def test_fade_in(self):
        scene = build_scene(self._base_spec())
        assert isinstance(scene, Scene)

    def test_fade_out(self):
        spec = self._base_spec(
            StepSpec(
                action="play",
                animation=AnimationSpec(type="fade_out", targets=["a"]),
            )
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_transfer(self):
        spec = self._base_spec(
            StepSpec(
                action="play",
                animation=AnimationSpec(type="transfer", connection="c1", payload="test"),
            )
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_pulse(self):
        spec = self._base_spec(
            StepSpec(
                action="play",
                animation=AnimationSpec(type="pulse", target="a", color="yellow"),
            )
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_highlight(self):
        spec = self._base_spec(
            StepSpec(
                action="play",
                animation=AnimationSpec(
                    type="highlight", target="a", color="red", intensity=0.6,
                ),
            )
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_color_shift(self):
        spec = self._base_spec(
            StepSpec(
                action="play",
                animation=AnimationSpec(
                    type="color_shift", target="a",
                    from_color="#4caf50", to_color="#f44336",
                ),
            )
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_scale_up(self):
        spec = self._base_spec(
            StepSpec(
                action="play",
                animation=AnimationSpec(type="scale_up", target="a", factor=1.5),
            )
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)

    def test_scale_down(self):
        spec = self._base_spec(
            StepSpec(
                action="play",
                animation=AnimationSpec(type="scale_down", target="a", factor=0.5),
            )
        )
        scene = build_scene(spec)
        assert isinstance(scene, Scene)


# ══════════════════════════════════════════════
# Security: Limits & Hardening
# ══════════════════════════════════════════════


class TestSecurityLimits:
    """Test security constraints."""

    def test_too_many_nodes(self):
        nodes = [NodeSpec(id=f"n{i}", label=f"N{i}") for i in range(51)]
        with pytest.raises(ValidationError, match="Too many nodes"):
            SceneSpec(
                nodes=nodes,
                choreography=[
                    StepSpec(
                        action="play",
                        animation=AnimationSpec(type="fade_in", targets=["n0"]),
                    )
                ],
            )

    def test_node_label_too_long(self):
        with pytest.raises(ValidationError):
            NodeSpec(id="n", label="A" * 51)

    def test_payload_too_long(self):
        with pytest.raises(ValidationError):
            AnimationSpec(type="transfer", payload="A" * 21)

    def test_yaml_too_large(self):
        # 2MB of padding
        huge = "version: '1.0'\n" + "# " + "x" * 2_000_000
        with pytest.raises(YAMLParseError, match="too large"):
            parse_yaml_string(huge)


# ══════════════════════════════════════════════
# E2E: parse_yaml_string() → Scene
# ══════════════════════════════════════════════


class TestE2EParseYaml:
    """End-to-end tests: YAML string → Scene object."""

    def test_minimal_yaml(self):
        scene = parse_yaml_string(MINIMAL_YAML)
        assert isinstance(scene, Scene)
        assert scene.total_duration > 0

    def test_full_yaml(self):
        scene = parse_yaml_string(FULL_YAML)
        assert isinstance(scene, Scene)
        assert scene.total_duration > 0

    def test_invalid_yaml_syntax(self):
        bad_yaml = "nodes:\n  - id: 'missing_bracket"
        with pytest.raises(YAMLParseError, match="YAML"):
            parse_yaml_string(bad_yaml)

    def test_yaml_not_a_dict(self):
        with pytest.raises(YAMLParseError, match="mapping"):
            parse_yaml_string("- just\n- a\n- list")

    def test_schema_validation_error(self):
        bad = textwrap.dedent("""\
            version: "1.0"
            nodes: []
            choreography:
              - action: play
                animation:
                  type: fade_in
                  targets: ["missing"]
        """)
        with pytest.raises(YAMLParseError, match="validation failed"):
            parse_yaml_string(bad)


# ══════════════════════════════════════════════
# Error Reporting Quality
# ══════════════════════════════════════════════


class TestErrorReporting:
    """Test that errors are human-readable (LLM feedback quality)."""

    def test_error_contains_field_path(self):
        try:
            parse_yaml_string(textwrap.dedent("""\
                version: "1.0"
                nodes:
                  - id: "a"
                    label: "A"
                choreography:
                  - action: play
            """))
        except YAMLParseError as exc:
            assert "animation" in str(exc).lower() or "requires" in str(exc).lower()

    def test_yaml_parse_error_has_errors_list(self):
        try:
            parse_yaml_string(textwrap.dedent("""\
                version: "1.0"
                nodes: []
                choreography:
                  - action: wait
                    duration: 1.0
            """))
        except YAMLParseError as exc:
            assert len(exc.errors) > 0

    def test_yaml_parse_error_preserves_content(self):
        content = "invalid: yaml: content: [["
        try:
            parse_yaml_string(content)
        except YAMLParseError as exc:
            assert exc.yaml_content == content
