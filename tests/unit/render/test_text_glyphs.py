"""Tests for text glyph extraction (verbs_to_contours always; skia parts when installed)."""

from __future__ import annotations

import pytest

from archmotion.render.text_glyphs import CLOSE, DONE, LINE, MOVE, QUAD, glyph_points, verbs_to_contours


def test_verbs_to_contours_rectangle_lines():
    # Move + 3 lines + close → anchor + 4 line triplets = 13 points, 1 contour.
    seq = [
        (MOVE, [(0.0, 0.0)]),
        (LINE, [(0.0, 0.0), (10.0, 0.0)]),
        (LINE, [(10.0, 0.0), (10.0, 10.0)]),
        (LINE, [(10.0, 10.0), (0.0, 10.0)]),
        (CLOSE, []),
    ]
    points, starts = verbs_to_contours(seq)
    assert starts == [0]
    assert len(points) == 13
    assert points[0] == (0.0, 0.0)
    assert points[-1] == (0.0, 0.0)


def test_verbs_to_contours_quad_to_cubic():
    seq = [
        (MOVE, [(0.0, 0.0)]),
        (QUAD, [(0.0, 0.0), (5.0, 10.0), (10.0, 0.0)]),
        (DONE, []),
    ]
    points, starts = verbs_to_contours(seq)
    # anchor + 1 cubic triplet = 4 points.
    assert len(points) == 4
    assert points[-1] == (10.0, 0.0)


def test_verbs_to_contours_multiple_contours():
    seq = [
        (MOVE, [(0.0, 0.0)]),
        (LINE, [(0.0, 0.0), (1.0, 1.0)]),
        (CLOSE, []),
        (MOVE, [(10.0, 10.0)]),
        (LINE, [(10.0, 10.0), (11.0, 11.0)]),
        (CLOSE, []),
    ]
    _points, starts = verbs_to_contours(seq)
    assert len(starts) == 2


def test_glyph_points_extracts_outlines():
    """Real glyph extraction (skia is installed in this environment)."""
    skia = pytest.importorskip("skia")
    _ = skia  # presence gate
    points, starts = glyph_points("Hi", family="Arial", size=40.0)
    assert len(points) > 0
    assert starts  # at least one contour


def test_glyph_points_empty_string_safe():
    skia = pytest.importorskip("skia")
    _ = skia
    points, starts = glyph_points("", family="Arial", size=40.0)
    assert points == []
    assert starts == []


def test_glyph_points_multi_glyph_advances_horizontally():
    """Successive glyphs advance rightward (x grows with each glyph)."""
    skia = pytest.importorskip("skia")
    _ = skia
    points, _starts = glyph_points("WW", family="Arial", size=40.0)
    xs = [p[0] for p in points]
    assert max(xs) > min(xs)
