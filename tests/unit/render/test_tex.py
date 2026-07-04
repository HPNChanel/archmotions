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
