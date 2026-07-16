"""Tests for core geometry: Transform, pathops, VMobject point building + morphing."""

from __future__ import annotations

import math

import numpy as np
import pytest

from archmotion.core import Style, Transform, VMobject


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


class Circle(VMobject):
    def __init__(self, radius: float = 60.0, **kwargs):
        self.radius = radius
        super().__init__(**kwargs)

    def generate_points(self) -> None:
        self.start_new_path((self.radius, 0.0))
        self.add_arc((0.0, 0.0), self.radius, 0.0, 360.0, n_segments=8)
        self.close_path()


# ── Transform ────────────────────────────────────────────────────


def test_translation_apply_to_point():
    t = Transform.translation(10.0, 20.0)
    assert t.apply_to_point((1.0, 2.0)) == (11.0, 22.0)


def test_scaling_uniform_and_nonuniform():
    assert Transform.scaling(2.0).apply_to_point((3.0, 4.0)) == (6.0, 8.0)
    assert Transform.scaling(2.0, 3.0).apply_to_point((1.0, 1.0)) == (2.0, 3.0)


def test_rotation_90_degrees():
    r = Transform.rotation(90.0)
    x, y = r.apply_to_point((1.0, 0.0))
    assert abs(x) < 1e-9
    assert abs(y - 1.0) < 1e-9


def test_compose_then_invert_roundtrip():
    t = Transform.translation(5.0, 5.0).compose(Transform.scaling(2.0))
    pts = np.array([[1.0, 1.0], [3.0, 3.0]])
    moved = t.apply_to_points(pts)
    back = t.invert().apply_to_points(moved)
    assert np.allclose(back, pts)


# ── VMobject point building ──────────────────────────────────────


def test_square_has_whole_triplet_count():
    sq = Square(100.0)
    # anchor + 4 line triplets = 1 + 12 = 13 points.
    assert sq.points.shape == (13, 2)
    assert sq.n_curves == 4


def test_square_bounding_box():
    sq = Square(100.0)
    bbox = sq.bounding_box()
    assert bbox.width == pytest.approx(100.0)
    assert bbox.height == pytest.approx(100.0)


def test_circle_bbox_matches_radius():
    c = Circle(60.0)
    bbox = c.bounding_box()
    assert bbox.width == pytest.approx(120.0, abs=1.0)
    assert bbox.height == pytest.approx(120.0, abs=1.0)


def test_start_new_path_required_before_curves():
    v = VMobject()
    with pytest.raises(RuntimeError):
        v.add_line_to((1.0, 1.0))


def test_close_path_returns_to_anchor():
    sq = Square(100.0)
    pts = sq.points
    anchor = pts[0]
    last = pts[-1]
    assert math.dist(anchor, last) < 1e-6


# ── morphing ─────────────────────────────────────────────────────


def test_align_with_pads_to_common_count():
    sq = Square(100.0)  # 13 pts
    c = Circle(60.0)  # 25 pts
    a, b = sq.align_with(c)
    assert a.shape[0] == b.shape[0]
    assert a.shape[0] >= 25


def test_interpolate_midpoint_shape():
    sq = Square(100.0)
    c = Circle(60.0)
    src, tgt = sq.align_with(c)
    sq.interpolate_points(src, tgt, 0.5)
    assert sq.points.shape == src.shape
    # Midpoint bbox sits between square and circle extents.
    assert sq.bounding_box().width < 120.0


def test_copy_is_independent():
    sq = Square(100.0)
    clone = sq.copy()
    assert clone.id != sq.id
    clone.shift(10.0, 0.0)
    assert sq.bounding_box().x == pytest.approx(0.0)


# ── Style ────────────────────────────────────────────────────────


def test_style_with_fill_and_stroke():
    s = Style().with_fill("#ff0000", 0.5).with_stroke("#00ff00", width=4.0)
    assert s.fill_color == "#ff0000"
    assert s.fill_opacity == 0.5
    assert s.stroke_color == "#00ff00"
    assert s.stroke_width == 4.0


def test_style_normalizes_named_colors_and_rejects_invalid_values():
    assert Style(fill_color="yellow").fill_color == "#ffff00"
    with pytest.raises(ValueError, match="color must use"):
        Style(fill_color="not-a-color")
    with pytest.raises(ValueError, match="fill_opacity"):
        Style(fill_opacity=1.5)


# ── pathops ──────────────────────────────────────────────────────


def test_arc_triplets_produce_segments():
    from archmotion.core.pathops import arc_triplets

    start, triplets = arc_triplets((0.0, 0.0), 50.0, 0.0, 360.0, n_segments=4)
    assert len(triplets) == 4
    # First triplet ends near the 90-degree point.
    end = triplets[0][2]
    assert abs(end[0] - 0.0) < 5.0
    assert abs(end[1] - 50.0) < 5.0


def test_resample_array_pads():
    from archmotion.core.pathops import resample_array

    a = np.ones((13, 2))
    out = resample_array(a, 25)
    assert out.shape == (25, 2)
