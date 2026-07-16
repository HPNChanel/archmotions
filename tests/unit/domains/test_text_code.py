"""Tests for the Text + Code domains (skia-gated)."""

from __future__ import annotations

import pytest

from archmotion.animation import FadeIn, Transform
from archmotion.core import Scene

skia = pytest.importorskip("skia", reason="skia-python not installed")


def test_text_has_one_contour_per_glyph():
    from archmotion.domains.text import Text

    t = Text("HH", size=40.0)
    # Two glyphs, each a single closed contour.
    assert len(t.contour_starts) == 2
    assert t.points.shape[0] > 0


def test_text_bbox_has_positive_width():
    from archmotion.domains.text import Text

    t = Text("Hello", size=40.0)
    bbox = t.bounding_box()
    assert bbox.width > 0
    assert bbox.height > 0


def test_text_can_transform_to_circle():
    from archmotion.domains.geometry import Circle
    from archmotion.domains.text import Text

    sc = Scene(fps=30)
    t = Text("X", size=40.0)
    sc.add(t)
    sc.play(Transform(t, Circle(radius=40.0).move_to(100.0, 100.0)))
    tl = sc.compile_timeline()
    assert any(m.target_id == t.id for m in tl.morph_actions)


def test_codeblock_builds_line_groups():
    from archmotion.domains.code import CodeBlock

    code = "def f(x):\n    return x + 1\n"
    cb = CodeBlock(code, language="python", size=20.0, origin=(0.0, 0.0))
    # Two non-empty lines → two line groups.
    assert len(cb.children) == 2
    # Each line holds colored Text spans.
    assert all(len(line.children) >= 1 for line in cb.children)


def test_codeblock_applies_syntax_colors():
    from archmotion.domains.code import CodeBlock

    cb = CodeBlock("return 42", language="python", size=20.0)
    colors = {span.style.fill_color for line in cb.children for span in line.children}
    # More than one color → syntax highlighting applied.
    assert len(colors) > 1


def test_codeblock_unknown_language_falls_back():
    from archmotion.domains.code import CodeBlock

    cb = CodeBlock("plain text line", language="not-a-real-lang-xyz", size=20.0)
    assert len(cb.children) >= 1


def test_codeblock_in_scene_renders_fadein():
    from archmotion.domains.code import CodeBlock

    sc = Scene(fps=30)
    cb = CodeBlock("x = 1\n", language="python", size=20.0)
    sc.add(cb)
    sc.play(FadeIn(*[span for line in cb.children for span in line.children]))
    tl = sc.compile_timeline()
    assert tl.total_frames > 0


def test_paragraph_creates_line_per_string():
    from archmotion.domains.text import Paragraph

    p = Paragraph("Line One\nLine Two\nLine Three", size=30.0)
    assert len(p.children) == 3


def test_paragraph_accepts_list_of_strings():
    from archmotion.domains.text import Paragraph

    p = Paragraph(["A", "B"], size=30.0)
    assert len(p.children) == 2


def test_paragraph_lines_are_stacked_vertically():
    from archmotion.domains.text import Paragraph

    p = Paragraph(["Top", "Bottom"], size=40.0, line_spacing=1.5)
    # Second line should be shifted down (negative y) relative to the first.
    bbox0 = p.children[0].bounding_box()
    bbox1 = p.children[1].bounding_box()
    assert bbox1.y > bbox0.y  # y grows downward; second line is below first
