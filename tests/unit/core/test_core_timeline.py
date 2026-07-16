"""Tests for the property model, timeline, animation system, and Scene."""

from __future__ import annotations

import pytest

from archmotion.animation import (
    AnimationGroup,
    Create,
    FadeIn,
    FadeOut,
    Transform,
)
from archmotion.core import Property, Scene, VMobject, ValueTracker, always_redraw


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


# ── PropertyAction ───────────────────────────────────────────────


def test_property_action_clamps_outside_interval():
    from archmotion.core import PropertyAction

    a = PropertyAction("x", Property.OPACITY, 1.0, 2.0, 0.0, 1.0, "linear")
    assert a.value_at(0.5) == 0.0
    assert a.value_at(1.5) == 0.5
    assert a.value_at(3.0) == 1.0


# ── Animations compile ───────────────────────────────────────────


def test_fade_in_compiles_opacity_zero_to_one():
    a = Square()
    fi = FadeIn(a, run_time=0.5)
    fi.begin()
    acts = fi.compile(0.0)
    assert len(acts) == 1
    assert acts[0].prop == Property.OPACITY
    assert acts[0].start_value == 0.0
    assert acts[0].end_value == 1.0
    fi.finish()
    assert a.opacity == 1.0


def test_fade_out_compiles_opacity_one_to_zero():
    a = Square()
    fo = FadeOut(a, run_time=0.5)
    acts = fo.compile(0.0)
    assert acts[0].start_value == 1.0
    assert acts[0].end_value == 0.0


def test_create_compiles_create_progress():
    a = Square()
    c = Create(a, run_time=1.0)
    acts = c.compile(0.0)
    assert acts[0].prop == Property.CREATE_PROGRESS
    assert acts[0].start_value == 0.0
    assert acts[0].end_value == 1.0


def test_transform_emits_morph_action():
    a = Square(100.0)
    b = Circle(60.0)
    t = Transform(a, b, run_time=1.0)
    t.begin()
    acts = t.compile(0.0)
    kinds = {type(x).__name__ for x in acts}
    assert "MorphAction" in kinds
    t.finish()
    # After finish, source adopts target point count.
    assert a.points.shape[0] == b.points.shape[0] or a.points.shape[0] >= b.points.shape[0]


def test_animation_group_staggers_start_times():
    a, b = Square(), Circle()
    g = AnimationGroup(FadeIn(a, run_time=1.0), FadeIn(b, run_time=1.0), lag_ratio=0.5)
    acts = g.compile(0.0)
    starts = sorted(x.start_time for x in acts)
    assert starts[0] == 0.0
    assert starts[1] == pytest.approx(0.5)


def test_fade_in_requires_target():
    with pytest.raises(TypeError):
        FadeIn()


# ── Scene + sticky timeline ──────────────────────────────────────


def test_scene_clock_advances_with_play_and_wait():
    sc = Scene(fps=30)
    a = Square()
    sc.add(a)
    sc.play(FadeIn(a, run_time=0.5))
    sc.wait(0.5)
    sc.play(FadeOut(a, run_time=0.5))
    assert sc.clock == pytest.approx(1.5)


def test_sticky_snapshot_hides_before_fadein():
    sc = Scene(fps=30)
    a = Square()
    sc.add(a)
    sc.play(FadeIn(a, run_time=1.0))  # starts at t=0
    tl = sc.compile_timeline()
    s_before = tl.snapshot_at(0.0)
    s_mid = tl.snapshot_at(0.5)
    s_after = tl.snapshot_at(2.0)
    assert s_before.scalars[a.id][Property.OPACITY] == 0.0
    assert 0.0 < s_mid.scalars[a.id][Property.OPACITY] < 1.0
    assert s_after.scalars[a.id][Property.OPACITY] == 1.0


def test_sticky_snapshot_visible_before_fadeout():
    sc = Scene(fps=30)
    a = Square()
    sc.add(a)
    sc.play(FadeOut(a, run_time=1.0))  # starts at t=0
    tl = sc.compile_timeline()
    assert tl.snapshot_at(0.0).scalars[a.id][Property.OPACITY] == 1.0
    assert tl.snapshot_at(2.0).scalars[a.id][Property.OPACITY] == 0.0


def test_play_accepts_animate_builder():
    sc = Scene(fps=30)
    a = Square()
    sc.add(a)
    sc.play(a.animate.shift(50.0, 0.0).set_fill("#ff0000"))
    tl = sc.compile_timeline()
    assert any(x.target_id == a.id for x in tl.morph_actions)


def test_value_tracker_builder_compiles_scalar_timeline():
    sc = Scene(fps=10)
    tracker = ValueTracker(2.0)
    sc.play(tracker.animate.set_value(12.0).set_run_time(1.0))
    timeline = sc.compile_timeline()

    assert tracker in sc.graphics
    assert timeline.snapshot_at(0.0).scalars[tracker.id][Property.VALUE] == 2.0
    assert timeline.snapshot_at(0.5).scalars[tracker.id][Property.VALUE] == pytest.approx(7.0)
    assert timeline.snapshot_at(1.0).scalars[tracker.id][Property.VALUE] == 12.0


def test_always_redraw_reads_frame_local_tracker_value():
    from archmotion.domains.geometry import Circle
    from archmotion.render.frame import FrameSpec, render_frame

    seen: list[float] = []
    tracker = ValueTracker(0.0)

    def factory():
        value = tracker.get_value()
        seen.append(value)
        return Circle(radius=5.0 + value, center=(40.0, 40.0))

    dynamic = always_redraw(factory)
    sc = Scene(resolution=(80, 80), fps=10)
    sc.add(tracker, dynamic)
    sc.play(tracker.animate.set_value(10.0).set_run_time(1.0))
    spec = FrameSpec(
        frame_index=5,
        width=80,
        height=80,
        fps=10,
        graphics=[dynamic],
        timeline=sc.compile_timeline(),
        camera=sc.camera,
        update_roots=sc.graphics,
    )

    render_frame(spec)
    assert seen[-1] == pytest.approx(5.0)
    assert dynamic.bounding_box().width == pytest.approx(20.0, abs=0.1)


def test_play_requires_animation():
    sc = Scene(fps=30)
    with pytest.raises(TypeError):
        sc.play()


def test_wait_negative_rejected():
    sc = Scene(fps=30)
    with pytest.raises(ValueError):
        sc.wait(-1.0)
