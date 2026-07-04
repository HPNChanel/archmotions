"""Tests for the geometry domain (shapes, lines, coordinate systems, morphing)."""

from __future__ import annotations

import math

import pytest

from archmotion.animation import Transform
from archmotion.core import Scene
from archmotion.domains.geometry import (
    Annulus,
    Arc,
    Arrow,
    Axes,
    Circle,
    DashedLine,
    Dot,
    DoubleArrow,
    Ellipse,
    FunctionGraph,
    Line,
    NumberLine,
    ParametricFunction,
    Polygon,
    Polyline,
    Rectangle,
    RegularPolygon,
    RoundedRectangle,
    Square,
)


def test_circle_bbox_matches_radius():
    c = Circle(radius=50.0)
    bbox = c.bounding_box()
    assert bbox.width == pytest.approx(100.0, abs=2.0)
    assert bbox.height == pytest.approx(100.0, abs=2.0)


def test_rectangle_dimensions():
    r = Rectangle(width=120.0, height=80.0)
    bbox = r.bounding_box()
    assert bbox.width == pytest.approx(120.0)
    assert bbox.height == pytest.approx(80.0)


def test_square_is_equilateral():
    s = Square(side=64.0)
    bbox = s.bounding_box()
    assert bbox.width == pytest.approx(bbox.height)


def test_regular_polygon_vertex_count():
    hexagon = RegularPolygon(n=6, radius=40.0)
    # 6 vertices → 1 anchor + 6 line triplets = 19 points.
    assert hexagon.n_curves == 6


def test_polygon_closes():
    tri = Polygon((0.0, 0.0), (10.0, 0.0), (5.0, 8.0))
    pts = tri.points
    assert pts[0] == pytest.approx(tuple(pts[-1]))


def test_line_is_open_two_points_anchor():
    line = Line((0.0, 0.0), (100.0, 0.0))
    assert line.n_curves == 1


def test_ellipse_bbox_matches_axes():
    e = Ellipse(width=120.0, height=80.0)
    bbox = e.bounding_box()
    assert bbox.width == pytest.approx(120.0, abs=5.0)
    assert bbox.height == pytest.approx(80.0, abs=5.0)


def test_dashed_line_has_multiple_contours():
    d = DashedLine((0.0, 0.0), (100.0, 0.0), dash_length=10.0, gap=6.0)
    assert len(d.contour_starts) > 1


def test_arrow_has_arrowhead_points():
    a = Arrow((0.0, 0.0), (100.0, 0.0))
    # Shaft + head produce more than a single segment.
    assert a.n_curves >= 4


def test_double_arrow_extends_arrow():
    da = DoubleArrow((0.0, 0.0), (100.0, 0.0))
    assert da.n_curves >= 6


def test_annulus_has_two_contours():
    ring = Annulus(inner_radius=20.0, outer_radius=50.0)
    assert len(ring.contour_starts) == 2


def test_number_line_maps_value_to_point():
    nl = NumberLine((0.0, 10.0), length=100.0, center=(50.0, 0.0))
    p = nl.number_to_point(5.0)
    assert p[0] == pytest.approx(50.0)


def test_axes_c2p_maps_origin_to_center():
    ax = Axes(x_range=(-1.0, 1.0), y_range=(-1.0, 1.0), center=(200.0, 200.0))
    p = ax.c2p(0.0, 0.0)
    assert p[0] == pytest.approx(200.0)
    assert p[1] == pytest.approx(200.0)


def test_function_graph_samples_curve():
    fg = FunctionGraph(lambda x: x * x, x_range=(-1.0, 1.0), samples=20)
    bbox = fg.bounding_box()
    # y = x^2 over [-1,1] → y in [0,1]; width spans the x-range pixels.
    assert bbox.width > 0
    assert bbox.height > 0


def test_parametric_function_circle_approx():
    pf = ParametricFunction(
        lambda t: (math.cos(t), math.sin(t)), t_range=(0.0, 2 * math.pi), samples=64
    )
    assert pf.n_curves >= 60


def test_transform_between_geometry_shapes():
    sc = Scene(fps=30)
    a = Circle(radius=50.0)
    sc.add(a)
    sc.play(Transform(a, Square(side=80.0)))
    tl = sc.compile_timeline()
    assert any(m.target_id == a.id for m in tl.morph_actions)


def test_rounded_rectangle_generates_points():
    rr = RoundedRectangle(width=120.0, height=80.0, corner_radius=15.0)
    assert rr.n_curves >= 8
