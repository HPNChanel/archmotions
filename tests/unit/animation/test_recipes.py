"""Tests for architecture recipe animations (Transfer/Pulse/Highlight/ColorShift/Scale)."""

from __future__ import annotations

import pytest

from archmotion.animation import ColorShift, FadeIn, Highlight, Pulse, Scale, Transfer
from archmotion.core import Property, Scene
from archmotion.domains.architecture import Connection, Node


def test_pulse_emits_ramp_up_and_down():
    n = Node("X")
    sc = Scene(fps=30)
    sc.add(n)
    sc.play(Pulse(n, run_time=1.0, intensity=0.8))
    tl = sc.compile_timeline()
    glow = [a for a in tl.property_actions if a.prop == Property.GLOW_INTENSITY]
    assert len(glow) == 2  # ramp up + ramp down
    assert glow[0].end_value == pytest.approx(0.8)
    assert glow[1].end_value == pytest.approx(0.0)


def test_highlight_ramps_then_holds():
    n = Node("X")
    sc = Scene(fps=30)
    sc.add(n)
    sc.play(Highlight(n, run_time=2.0, intensity=0.9))
    tl = sc.compile_timeline()
    glow = [a for a in tl.property_actions if a.prop == Property.GLOW_INTENSITY]
    assert len(glow) == 2
    # The hold segment keeps peak intensity.
    assert glow[1].start_value == pytest.approx(0.9)
    assert glow[1].end_value == pytest.approx(0.9)


def test_colorshift_commits_end_color():
    n = Node("X").set_fill("#4caf50")
    sc = Scene(fps=30)
    sc.add(n)
    sc.play(ColorShift(n, "#4caf50", "#f44336", run_time=1.0))
    sc.compile_timeline()
    # finish() commits the end fill color.
    assert n.style.fill_color == "#f44336"


def test_scale_emits_scale_property():
    n = Node("X")
    sc = Scene(fps=30)
    sc.add(n)
    sc.play(Scale(n, 1.5, run_time=0.3))
    tl = sc.compile_timeline()
    scale = [a for a in tl.property_actions if a.prop == Property.SCALE]
    assert scale[0].start_value == pytest.approx(1.0)
    assert scale[0].end_value == pytest.approx(1.5)


def test_transfer_emits_path_progress():
    a = Node("A", center=(0.0, 0.0))
    b = Node("B", center=(300.0, 0.0))
    conn = Connection(a, b)
    sc = Scene(fps=30)
    sc.add(a, b, conn)
    sc.play(FadeIn(a, b), Transfer(conn, run_time=1.0))
    tl = sc.compile_timeline()
    progress = [act for act in tl.property_actions if act.prop == Property.PATH_PROGRESS]
    assert progress
    # Transfer auto-creates a Packet bound to the connection.
    assert progress[0].target_id != a.id
    assert progress[0].target_id != b.id
