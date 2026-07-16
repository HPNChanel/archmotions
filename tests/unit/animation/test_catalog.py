"""Tests for the new Phase-6 animation catalog.

Covers: Write, Uncreate, DrawBorderThenFill, Typewriter, ReplacementTransform,
GrowFromCenter, GrowFromEdge, GrowBar, DrawLine, SweepPie, Flash, Indicate,
FadeToColor.
"""

from __future__ import annotations

import pytest

from archmotion.animation import (
    DrawBorderThenFill,
    DrawLine,
    FadeToColor,
    Flash,
    GrowBar,
    GrowFromCenter,
    GrowFromEdge,
    Indicate,
    ReplacementTransform,
    SweepPie,
    Typewriter,
    Uncreate,
    Write,
)
from archmotion.core import Property, Scene
from archmotion.domains.architecture import Node
from archmotion.domains.geometry import Circle, Rectangle

# ──────────────────────────────────────────────
# Creation animations
# ──────────────────────────────────────────────


class TestWrite:
    def test_emits_create_progress(self):
        n = Node("X")
        sc = Scene(fps=30)
        sc.add(n)
        sc.play(Write(n, run_time=1.0))
        tl = sc.compile_timeline()
        cp = [a for a in tl.property_actions if a.prop == Property.CREATE_PROGRESS]
        assert len(cp) == 1
        assert cp[0].start_value == pytest.approx(0.0)
        assert cp[0].end_value == pytest.approx(1.0)

    def test_finish_sets_opacity(self):
        n = Node("X")
        anim = Write(n)
        anim.finish()
        assert n.opacity == pytest.approx(1.0)


class TestUncreate:
    def test_emits_reverse_create_progress(self):
        n = Node("X")
        sc = Scene(fps=30)
        sc.add(n)
        sc.play(Uncreate(n, run_time=1.0))
        tl = sc.compile_timeline()
        cp = [a for a in tl.property_actions if a.prop == Property.CREATE_PROGRESS]
        assert len(cp) == 1
        assert cp[0].start_value == pytest.approx(1.0)
        assert cp[0].end_value == pytest.approx(0.0)

    def test_finish_hides(self):
        n = Node("X")
        anim = Uncreate(n)
        anim.finish()
        assert n.opacity == pytest.approx(0.0)


class TestDrawBorderThenFill:
    def test_emits_create_and_fill_opacity(self):
        n = Node("X")
        sc = Scene(fps=30)
        sc.add(n)
        sc.play(DrawBorderThenFill(n, run_time=2.0))
        tl = sc.compile_timeline()
        cp = [a for a in tl.property_actions if a.prop == Property.CREATE_PROGRESS]
        fo = [a for a in tl.property_actions if a.prop == Property.FILL_OPACITY]
        assert len(cp) == 1
        assert len(fo) == 1
        # Fill opacity starts at 0, ends at the original fill opacity.
        assert fo[0].start_value == pytest.approx(0.0)
        # Create finishes in the first half; fill in the second half.
        assert cp[0].end_time < fo[0].end_time


class TestTypewriter:
    def test_uses_linear_rate(self):
        n = Node("X")
        tw = Typewriter(n, run_time=1.0)
        assert tw.rate_func == "linear"


# ──────────────────────────────────────────────
# Transform variant
# ──────────────────────────────────────────────


class TestReplacementTransform:
    def test_finish_commits_original_points(self):
        a = Circle(radius=40.0).move_to(100.0, 100.0)
        b = Rectangle(width=60.0, height=30.0).move_to(200.0, 200.0)
        orig_target_pts = b.points.copy()
        anim = ReplacementTransform(a, b, run_time=1.0)
        anim.begin()
        anim.finish()
        # Source adopts the target's ORIGINAL points (not aligned/resampled).
        import numpy as np

        assert np.allclose(a.points, orig_target_pts)


# ──────────────────────────────────────────────
# Growth animations
# ──────────────────────────────────────────────


class TestGrowFromCenter:
    def test_emits_scale_and_opacity(self):
        n = Node("X")
        sc = Scene(fps=30)
        sc.add(n)
        sc.play(GrowFromCenter(n, run_time=1.0))
        tl = sc.compile_timeline()
        scales = [a for a in tl.property_actions if a.prop == Property.SCALE]
        opacities = [a for a in tl.property_actions if a.prop == Property.OPACITY]
        assert len(scales) == 1
        assert scales[0].start_value == pytest.approx(0.0)
        assert scales[0].end_value == pytest.approx(1.0)
        assert len(opacities) == 1
        assert opacities[0].start_value == pytest.approx(0.0)


class TestGrowFromEdge:
    def test_emits_scale_opacity_position(self):
        n = Node("X")
        sc = Scene(fps=30)
        sc.add(n)
        sc.play(GrowFromEdge(n, edge="bottom", run_time=1.0))
        tl = sc.compile_timeline()
        scales = [a for a in tl.property_actions if a.prop == Property.SCALE]
        pos_y = [a for a in tl.property_actions if a.prop == Property.POSITION_Y]
        assert len(scales) == 1
        assert len(pos_y) == 1
        # Position Y starts non-zero (edge offset) and ends at 0.
        assert pos_y[0].end_value == pytest.approx(0.0)

    def test_invalid_edge_raises(self):
        n = Node("X")
        with pytest.raises(ValueError, match="edge"):
            GrowFromEdge(n, edge="sideways")


class TestGrowBar:
    def test_emits_morph_action(self):
        bar = Rectangle(width=30.0, height=100.0)
        sc = Scene(fps=30)
        sc.add(bar)
        sc.play(GrowBar(bar, run_time=1.0))
        tl = sc.compile_timeline()
        assert len(tl.morph_actions) == 1
        assert tl.morph_actions[0].target_id == bar.id


# ──────────────────────────────────────────────
# Chart animations
# ──────────────────────────────────────────────


class TestDrawLine:
    def test_emits_create_progress(self):
        line = Rectangle(width=100.0, height=2.0)
        sc = Scene(fps=30)
        sc.add(line)
        sc.play(DrawLine(line, run_time=1.0))
        tl = sc.compile_timeline()
        cp = [a for a in tl.property_actions if a.prop == Property.CREATE_PROGRESS]
        assert len(cp) == 1
        assert cp[0].start_value == pytest.approx(0.0)


class TestSweepPie:
    def test_emits_create_progress(self):
        from archmotion.domains.charts import PieChart

        pie = PieChart([3.0, 7.0])
        sc = Scene(fps=30)
        sc.add(pie)
        sc.play(SweepPie(pie, run_time=1.0))
        tl = sc.compile_timeline()
        cp = [a for a in tl.property_actions if a.prop == Property.CREATE_PROGRESS]
        assert len(cp) == 1


# ──────────────────────────────────────────────
# Indicator / effect animations
# ──────────────────────────────────────────────


class TestFlash:
    def test_emits_scale_and_glow(self):
        n = Node("X")
        sc = Scene(fps=30)
        sc.add(n)
        sc.play(Flash(n, run_time=0.5))
        tl = sc.compile_timeline()
        scales = [a for a in tl.property_actions if a.prop == Property.SCALE]
        glows = [a for a in tl.property_actions if a.prop == Property.GLOW_INTENSITY]
        assert len(scales) == 2  # up then down
        assert len(glows) == 2  # spike up then down
        assert scales[0].end_value == pytest.approx(1.5)
        assert scales[1].end_value == pytest.approx(1.0)


class TestIndicate:
    def test_emits_scale_and_color(self):
        n = Node("X").set_fill("#3b82f6")
        sc = Scene(fps=30)
        sc.add(n)
        sc.play(Indicate(n, color="#ff0000", run_time=0.5))
        tl = sc.compile_timeline()
        scales = [a for a in tl.property_actions if a.prop == Property.SCALE]
        fill_r = [a for a in tl.property_actions if a.prop == Property.FILL_R]
        assert len(scales) == 2  # up then down
        assert len(fill_r) == 2  # to flash color then back


class TestFadeToColor:
    def test_reads_current_color(self):
        n = Node("X").set_fill("#3b82f6")
        sc = Scene(fps=30)
        sc.add(n)
        sc.play(FadeToColor(n, "#ff0000", run_time=0.8))
        tl = sc.compile_timeline()
        fill_r = [a for a in tl.property_actions if a.prop == Property.FILL_R]
        assert len(fill_r) == 1
        # Start value = current fill R (blue → low R).
        assert fill_r[0].start_value < 0.5
        # End value = target R (red → high R).
        assert fill_r[0].end_value > 0.5

    def test_finish_commits_color(self):
        n = Node("X").set_fill("#3b82f6")
        anim = FadeToColor(n, "#ff0000")
        anim.finish()
        assert n.style.fill_color == "#ff0000"
