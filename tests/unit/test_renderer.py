"""Unit tests for Phase 4a -- Renderer (Canvas, Painters, Frame).

Tests cover:
    - hex_to_color4f conversion (various formats)
    - rgba_to_color4f conversion
    - interpolate_path (polyline interpolation)
    - SkiaCanvas lifecycle (create, clear, snapshot, dispose)
    - render_frame smoke test (produces correct byte count)
    - Painter smoke tests (no crash on draw calls)
"""

from __future__ import annotations

import pytest

from archmotion._types import AnimatableProperty, PrimitiveType
from archmotion.layout.bbox import BoundingBox
from archmotion.renderer.canvas import SkiaCanvas, hex_to_color4f, rgba_to_color4f, make_font
from archmotion.renderer.painters import (
    interpolate_path,
    paint_connection,
    paint_database,
    paint_node,
    paint_packet,
)
from archmotion.renderer.frame import FrameSpec, render_frame
from archmotion.renderer.theme import ThemeConfig
from archmotion.timeline.actions import ScheduledAction


# ──────────────────────────────────────────────
# Color Conversion Tests
# ──────────────────────────────────────────────


class TestHexToColor4f:
    """Test CSS hex color to skia.Color4f conversion."""

    def test_6_digit_hex(self):
        c = hex_to_color4f("#ff0000")
        assert abs(c.fR - 1.0) < 0.01
        assert abs(c.fG - 0.0) < 0.01
        assert abs(c.fB - 0.0) < 0.01
        assert abs(c.fA - 1.0) < 0.01

    def test_8_digit_hex_with_alpha(self):
        c = hex_to_color4f("#00000066")
        assert abs(c.fR - 0.0) < 0.01
        assert abs(c.fA - 0.4) < 0.02  # 0x66/255 = ~0.4

    def test_3_digit_hex(self):
        c = hex_to_color4f("#fff")
        assert abs(c.fR - 1.0) < 0.01
        assert abs(c.fG - 1.0) < 0.01
        assert abs(c.fB - 1.0) < 0.01

    def test_opacity_multiplier(self):
        c = hex_to_color4f("#ffffff", opacity=0.5)
        assert abs(c.fA - 0.5) < 0.01

    def test_no_hash_prefix(self):
        c = hex_to_color4f("cdd6f4")
        assert c.fR > 0.0  # Should parse correctly

    def test_invalid_fallback_to_white(self):
        c = hex_to_color4f("#xyz")
        # Should not crash, falls back to white
        assert c is not None


class TestRgbaToColor4f:
    """Test RGBA tuple conversion."""

    def test_full_opacity(self):
        c = rgba_to_color4f((0.5, 0.5, 0.5, 1.0))
        assert abs(c.fR - 0.5) < 0.01
        assert abs(c.fA - 1.0) < 0.01

    def test_with_opacity_multiplier(self):
        c = rgba_to_color4f((1.0, 1.0, 1.0, 1.0), opacity=0.5)
        assert abs(c.fA - 0.5) < 0.01


# ──────────────────────────────────────────────
# Path Interpolation Tests
# ──────────────────────────────────────────────


class TestInterpolatePath:
    """Test polyline path interpolation for Transfer packets."""

    def test_start_of_path(self):
        route = [(0.0, 0.0), (100.0, 0.0)]
        pos = interpolate_path(route, 0.0)
        assert abs(pos[0] - 0.0) < 0.01
        assert abs(pos[1] - 0.0) < 0.01

    def test_end_of_path(self):
        route = [(0.0, 0.0), (100.0, 0.0)]
        pos = interpolate_path(route, 1.0)
        assert abs(pos[0] - 100.0) < 0.01

    def test_midpoint_of_straight_line(self):
        route = [(0.0, 0.0), (200.0, 0.0)]
        pos = interpolate_path(route, 0.5)
        assert abs(pos[0] - 100.0) < 0.01

    def test_l_shaped_path(self):
        route = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)]
        # Total length = 200, midpoint at 100 = end of first segment
        pos = interpolate_path(route, 0.5)
        assert abs(pos[0] - 100.0) < 0.01
        assert abs(pos[1] - 0.0) < 0.01

    def test_l_shaped_path_75_percent(self):
        route = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)]
        # 75% of 200 = 150 -> 50 into second segment
        pos = interpolate_path(route, 0.75)
        assert abs(pos[0] - 100.0) < 0.01
        assert abs(pos[1] - 50.0) < 0.01

    def test_empty_route_returns_origin(self):
        pos = interpolate_path([], 0.5)
        assert pos == (0.0, 0.0)

    def test_single_point_route(self):
        pos = interpolate_path([(50.0, 50.0)], 0.5)
        assert abs(pos[0] - 50.0) < 0.01

    def test_negative_progress_clamps(self):
        route = [(0.0, 0.0), (100.0, 0.0)]
        pos = interpolate_path(route, -0.5)
        assert abs(pos[0] - 0.0) < 0.01

    def test_over_1_progress_clamps(self):
        route = [(0.0, 0.0), (100.0, 0.0)]
        pos = interpolate_path(route, 1.5)
        assert abs(pos[0] - 100.0) < 0.01


# ──────────────────────────────────────────────
# SkiaCanvas Lifecycle Tests
# ──────────────────────────────────────────────


class TestSkiaCanvas:
    """Test SkiaCanvas create/clear/snapshot/dispose."""

    def test_create_canvas(self):
        canvas = SkiaCanvas(320, 240)
        assert canvas.width == 320
        assert canvas.height == 240
        canvas.dispose()

    def test_snapshot_returns_correct_bytes(self):
        canvas = SkiaCanvas(100, 100)
        canvas.clear(rgba_to_color4f((0.0, 0.0, 0.0, 1.0)))
        data = canvas.snapshot()
        assert len(data) == 100 * 100 * 4  # RGBA
        canvas.dispose()

    def test_dispose_is_safe_to_call_twice(self):
        canvas = SkiaCanvas(100, 100)
        canvas.dispose()
        canvas.dispose()  # Should not crash

    def test_native_canvas_exists(self):
        canvas = SkiaCanvas(100, 100)
        assert canvas.native is not None
        canvas.dispose()


class TestMakeFont:
    """Test font creation."""

    def test_make_font_returns_font(self):
        font = make_font("Arial", 14.0)
        assert font is not None
        # Can measure text
        width = font.measureText("Hello")
        assert width > 0

    def test_fallback_font(self):
        # Non-existent font should still return a valid font
        font = make_font("NonExistentFontFamily12345", 14.0)
        assert font is not None


# ──────────────────────────────────────────────
# Painter Smoke Tests
# ──────────────────────────────────────────────


class TestPainterSmoke:
    """Smoke tests: painters should not crash when drawing."""

    @pytest.fixture()
    def canvas(self):
        c = SkiaCanvas(400, 300)
        c.clear(rgba_to_color4f((0.0, 0.0, 0.0, 1.0)))
        yield c
        c.dispose()

    @pytest.fixture()
    def theme(self):
        return ThemeConfig()

    @pytest.fixture()
    def bbox(self):
        return BoundingBox(x=50.0, y=50.0, width=150.0, height=50.0)

    def test_paint_node_no_crash(self, canvas, bbox, theme):
        paint_node(canvas, bbox, "API Gateway", theme)

    def test_paint_node_with_opacity(self, canvas, bbox, theme):
        paint_node(canvas, bbox, "Server", theme, opacity=0.5)

    def test_paint_node_with_glow(self, canvas, bbox, theme):
        paint_node(canvas, bbox, "Auth", theme, glow_intensity=0.8)

    def test_paint_database_no_crash(self, canvas, bbox, theme):
        paint_database(canvas, bbox, "PostgreSQL", theme)

    def test_paint_connection_no_crash(self, canvas, theme):
        route = [(50.0, 75.0), (200.0, 75.0)]
        paint_connection(canvas, route, label="HTTP", theme=theme)

    def test_paint_connection_l_shape(self, canvas, theme):
        route = [(50.0, 50.0), (150.0, 50.0), (150.0, 150.0)]
        paint_connection(canvas, route, label=None, theme=theme)

    def test_paint_packet_no_crash(self, canvas, theme):
        paint_packet(canvas, (100.0, 100.0), "GET /api", theme)

    def test_paint_packet_custom_color(self, canvas, theme):
        paint_packet(canvas, (100.0, 100.0), "200 OK", theme, packet_color="#ff5733")


# ──────────────────────────────────────────────
# render_frame Smoke Test
# ──────────────────────────────────────────────


class TestRenderFrame:
    """Smoke test: render_frame should produce correct byte output."""

    def test_renders_correct_byte_count(self):
        """An empty frame should produce width * height * 4 bytes."""
        spec = FrameSpec(
            frame_index=0,
            width=320,
            height=240,
            fps=60,
            theme=ThemeConfig(),
            node_boxes={},
            node_labels={},
            node_types={},
            connection_routes={},
            connection_labels={},
            compiled_actions=(),
            transfer_metas=(),
        )
        result = render_frame(spec)
        assert len(result) == 320 * 240 * 4

    def test_renders_with_node(self):
        """Frame with a single node should not crash and produce bytes."""
        bbox = BoundingBox(x=100.0, y=100.0, width=150.0, height=50.0)
        spec = FrameSpec(
            frame_index=0,
            width=400,
            height=300,
            fps=60,
            theme=ThemeConfig(),
            node_boxes={"node1": bbox},
            node_labels={"node1": "Server"},
            node_types={"node1": PrimitiveType.NODE},
            connection_routes={},
            connection_labels={},
            compiled_actions=(),
            transfer_metas=(),
        )
        result = render_frame(spec)
        assert len(result) == 400 * 300 * 4

    def test_renders_with_animation(self):
        """Frame with FadeIn animation at midpoint."""
        bbox = BoundingBox(x=100.0, y=100.0, width=150.0, height=50.0)
        action = ScheduledAction(
            target_id="node1",
            prop=AnimatableProperty.OPACITY,
            start_time=0.0,
            end_time=1.0,
            start_value=0.0,
            end_value=1.0,
        )
        spec = FrameSpec(
            frame_index=30,  # t=0.5s (mid-fade)
            width=400,
            height=300,
            fps=60,
            theme=ThemeConfig(),
            node_boxes={"node1": bbox},
            node_labels={"node1": "Auth Service"},
            node_types={"node1": PrimitiveType.NODE},
            connection_routes={},
            connection_labels={},
            compiled_actions=(action,),
            transfer_metas=(),
        )
        result = render_frame(spec)
        assert len(result) == 400 * 300 * 4

    def test_renders_database_type(self):
        """Frame with a Database primitive type."""
        bbox = BoundingBox(x=100.0, y=100.0, width=150.0, height=60.0)
        spec = FrameSpec(
            frame_index=0,
            width=400,
            height=300,
            fps=60,
            theme=ThemeConfig(),
            node_boxes={"db1": bbox},
            node_labels={"db1": "PostgreSQL"},
            node_types={"db1": PrimitiveType.DATABASE},
            connection_routes={},
            connection_labels={},
            compiled_actions=(),
            transfer_metas=(),
        )
        result = render_frame(spec)
        assert len(result) == 400 * 300 * 4
