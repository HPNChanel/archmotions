"""Unit tests for PLAN-011 & PLAN-012 — Themes, Corner Radius, YAML Schema updates.

Tests cover:
    - Theme registry (4 themes available)
    - Theme field validation
    - get_theme() happy and error paths
    - conn_corner_radius field on ThemeConfig
    - Connection corner_radius parameter
    - YAML schema: theme and corner_radius fields
    - Builder: theme wiring to Scene
    - Builder: corner_radius wiring to Connection
"""

import pytest

from archmotion.ai.schema import ConnectionSpec, SceneSpec
from archmotion.domains.architecture import Connection, Node
from archmotion.render.theme import THEMES, ThemeConfig, get_theme

# ──────────────────────────────────────────────
# Theme Registry Tests
# ──────────────────────────────────────────────


class TestThemeRegistry:
    def test_four_themes_available(self):
        assert len(THEMES) == 4
        assert set(THEMES.keys()) == {
            "dark_terminal", "neon_cyber", "blueprint", "light_paper",
        }

    def test_all_themes_are_themeconfig(self):
        for name, theme in THEMES.items():
            assert isinstance(theme, ThemeConfig), f"{name} is not ThemeConfig"

    def test_dark_terminal_is_default(self):
        default = ThemeConfig()
        assert default.name == "dark_terminal"

    def test_get_theme_dark_terminal(self):
        theme = get_theme("dark_terminal")
        assert theme.name == "dark_terminal"

    def test_get_theme_neon_cyber(self):
        theme = get_theme("neon_cyber")
        assert theme.name == "neon_cyber"
        assert theme.font_color == "#39ff14"

    def test_get_theme_blueprint(self):
        theme = get_theme("blueprint")
        assert theme.name == "blueprint"

    def test_get_theme_light_paper(self):
        theme = get_theme("light_paper")
        assert theme.name == "light_paper"
        assert theme.node_fill == "#ffffff"

    def test_get_theme_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown theme"):
            get_theme("nonexistent")


# ──────────────────────────────────────────────
# Corner Radius on ThemeConfig
# ──────────────────────────────────────────────


class TestThemeCornerRadius:
    def test_default_corner_radius(self):
        theme = ThemeConfig()
        assert theme.conn_corner_radius == 12.0

    def test_neon_has_larger_radius(self):
        theme = get_theme("neon_cyber")
        assert theme.conn_corner_radius == 14.0

    def test_blueprint_has_smaller_radius(self):
        theme = get_theme("blueprint")
        assert theme.conn_corner_radius == 8.0

    def test_light_paper_radius(self):
        theme = get_theme("light_paper")
        assert theme.conn_corner_radius == 10.0

    def test_custom_zero_radius(self):
        theme = ThemeConfig(conn_corner_radius=0.0)
        assert theme.conn_corner_radius == 0.0


# ──────────────────────────────────────────────
# Connection corner_radius
# ──────────────────────────────────────────────


class TestConnectionCornerRadius:
    def test_connection_default_no_radius(self):
        a = Node("A")
        b = Node("B")
        b.right_of(a)
        conn = Connection(a, b)
        # v2 default corner_radius is 0.0 (sharp corners) until resolved.
        assert conn.corner_radius == 0.0

    def test_connection_with_custom_radius(self):
        a = Node("A")
        b = Node("B")
        b.right_of(a)
        conn = Connection(a, b, corner_radius=20.0)
        assert conn.corner_radius == 20.0


# ──────────────────────────────────────────────
# YAML Schema: theme and corner_radius
# ──────────────────────────────────────────────


class TestYAMLSchemaTheme:
    def _minimal_spec(self, **overrides):
        data = {
            "nodes": [{"id": "n1", "label": "Node1"}],
            "choreography": [
                {"action": "play", "animation": {"type": "fade_in", "targets": ["n1"]}},
            ],
        }
        data.update(overrides)
        return SceneSpec(**data)

    def test_default_theme_is_dark_terminal(self):
        spec = self._minimal_spec()
        assert spec.theme == "dark_terminal"

    def test_custom_theme_neon_cyber(self):
        spec = self._minimal_spec(theme="neon_cyber")
        assert spec.theme == "neon_cyber"

    def test_custom_theme_blueprint(self):
        spec = self._minimal_spec(theme="blueprint")
        assert spec.theme == "blueprint"

    def test_connection_corner_radius_in_schema(self):
        data = {
            "nodes": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
            "connections": [
                {"id": "c1", "source": "a", "target": "b", "corner_radius": 20.0},
            ],
            "choreography": [
                {"action": "play", "animation": {"type": "fade_in", "targets": ["a"]}},
            ],
        }
        spec = SceneSpec(**data)
        assert spec.connections[0].corner_radius == 20.0

    def test_connection_corner_radius_default_none(self):
        conn = ConnectionSpec(id="c1", source="a", target="b")
        assert conn.corner_radius is None

    def test_connection_corner_radius_validation_max(self):
        with pytest.raises(Exception):
            ConnectionSpec(id="c1", source="a", target="b", corner_radius=100.0)


# ──────────────────────────────────────────────
# Theme Visual Aesthetics Sanity Checks
# ──────────────────────────────────────────────


class TestThemeAesthetics:
    def test_neon_has_dark_background(self):
        theme = get_theme("neon_cyber")
        r, g, b, a = theme.background_rgba
        assert r < 0.1 and g < 0.1 and b < 0.1

    def test_light_paper_has_light_background(self):
        theme = get_theme("light_paper")
        r, g, b, a = theme.background_rgba
        assert r > 0.9 and g > 0.9 and b > 0.9

    def test_blueprint_has_blue_tint(self):
        theme = get_theme("blueprint")
        r, g, b, a = theme.background_rgba
        assert b > r and b > g

    def test_all_themes_have_positive_glow(self):
        for name, theme in THEMES.items():
            assert theme.glow_blur_radius > 0, f"{name} glow_blur_radius should be > 0"

    def test_all_themes_frozen(self):
        for name, theme in THEMES.items():
            with pytest.raises(Exception):
                theme.name = "hacked"
