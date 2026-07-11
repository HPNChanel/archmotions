"""Unit tests for PLAN-017 — Public API Surface.

Tests cover:
    - Top-level imports (all public symbols)
    - Scene.export() format routing
    - Exporter package re-exports
    - __all__ completeness
"""

import json
import tempfile

import pytest

import archmotion
from archmotion import (
    Cache,
    Cloud,
    ColorShift,
    Connection,
    Database,
    FadeIn,
    FadeOut,
    Highlight,
    Node,
    Pulse,
    Queue,
    ScaleDown,
    ScaleUp,
    Scene,
    Transfer,
    User,
    load_yaml,
    parse_yaml_string,
)
from archmotion.exporter.html_v2 import build_html
from archmotion.exporter.lottie_v2 import build_lottie
from archmotion.exporter.svg_v2 import build_svg

# ──────────────────────────────────────────────
# Import Tests
# ──────────────────────────────────────────────


class TestTopLevelImports:
    def test_scene_importable(self):
        assert Scene is not None

    def test_all_primitives_importable(self):
        for cls in (Node, Database, Cloud, Queue, Cache, User):
            assert cls is not None

    def test_connection_importable(self):
        assert Connection is not None

    def test_all_animations_importable(self):
        for cls in (FadeIn, FadeOut, Transfer, Pulse, Highlight, ColorShift, ScaleUp, ScaleDown):
            assert cls is not None

    def test_yaml_functions_importable(self):
        assert callable(load_yaml)
        assert callable(parse_yaml_string)

    def test_version_exists(self):
        assert hasattr(archmotion, "__version__")
        assert isinstance(archmotion.__version__, str)


class TestExporterImports:
    def test_build_lottie_importable(self):
        assert callable(build_lottie)

    def test_build_svg_importable(self):
        assert callable(build_svg)

    def test_build_html_importable(self):
        assert callable(build_html)


# ──────────────────────────────────────────────
# __all__ Completeness
# ──────────────────────────────────────────────


class TestAllCompleteness:
    def test_top_level_all_has_core(self):
        for name in ("Scene", "Node", "Database", "Connection"):
            assert name in archmotion.__all__

    def test_top_level_all_has_animations(self):
        for name in ("FadeIn", "FadeOut", "Transfer", "Pulse"):
            assert name in archmotion.__all__

    def test_top_level_all_has_yaml(self):
        for name in ("load_yaml", "parse_yaml_string"):
            assert name in archmotion.__all__


# ──────────────────────────────────────────────
# Scene.export() Tests
# ──────────────────────────────────────────────


def _make_scene() -> Scene:
    """Create a minimal scene with one animation."""
    scene = Scene(resolution="720p", fps=30)
    a = Node("Server A")
    b = Node("Server B").right_of(a)
    scene.play(FadeIn(a, b))
    return scene


class TestSceneExport:
    def test_export_lottie(self):
        scene = _make_scene()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = scene.export(f"{tmpdir}/output.json")
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["v"] is not None

    def test_export_lottie_minified(self):
        scene = _make_scene()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = scene.export(f"{tmpdir}/output.json", minify=True)
            content = path.read_text()
            assert "\n  " not in content

    def test_export_svg(self):
        scene = _make_scene()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = scene.export(f"{tmpdir}/output.svg")
            assert path.exists()
            assert "<svg" in path.read_text()

    def test_export_html(self):
        scene = _make_scene()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = scene.export(f"{tmpdir}/output.html")
            assert path.exists()
            content = path.read_text()
            assert "lottie" in content

    def test_export_html_custom_title(self):
        scene = _make_scene()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = scene.export(
                f"{tmpdir}/output.html",
                title="My Test Title",
            )
            assert "My Test Title" in path.read_text()

    def test_export_unsupported_format_raises(self):
        scene = _make_scene()
        with pytest.raises(ValueError, match="Unsupported export format"):
            scene.export("output.avi")

    def test_export_empty_timeline_raises(self):
        scene = Scene()
        with pytest.raises(Exception):
            scene.export("output.json")
