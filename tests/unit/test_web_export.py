"""Unit tests for PLAN-015 — Lottie / SVG / HTML Player Export.

Tests cover:
    - Lottie JSON structure: version, dimensions, layers, keyframes
    - Easing mapping: all EasingType → Lottie bezier curves
    - Color conversion: hex/rgba → Lottie arrays
    - Shape builders: rect, path, connection
    - Keyframe builder: opacity, scale animations
    - HTML player: template rendering, embedded Lottie
    - SVG exporter: valid SVG structure, CSS animations
    - File export: Lottie JSON, HTML, SVG file creation
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from archmotion._types import AnimatableProperty, EasingType, PrimitiveType
from archmotion.exporter.lottie import (
    _LOTTIE_VERSION,
    _build_connection_path,
    _build_keyframes,
    _build_rect_shape,
    _easing_to_lottie,
    _hex_to_lottie_color,
    _rgba_to_lottie,
    build_lottie_json,
    export_lottie,
)
from archmotion.exporter.html_player import (
    build_animated_svg,
    export_html_player,
    export_svg,
)
from archmotion.layout.bbox import BoundingBox
from archmotion.layout.resolver import ResolvedLayout
from archmotion.renderer.theme import ThemeConfig, get_theme
from archmotion.timeline.actions import ScheduledAction
from archmotion.timeline.compiler import CompiledTimeline


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


def _make_layout() -> ResolvedLayout:
    """Create a minimal resolved layout for testing."""
    return ResolvedLayout(
        node_boxes={
            "A": BoundingBox(x=100, y=200, width=120, height=50),
            "B": BoundingBox(x=400, y=200, width=120, height=50),
        },
        connection_routes={
            "conn_1": [(220.0, 225.0), (400.0, 225.0)],
        },
        canvas_width=1920,
        canvas_height=1080,
    )


def _make_timeline(fps: int = 60) -> CompiledTimeline:
    """Create a minimal compiled timeline for testing."""
    actions = [
        ScheduledAction(
            target_id="A",
            prop=AnimatableProperty.OPACITY,
            start_time=0.0,
            end_time=0.5,
            start_value=0.0,
            end_value=1.0,
            easing=EasingType.EASE_IN_OUT,
        ),
        ScheduledAction(
            target_id="B",
            prop=AnimatableProperty.OPACITY,
            start_time=0.5,
            end_time=1.0,
            start_value=0.0,
            end_value=1.0,
            easing=EasingType.EASE_OUT,
        ),
        ScheduledAction(
            target_id="A",
            prop=AnimatableProperty.SCALE,
            start_time=1.0,
            end_time=1.5,
            start_value=1.0,
            end_value=1.2,
            easing=EasingType.EASE_IN_OUT,
        ),
    ]
    return CompiledTimeline(
        actions=actions,
        total_duration=2.0,
        total_frames=120,
        fps=fps,
        transfer_metas=[],
    )


def _make_theme() -> ThemeConfig:
    """Get the default dark_terminal theme."""
    return get_theme("dark_terminal")


# ──────────────────────────────────────────────
# Easing Mapping
# ──────────────────────────────────────────────


class TestEasingMapping:
    def test_all_easing_types_have_mapping(self):
        """Every EasingType should produce valid Lottie bezier data."""
        for easing in EasingType:
            result = _easing_to_lottie(easing)
            assert "i" in result
            assert "o" in result
            assert "x" in result["i"]
            assert "y" in result["i"]

    def test_linear_easing(self):
        result = _easing_to_lottie(EasingType.LINEAR)
        # Linear: out handle at (0,0), in handle at (1,1)
        assert result["o"]["x"] == [0.0]
        assert result["o"]["y"] == [0.0]


# ──────────────────────────────────────────────
# Color Conversion
# ──────────────────────────────────────────────


class TestColorConversion:
    def test_rgba_to_lottie(self):
        result = _rgba_to_lottie((0.5, 0.3, 0.8, 1.0))
        assert len(result) == 4
        assert result[0] == pytest.approx(0.5)
        assert result[3] == pytest.approx(1.0)

    def test_hex_to_lottie_valid(self):
        result = _hex_to_lottie_color("#ff0000")
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(0.0)
        assert result[2] == pytest.approx(0.0)

    def test_hex_to_lottie_invalid_fallback(self):
        result = _hex_to_lottie_color("invalid")
        assert result == [1.0, 1.0, 1.0, 1.0]  # White fallback


# ──────────────────────────────────────────────
# Shape Builders
# ──────────────────────────────────────────────


class TestShapeBuilders:
    def test_rect_shape_structure(self):
        bbox = BoundingBox(x=100, y=200, width=120, height=50)
        shapes = _build_rect_shape(bbox, [0.1, 0.1, 0.1, 1.0], [0.5, 0.5, 0.5, 1.0])
        assert len(shapes) == 3  # rect + fill + stroke
        assert shapes[0]["ty"] == "rc"
        assert shapes[1]["ty"] == "fl"
        assert shapes[2]["ty"] == "st"

    def test_connection_path_structure(self):
        points = [(100.0, 200.0), (300.0, 200.0), (300.0, 400.0)]
        shapes = _build_connection_path(points, [0.5, 0.5, 0.5, 1.0])
        assert len(shapes) == 2  # path + stroke
        assert shapes[0]["ty"] == "sh"
        assert shapes[1]["ty"] == "st"
        # Verify vertices
        verts = shapes[0]["ks"]["k"]["v"]
        assert len(verts) == 3

    def test_connection_path_empty(self):
        shapes = _build_connection_path([(0, 0)], [1, 1, 1, 1])
        assert shapes == []


# ──────────────────────────────────────────────
# Keyframe Builder
# ──────────────────────────────────────────────


class TestKeyframeBuilder:
    def test_opacity_keyframes(self):
        actions = [
            ScheduledAction(
                target_id="A", prop=AnimatableProperty.OPACITY,
                start_time=0.0, end_time=0.5,
                start_value=0.0, end_value=1.0,
            ),
        ]
        kf = _build_keyframes(actions, fps=60, prop_filter=AnimatableProperty.OPACITY)
        assert len(kf) == 2  # start + end
        assert kf[0]["t"] == 0   # Frame 0
        assert kf[0]["s"] == [0.0]
        assert kf[0]["e"] == [100.0]
        assert kf[1]["t"] == 30  # Frame 30 (0.5s × 60fps)

    def test_no_matching_actions(self):
        actions = [
            ScheduledAction(
                target_id="A", prop=AnimatableProperty.SCALE,
                start_time=0.0, end_time=1.0,
                start_value=1.0, end_value=1.5,
            ),
        ]
        kf = _build_keyframes(actions, fps=60, prop_filter=AnimatableProperty.OPACITY)
        assert kf == []


# ──────────────────────────────────────────────
# Lottie JSON Structure
# ──────────────────────────────────────────────


class TestBuildLottieJson:
    def test_root_structure(self):
        layout = _make_layout()
        timeline = _make_timeline()
        theme = _make_theme()

        lottie = build_lottie_json(
            timeline=timeline, layout=layout, theme=theme,
            node_labels={"A": "Server", "B": "Client"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
            connection_labels={"conn_1": "Request"},
        )

        assert lottie["v"] == _LOTTIE_VERSION
        assert lottie["fr"] == 60
        assert lottie["w"] == 1920
        assert lottie["h"] == 1080
        assert lottie["ip"] == 0
        assert lottie["op"] == 120

    def test_has_layers(self):
        layout = _make_layout()
        timeline = _make_timeline()
        theme = _make_theme()

        lottie = build_lottie_json(
            timeline=timeline, layout=layout, theme=theme,
            node_labels={"A": "Server", "B": "Client"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
            connection_labels={"conn_1": "Request"},
        )

        layers = lottie["layers"]
        # 1 connection + 2 nodes = 3 layers
        assert len(layers) == 3

    def test_node_layer_has_shapes(self):
        layout = _make_layout()
        timeline = _make_timeline()
        theme = _make_theme()

        lottie = build_lottie_json(
            timeline=timeline, layout=layout, theme=theme,
            node_labels={"A": "Server", "B": "Client"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
            connection_labels={"conn_1": None},
        )

        # Find a node layer
        node_layers = [l for l in lottie["layers"] if "Server" in l["nm"]]
        assert len(node_layers) == 1
        assert len(node_layers[0]["shapes"]) >= 1

    def test_keyframes_present_for_animated_nodes(self):
        layout = _make_layout()
        timeline = _make_timeline()
        theme = _make_theme()

        lottie = build_lottie_json(
            timeline=timeline, layout=layout, theme=theme,
            node_labels={"A": "Server", "B": "Client"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
            connection_labels={"conn_1": None},
        )

        # Node A has opacity + scale actions
        server_layer = next(l for l in lottie["layers"] if "Server" in l["nm"])
        transform = server_layer["ks"]
        # Opacity should be animated (a=1)
        assert transform["o"]["a"] == 1

    def test_json_serializable(self):
        layout = _make_layout()
        timeline = _make_timeline()
        theme = _make_theme()

        lottie = build_lottie_json(
            timeline=timeline, layout=layout, theme=theme,
            node_labels={"A": "A", "B": "B"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.DATABASE},
            connection_labels={"conn_1": None},
        )

        # Must be JSON-serializable without errors
        json_str = json.dumps(lottie)
        assert len(json_str) > 100

    def test_different_primitive_types(self):
        layout = _make_layout()
        timeline = _make_timeline()
        theme = _make_theme()

        lottie = build_lottie_json(
            timeline=timeline, layout=layout, theme=theme,
            node_labels={"A": "Cloud", "B": "DB"},
            node_types={"A": PrimitiveType.CLOUD, "B": PrimitiveType.DATABASE},
            connection_labels={"conn_1": None},
        )

        assert len(lottie["layers"]) == 3


# ──────────────────────────────────────────────
# SVG Builder
# ──────────────────────────────────────────────


class TestBuildAnimatedSvg:
    def test_svg_root_element(self):
        svg = build_animated_svg(
            timeline=_make_timeline(), layout=_make_layout(),
            theme=_make_theme(),
            node_labels={"A": "Server", "B": "Client"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
            connection_labels={"conn_1": None},
        )
        assert svg.startswith("<svg")
        assert 'viewBox="0 0 1920 1080"' in svg
        assert "</svg>" in svg

    def test_svg_contains_nodes(self):
        svg = build_animated_svg(
            timeline=_make_timeline(), layout=_make_layout(),
            theme=_make_theme(),
            node_labels={"A": "Server", "B": "Client"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
            connection_labels={"conn_1": None},
        )
        assert "Server" in svg
        assert "Client" in svg

    def test_svg_contains_connections(self):
        svg = build_animated_svg(
            timeline=_make_timeline(), layout=_make_layout(),
            theme=_make_theme(),
            node_labels={"A": "A", "B": "B"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
            connection_labels={"conn_1": None},
        )
        assert "<polyline" in svg

    def test_svg_has_css_animations(self):
        svg = build_animated_svg(
            timeline=_make_timeline(), layout=_make_layout(),
            theme=_make_theme(),
            node_labels={"A": "A", "B": "B"},
            node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
            connection_labels={"conn_1": None},
        )
        assert "@keyframes" in svg


# ──────────────────────────────────────────────
# File Export
# ──────────────────────────────────────────────


class TestFileExport:
    def test_export_lottie_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            result = export_lottie(
                timeline=_make_timeline(), layout=_make_layout(),
                theme=_make_theme(),
                node_labels={"A": "A", "B": "B"},
                node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
                connection_labels={"conn_1": None},
                output_path=path,
            )
            assert result.exists()
            data = json.loads(result.read_text())
            assert data["v"] == _LOTTIE_VERSION

    def test_export_lottie_minified(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.min.json"
            result = export_lottie(
                timeline=_make_timeline(), layout=_make_layout(),
                theme=_make_theme(),
                node_labels={"A": "A", "B": "B"},
                node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
                connection_labels={"conn_1": None},
                output_path=path,
                minify=True,
            )
            content = result.read_text()
            # Minified should have no indentation
            assert "\n  " not in content

    def test_export_html_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "player.html"
            result = export_html_player(
                timeline=_make_timeline(), layout=_make_layout(),
                theme=_make_theme(),
                node_labels={"A": "A", "B": "B"},
                node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
                connection_labels={"conn_1": None},
                output_path=path,
            )
            assert result.exists()
            content = result.read_text()
            assert "<!DOCTYPE html>" in content
            assert "lottie" in content
            assert "ArchMotion" in content

    def test_export_svg_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "animation.svg"
            result = export_svg(
                timeline=_make_timeline(), layout=_make_layout(),
                theme=_make_theme(),
                node_labels={"A": "A", "B": "B"},
                node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
                connection_labels={"conn_1": None},
                output_path=path,
            )
            assert result.exists()
            content = result.read_text()
            assert "<svg" in content

    def test_html_player_custom_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "custom.html"
            export_html_player(
                timeline=_make_timeline(), layout=_make_layout(),
                theme=_make_theme(),
                node_labels={"A": "A", "B": "B"},
                node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
                connection_labels={"conn_1": None},
                output_path=path,
                title="My Custom Title",
            )
            content = path.read_text()
            assert "My Custom Title" in content

    def test_html_player_theme_colors(self):
        """HTML player should use theme colors for UI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "themed.html"
            theme = get_theme("neon_cyber")
            export_html_player(
                timeline=_make_timeline(), layout=_make_layout(),
                theme=theme,
                node_labels={"A": "A", "B": "B"},
                node_types={"A": PrimitiveType.NODE, "B": PrimitiveType.NODE},
                connection_labels={"conn_1": None},
                output_path=path,
            )
            content = path.read_text()
            # Should contain neon_cyber's accent color
            assert theme.node_border in content
