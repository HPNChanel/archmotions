"""Renderer smoke tests (skia-gated) — exercise the generic path renderer for real.

These guard against skia-API regressions that only surface with skia installed
(e.g. the ``Create`` path-trim ``getSegment`` signature).
"""

from __future__ import annotations

import pytest

from archmotion.animation import Create, FadeIn, Transform
from archmotion.core import Scene
from archmotion.render.frame import FrameSpec, render_frame

skia = pytest.importorskip("skia", reason="skia-python not installed")


def _render_first_frame(scene: Scene) -> int:
    """Render frame 0 and return the byte count."""
    tl = scene.compile_timeline()
    graphics = [g for g in scene.all_graphics() if g.__class__.__name__ != "Scene"]
    spec = FrameSpec(
        frame_index=0,
        width=scene.resolution[0],
        height=scene.resolution[1],
        fps=scene.fps,
        graphics=graphics,
        timeline=tl,
        camera=scene.camera,
    )
    return len(render_frame(spec))


def test_render_frame_geometry():
    from archmotion.domains.geometry import Circle

    sc = Scene(resolution=(200, 150), fps=24)
    sc.add(Circle(radius=40).move_to(100, 75).set_fill("#3b82f6"))
    sc.play(FadeIn(Circle(radius=30).move_to(100, 75)))
    assert _render_first_frame(sc) == 200 * 150 * 4


def test_render_create_uses_path_trim():
    """Create exercises PathMeasure.getSegment with the correct signature."""
    from archmotion.domains.geometry import Square

    sc = Scene(resolution=(200, 150), fps=24)
    sc.add(Square(side=60).move_to(100, 75).set_fill("#22c55e"))
    sc.play(Create(Square(side=40).move_to(100, 75)))
    # Frame 0 is during the Create → CREATE_PROGRESS 0 → trimmed path.
    assert _render_first_frame(sc) == 200 * 150 * 4


def test_render_text_and_transform():
    from archmotion.domains.geometry import Circle
    from archmotion.domains.text import Text

    sc = Scene(resolution=(200, 150), fps=24)
    t = Text("A", size=30).move_to(100, 75)
    sc.add(t)
    sc.play(Transform(t, Circle(radius=30).move_to(100, 75)))
    assert _render_first_frame(sc) == 200 * 150 * 4
