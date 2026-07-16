"""Tests for the charts domain + chart -> shape fusion."""

from __future__ import annotations

import pytest

from archmotion.animation import Transform
from archmotion.core import Scene
from archmotion.domains.charts import BarChart, LineChart, PieChart, ScatterPlot
from archmotion.domains.geometry import Circle


def test_bar_chart_one_contour_per_value():
    chart = BarChart([1.0, 2.0, 3.0], origin=(0.0, 200.0))
    assert len(chart.contour_starts) == 3


def test_bar_chart_heights_proportional():
    chart = BarChart([1.0, 2.0, 4.0], height=120.0, origin=(0.0, 200.0), max_value=4.0)
    bbox = chart.bounding_box()
    # Tallest bar (value 4) reaches 120px above the baseline.
    assert bbox.height == pytest.approx(120.0, abs=1.0)


def test_line_chart_is_single_polyline():
    chart = LineChart([1.0, 3.0, 2.0, 4.0])
    assert chart.n_curves == 3  # 4 points -> 3 segments


def test_pie_chart_wedge_count_matches_values():
    chart = PieChart([1.0, 2.0, 3.0])
    assert len(chart.contour_starts) == 3


def test_bar_chart_transforms_to_circle_fusion():
    sc = Scene(fps=30)
    chart = BarChart([2.0, 4.0, 6.0], origin=(200.0, 300.0))
    sc.add(chart)
    sc.play(Transform(chart, Circle(radius=50.0).move_to(200.0, 250.0)))
    tl = sc.compile_timeline()
    assert any(m.target_id == chart.id for m in tl.morph_actions)


def test_empty_charts_safe():
    assert BarChart([]).points.shape[0] == 0
    assert LineChart([1.0]).points.shape[0] == 0
    assert PieChart([0.0, 0.0]).points.shape[0] == 0


def test_scatter_plot_one_contour_per_point():
    plot = ScatterPlot([(0.0, 0.0), (1.0, 2.0), (2.0, 1.0)], width=200.0, height=150.0)
    assert len(plot.contour_starts) == 3


def test_scatter_plot_empty_safe():
    plot = ScatterPlot([])
    assert plot.points.shape[0] == 0


def test_scatter_plot_maps_data_to_pixels():
    plot = ScatterPlot(
        [(0.0, 0.0), (10.0, 10.0)],
        x_range=(0.0, 10.0),
        y_range=(0.0, 10.0),
        width=100.0,
        height=100.0,
        origin=(0.0, 100.0),
    )
    pts = plot.points
    # First point at data (0,0) → pixel (0, 100) [bottom-left].
    assert pts[0][0] == pytest.approx(5.0, abs=1.0)  # dot radius offset
    # Second point at data (10,10) → pixel (100, 0) [top-right].
    assert pts[0][0] < pts[-1][0]  # x increases
