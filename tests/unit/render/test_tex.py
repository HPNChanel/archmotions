"""Tests for the LaTeX → VMobject pipeline (skipped if latex/dvisvgm absent)."""

from __future__ import annotations

import pytest

from archmotion.render.tex import latex_available, tex_to_vmobject

latex_required = pytest.mark.skipif(not latex_available(), reason="latex + dvisvgm not installed")


@latex_required
def test_tex_compiles_simple_expression():
    obj = tex_to_vmobject(r"a + b = c")
    assert obj.points.shape[0] > 0
    assert obj.contour_starts


@latex_required
def test_tex_compiles_fraction():
    obj = tex_to_vmobject(r"\frac{1}{2}")
    assert obj.points.shape[0] > 0


def test_tex_unavailable_raises_when_missing(monkeypatch):
    """When latex is unavailable, tex_to_vmobject raises RuntimeError."""
    if latex_available():
        pytest.skip("latex present; cannot test the missing-binary path here")
    with pytest.raises(RuntimeError):
        tex_to_vmobject("x")


def test_dvisvgm_use_elements_are_placed_and_repeated(tmp_path):
    from archmotion.render.tex import _extract_paths

    svg = tmp_path / "glyphs.svg"
    svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg"
            xmlns:xlink="http://www.w3.org/1999/xlink">
          <defs><path id="glyph" d="M0 0 L2 0 L2 3 Z" /></defs>
          <g transform="translate(5 7)">
            <use x="10" y="20" xlink:href="#glyph" />
            <use x="30" y="20" xlink:href="#glyph" />
          </g>
        </svg>""",
        encoding="utf-8",
    )

    paths = _extract_paths(svg)
    assert len(paths) == 2
    assert min(point[0] for point in paths[0].points) == pytest.approx(15.0)
    assert min(point[0] for point in paths[1].points) == pytest.approx(35.0)
    assert min(point[1] for point in paths[0].points) == pytest.approx(27.0)


@latex_required
def test_repeated_tex_glyphs_keep_distinct_positions():
    single = tex_to_vmobject("x")
    repeated = tex_to_vmobject("x+x")
    assert repeated.bounding_box().width > single.bounding_box().width * 2
