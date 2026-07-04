"""Tests for the SVG path parser (pure Python, always runs)."""

from __future__ import annotations

from archmotion.core.svg_path import parse_svg_path


def test_rect_path_has_four_line_segments():
    p = parse_svg_path("M 0 0 L 10 0 L 10 10 L 0 10 Z")
    assert p.contour_starts == [0]
    # anchor + 4 line triplets = 13 points.
    assert len(p.points) == 13
    assert p.points[0] == (0.0, 0.0)
    assert p.points[-1] == (0.0, 0.0)  # closed back to origin


def test_cubic_path():
    p = parse_svg_path("M 0 0 C 10 10 20 10 30 0")
    assert len(p.points) == 4  # anchor + 1 triplet
    assert p.points[1] == (10.0, 10.0)
    assert p.points[-1] == (30.0, 0.0)


def test_quad_converts_to_cubic():
    p = parse_svg_path("M 0 0 Q 50 100 100 0")
    assert len(p.points) == 4
    assert p.points[-1] == (100.0, 0.0)


def test_relative_moveto_and_lineto():
    p = parse_svg_path("m 10 10 l 20 0 l 0 20 z")
    assert p.points[0] == (10.0, 10.0)
    # Second point (end of first line) is relative: 10+20=30.
    # LineTo appends a triplet; the end point is index 3.
    assert p.points[3] == (30.0, 10.0)


def test_horizontal_vertical_commands():
    p = parse_svg_path("M 0 0 H 50 V 50 Z")
    # anchor + H + V + Z close = 3 line triplets = 10 points.
    assert len(p.points) == 10
    assert p.points[3] == (50.0, 0.0)


def test_multiple_contours():
    p = parse_svg_path("M 0 0 L 5 5 Z M 100 100 L 105 105 Z")
    assert len(p.contour_starts) == 2


def test_empty_path_safe():
    p = parse_svg_path("")
    assert p.points == []
    assert p.contour_starts == []
