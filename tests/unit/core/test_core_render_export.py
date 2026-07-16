"""Tests for the skia-free renderer (resolve_effective) + v2 exporters."""

from __future__ import annotations

import json

import pytest

from archmotion.animation import FadeIn
from archmotion.core import Property, Scene, VMobject
from archmotion.exporter.lottie_v2 import build_lottie
from archmotion.exporter.svg_v2 import build_svg
from archmotion.render.path_render import resolve_effective


class Square(VMobject):
    def __init__(self, side: float = 100.0, **kwargs):
        self.side = side
        super().__init__(**kwargs)

    def generate_points(self) -> None:
        s = self.side
        self.start_new_path((0.0, 0.0))
        self.add_line_to((s, 0.0))
        self.add_line_to((s, s))
        self.add_line_to((0.0, s))
        self.close_path()


# ── resolve_effective ────────────────────────────────────────────


def test_resolve_effective_uses_morph_points():
    import numpy as np

    g = Square(100.0)
    morphed = np.zeros((13, 2))
    state = resolve_effective(g, {}, morphed, Scene(resolution=(320, 240)).camera)
    assert np.allclose(state.points, morphed)


def test_resolve_effective_opacity_default_and_override():
    g = Square(100.0)
    default = resolve_effective(g, None, None, Scene(resolution=(320, 240)).camera)
    assert default.opacity == 1.0
    override = resolve_effective(
        g, {Property.OPACITY: 0.25}, None, Scene(resolution=(320, 240)).camera
    )
    assert override.opacity == 0.25


def test_resolve_effective_create_progress_default_full():
    g = Square(100.0)
    state = resolve_effective(g, None, None, Scene(resolution=(320, 240)).camera)
    assert state.create_progress == 1.0


def test_resolve_effective_fill_color_from_rgb_scalars():
    g = Square(100.0)
    scalars = {Property.FILL_R: 1.0, Property.FILL_G: 0.0, Property.FILL_B: 0.0}
    state = resolve_effective(g, scalars, None, Scene(resolution=(320, 240)).camera)
    assert state.fill_color == "#ff0000"


# ── SVG export ───────────────────────────────────────────────────


def test_svg_contains_path_and_dimensions():
    sc = Scene(resolution=(640, 360))
    sc.add(Square(100.0).move_to(200.0, 180.0))
    sc.play(FadeIn(Square(100.0).move_to(400.0, 180.0)))
    svg = build_svg(sc)
    assert "<svg" in svg
    assert 'width="640"' in svg
    assert "<path" in svg
    assert svg.strip().endswith("</svg>")


def test_svg_has_opacity_keyframes_for_fadein():
    sc = Scene(resolution=(320, 240))
    a = Square(100.0)
    sc.add(a)
    sc.play(FadeIn(a, run_time=1.0))
    svg = build_svg(sc)
    assert "@keyframes" in svg


def test_svg_keeps_open_paths_open_and_escapes_title():
    from archmotion.domains.geometry import Line

    sc = Scene(resolution=(320, 240))
    line = Line((10.0, 10.0), (100.0, 100.0))
    sc.add(line)
    sc.play(FadeIn(line))
    svg = build_svg(sc, title="A < B & C")
    path_markup = next(part for part in svg.splitlines() if "<path" in part)
    assert " Z" not in path_markup
    assert "A &lt; B &amp; C" in svg


# ── Lottie export ────────────────────────────────────────────────


def test_lottie_is_valid_json_with_layers():
    sc = Scene(resolution=(640, 360))
    sc.add(Square(100.0).move_to(200.0, 180.0))
    sc.play(FadeIn(Square(100.0).move_to(400.0, 180.0)))
    lot = build_lottie(sc)
    assert isinstance(lot, dict)
    assert lot["w"] == 640
    assert lot["h"] == 360
    assert len(lot["layers"]) == 2
    # JSON-serializable.
    serialized = json.dumps(lot)
    assert '"layers"' in serialized


def test_lottie_opacity_keyframes_present():
    sc = Scene(resolution=(320, 240))
    a = Square(100.0)
    sc.add(a)
    sc.play(FadeIn(a, run_time=1.0))
    lot = build_lottie(sc)
    opacity_prop = lot["layers"][0]["ks"]["o"]
    assert opacity_prop["a"] == 1
    assert opacity_prop["k"][0]["s"] == [0.0]


def test_lottie_paths_use_bodymovin_vertex_schema():
    sc = Scene(resolution=(320, 240))
    square = Square(100.0)
    sc.add(square)
    sc.play(FadeIn(square))
    lot = build_lottie(sc)
    path = next(shape for shape in lot["layers"][0]["shapes"] if shape["ty"] == "sh")
    geometry = path["ks"]["k"]
    assert set(geometry) == {"i", "o", "v", "c"}
    assert all(len(vertex) == 2 for vertex in geometry["v"])
    assert len(geometry["i"]) == len(geometry["v"]) == len(geometry["o"])


def test_resolve_effective_matrix_is_3x3():
    g = Square(100.0)
    state = resolve_effective(g, None, None, Scene(resolution=(320, 240)).camera)
    matrix = state.matrix
    assert matrix.shape == (3, 3)


def test_scene_background_uses_shared_strict_color_contract():
    scene = Scene(background_color="red")
    assert scene.theme.background_rgba == (1.0, 0.0, 0.0, 1.0)
    with pytest.raises(ValueError, match="color must use"):
        Scene(background_color="not-a-color")
