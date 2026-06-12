"""Unit tests for PLAN-008 -- Enhanced Animations (Highlight, ColorShift, Scale).

Tests cover:
    - Animation class construction + validation
    - Timeline compiler decomposition
    - Renderer integration (scale & color rendering)
    - Backward compatibility (existing animations unaffected)
"""

from __future__ import annotations

import math

import pytest

from archmotion._types import AnimatableProperty, EasingType, PrimitiveType
from archmotion.api.primitives import Node
from archmotion.layout.bbox import BoundingBox
from archmotion.motions._animations import (
    ColorShift,
    FadeIn,
    Highlight,
    Pulse,
    ScaleDown,
    ScaleUp,
    _parse_hex_color,
)
from archmotion.renderer.frame import (
    FrameSpec,
    _apply_color_shift,
    _apply_scale,
    render_frame,
)
from archmotion.renderer.theme import ThemeConfig
from archmotion.timeline.compiler import compile_timeline


# ──────────────────────────────────────────────
# Highlight Construction
# ──────────────────────────────────────────────


class TestHighlightConstruction:
    """Test Highlight animation class."""

    def test_default_construction(self):
        node = Node("Server")
        h = Highlight(node)
        assert h.target is node
        assert h.color == "yellow"
        assert h.duration == 1.0
        assert h.intensity == 0.8

    def test_custom_params(self):
        node = Node("Server")
        h = Highlight(node, color="red", duration=2.0, intensity=0.5)
        assert h.color == "red"
        assert h.duration == 2.0
        assert h.intensity == 0.5

    def test_non_node_raises(self):
        with pytest.raises(TypeError, match="Highlight target must be a Node"):
            Highlight("not_a_node")

    def test_invalid_intensity(self):
        node = Node("Server")
        with pytest.raises(ValueError, match="intensity"):
            Highlight(node, intensity=1.5)

    def test_frozen_immutable(self):
        h = Highlight(Node("Server"))
        with pytest.raises(AttributeError):
            h.color = "blue"


# ──────────────────────────────────────────────
# ColorShift Construction
# ──────────────────────────────────────────────


class TestColorShiftConstruction:
    """Test ColorShift animation class."""

    def test_default_construction(self):
        node = Node("Server")
        cs = ColorShift(node)
        assert cs.from_color == "#4caf50"
        assert cs.to_color == "#f44336"

    def test_custom_colors(self):
        node = Node("Server")
        cs = ColorShift(node, from_color="#00ff00", to_color="#ff0000")
        assert cs.from_color == "#00ff00"
        assert cs.to_color == "#ff0000"

    def test_non_node_raises(self):
        with pytest.raises(TypeError, match="ColorShift target must be a Node"):
            ColorShift("not_a_node")

    def test_invalid_from_color(self):
        node = Node("Server")
        with pytest.raises(ValueError, match="hex"):
            ColorShift(node, from_color="not_hex")

    def test_invalid_to_color(self):
        node = Node("Server")
        with pytest.raises(ValueError, match="hex"):
            ColorShift(node, to_color="xyz")


# ──────────────────────────────────────────────
# ScaleUp / ScaleDown Construction
# ──────────────────────────────────────────────


class TestScaleConstruction:
    """Test ScaleUp/ScaleDown animation classes."""

    def test_scale_up_default(self):
        node = Node("Server")
        su = ScaleUp(node)
        assert su.factor == 1.3  # DEFAULT_SCALE_FACTOR
        assert su.easing == EasingType.EASE_OUT

    def test_scale_down_default(self):
        node = Node("Server")
        sd = ScaleDown(node)
        assert sd.factor == 0.7

    def test_scale_up_factor_must_exceed_1(self):
        node = Node("Server")
        with pytest.raises(ValueError, match="ScaleUp factor"):
            ScaleUp(node, factor=0.5)

    def test_scale_down_factor_must_be_below_1(self):
        node = Node("Server")
        with pytest.raises(ValueError, match="ScaleDown factor"):
            ScaleDown(node, factor=1.5)

    def test_scale_up_non_node_raises(self):
        with pytest.raises(TypeError, match="ScaleUp target must be a Node"):
            ScaleUp("not_a_node")

    def test_scale_down_non_node_raises(self):
        with pytest.raises(TypeError, match="ScaleDown target must be a Node"):
            ScaleDown("not_a_node")


# ──────────────────────────────────────────────
# _parse_hex_color Helper
# ──────────────────────────────────────────────


class TestParseHexColor:
    """Test hex color parsing utility."""

    def test_standard_hex(self):
        r, g, b = _parse_hex_color("#ff0000")
        assert abs(r - 1.0) < 0.01
        assert abs(g - 0.0) < 0.01
        assert abs(b - 0.0) < 0.01

    def test_no_hash_prefix(self):
        r, g, b = _parse_hex_color("00ff00")
        assert abs(g - 1.0) < 0.01

    def test_mixed_case(self):
        r, g, b = _parse_hex_color("#FF5733")
        assert r > 0.9

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="6-digit"):
            _parse_hex_color("#fff")

    def test_invalid_chars_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            _parse_hex_color("#gggggg")


# ──────────────────────────────────────────────
# Timeline Compiler Decomposition
# ──────────────────────────────────────────────


class TestHighlightDecomposition:
    """Test Highlight decomposition into ScheduledActions."""

    def test_creates_two_actions(self):
        node = Node("Server")
        play_calls = [{
            "animation": Highlight(node, duration=1.0, intensity=0.8),
            "start_time": 0.0,
            "duration": 1.0,
        }]
        result = compile_timeline(play_calls, total_duration=2.0, fps=30)
        # Should create 2 actions: ramp_up + hold
        target_actions = [a for a in result.actions if a.target_id == node.id]
        assert len(target_actions) == 2

    def test_ramp_up_then_hold(self):
        node = Node("Server")
        play_calls = [{
            "animation": Highlight(node, duration=2.0, intensity=0.6),
            "start_time": 0.0,
            "duration": 2.0,
        }]
        result = compile_timeline(play_calls, total_duration=2.0, fps=30)
        target_actions = [a for a in result.actions if a.target_id == node.id]
        ramp = target_actions[0]
        hold = target_actions[1]

        # Ramp up: 0 -> 0.6
        assert ramp.start_value == 0.0
        assert ramp.end_value == 0.6
        assert ramp.prop == AnimatableProperty.GLOW_INTENSITY

        # Hold: 0.6 -> 0.6
        assert hold.start_value == 0.6
        assert hold.end_value == 0.6


class TestColorShiftDecomposition:
    """Test ColorShift decomposition into R/G/B ScheduledActions."""

    def test_creates_three_actions(self):
        node = Node("Server")
        play_calls = [{
            "animation": ColorShift(node, from_color="#ff0000", to_color="#00ff00"),
            "start_time": 0.0,
            "duration": 1.0,
        }]
        result = compile_timeline(play_calls, total_duration=2.0, fps=30)
        target_actions = [a for a in result.actions if a.target_id == node.id]
        assert len(target_actions) == 3

    def test_rgb_channels(self):
        node = Node("Server")
        play_calls = [{
            "animation": ColorShift(node, from_color="#ff0000", to_color="#0000ff"),
            "start_time": 0.0,
            "duration": 1.0,
        }]
        result = compile_timeline(play_calls, total_duration=2.0, fps=30)
        target_actions = {a.prop: a for a in result.actions if a.target_id == node.id}

        r_action = target_actions[AnimatableProperty.COLOR_R]
        assert abs(r_action.start_value - 1.0) < 0.01  # FF -> 1.0
        assert abs(r_action.end_value - 0.0) < 0.01    # 00 -> 0.0

        b_action = target_actions[AnimatableProperty.COLOR_B]
        assert abs(b_action.start_value - 0.0) < 0.01  # 00 -> 0.0
        assert abs(b_action.end_value - 1.0) < 0.01    # FF -> 1.0


class TestScaleDecomposition:
    """Test ScaleUp/ScaleDown decomposition."""

    def test_scale_up_creates_action(self):
        node = Node("Server")
        play_calls = [{
            "animation": ScaleUp(node, factor=1.5),
            "start_time": 0.0,
            "duration": 0.5,
        }]
        result = compile_timeline(play_calls, total_duration=2.0, fps=30)
        target_actions = [a for a in result.actions if a.target_id == node.id]
        assert len(target_actions) == 1
        assert target_actions[0].prop == AnimatableProperty.SCALE
        assert target_actions[0].start_value == 1.0
        assert target_actions[0].end_value == 1.5

    def test_scale_down_creates_action(self):
        node = Node("Server")
        play_calls = [{
            "animation": ScaleDown(node, factor=0.5),
            "start_time": 0.0,
            "duration": 0.5,
        }]
        result = compile_timeline(play_calls, total_duration=2.0, fps=30)
        target_actions = [a for a in result.actions if a.target_id == node.id]
        assert len(target_actions) == 1
        assert target_actions[0].end_value == 0.5


# ──────────────────────────────────────────────
# Renderer Integration (Scale + Color)
# ──────────────────────────────────────────────


class TestApplyScale:
    """Test _apply_scale helper in frame renderer."""

    def test_no_scale_returns_original(self):
        bbox = BoundingBox(10, 20, 100, 50)
        state: dict = {}
        result = _apply_scale(state, "node1", bbox)
        assert result is bbox  # same object

    def test_scale_up_expands_bbox(self):
        bbox = BoundingBox(10, 20, 100, 50)
        state = {"node1": {AnimatableProperty.SCALE: 2.0}}
        result = _apply_scale(state, "node1", bbox)
        assert result.width == 200.0
        assert result.height == 100.0
        # Center should remain the same
        assert abs(result.center[0] - bbox.center[0]) < 0.01
        assert abs(result.center[1] - bbox.center[1]) < 0.01

    def test_scale_down_shrinks_bbox(self):
        bbox = BoundingBox(10, 20, 100, 50)
        state = {"node1": {AnimatableProperty.SCALE: 0.5}}
        result = _apply_scale(state, "node1", bbox)
        assert result.width == 50.0
        assert result.height == 25.0


class TestApplyColorShift:
    """Test _apply_color_shift helper in frame renderer."""

    def test_no_color_returns_original(self):
        theme = ThemeConfig()
        state: dict = {}
        result = _apply_color_shift(state, "node1", theme)
        assert result is theme

    def test_color_override_changes_fill(self):
        theme = ThemeConfig()
        state = {
            "node1": {
                AnimatableProperty.COLOR_R: 1.0,
                AnimatableProperty.COLOR_G: 0.0,
                AnimatableProperty.COLOR_B: 0.0,
            }
        }
        result = _apply_color_shift(state, "node1", theme)
        assert result.node_fill == "#ff0000"
        # Original theme unchanged
        assert theme.node_fill == "#1e1e2e"


class TestRenderWithNewAnimations:
    """Integration: render_frame handles Scale and ColorShift."""

    def _make_spec(
        self,
        animated_actions: tuple = (),
    ) -> FrameSpec:
        return FrameSpec(
            frame_index=0,
            width=100,
            height=100,
            fps=30,
            theme=ThemeConfig(),
            node_boxes={"n1": BoundingBox(10, 10, 80, 40)},
            node_labels={"n1": "Server"},
            node_types={"n1": PrimitiveType.NODE},
            connection_routes={},
            connection_labels={},
            compiled_actions=animated_actions,
            transfer_metas=(),
        )

    def test_render_with_no_animations(self):
        result = render_frame(self._make_spec())
        assert len(result) == 100 * 100 * 4

    def test_render_with_scale_action(self):
        from archmotion.timeline.actions import ScheduledAction

        action = ScheduledAction(
            target_id="n1",
            prop=AnimatableProperty.SCALE,
            start_time=0.0,
            end_time=1.0,
            start_value=1.0,
            end_value=1.5,
            easing=EasingType.LINEAR,
        )
        result = render_frame(self._make_spec(animated_actions=(action,)))
        assert len(result) == 100 * 100 * 4

    def test_render_with_color_actions(self):
        from archmotion.timeline.actions import ScheduledAction

        actions = tuple(
            ScheduledAction(
                target_id="n1",
                prop=prop,
                start_time=0.0,
                end_time=1.0,
                start_value=0.0,
                end_value=1.0,
                easing=EasingType.LINEAR,
            )
            for prop in (
                AnimatableProperty.COLOR_R,
                AnimatableProperty.COLOR_G,
                AnimatableProperty.COLOR_B,
            )
        )
        result = render_frame(self._make_spec(animated_actions=actions))
        assert len(result) == 100 * 100 * 4


# ──────────────────────────────────────────────
# Backward Compatibility
# ──────────────────────────────────────────────


class TestBackwardCompatibility:
    """Verify existing animations still work after adding new ones."""

    def test_fadein_unchanged(self):
        node = Node("Test")
        fi = FadeIn(node)
        assert fi.duration == 0.5

    def test_pulse_unchanged(self):
        node = Node("Test")
        p = Pulse(node, color="yellow")
        assert p.intensity == 0.8

    def test_compile_mixed_animations(self):
        node = Node("Server")
        play_calls = [
            {"animation": FadeIn(node), "start_time": 0.0, "duration": 0.5},
            {"animation": Highlight(node, duration=1.0), "start_time": 0.5, "duration": 1.0},
            {"animation": ScaleUp(node, factor=1.5), "start_time": 1.5, "duration": 0.5},
        ]
        result = compile_timeline(play_calls, total_duration=2.0, fps=30)
        # FadeIn: 1 action, Highlight: 2 actions, ScaleUp: 1 action = 4 total
        assert len(result.actions) == 4
