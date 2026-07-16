"""Frame rendering + MP4 export for v2.0 scenes (skia-lazy).

``render_scene`` compiles the timeline, paints each frame via the generic
:class:`~archmotion.render.path_render` renderer, and pipes raw RGBA frames into
FFmpeg (``imageio-ffmpeg``) to produce an MP4. ``render_frame`` is a picklable
single-frame function so the same data can later be farmed to a worker pool.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from archmotion.core.vmobject import VMobject
from archmotion.render.path_render import (
    DEFAULT_BACKGROUND_RGBA,
    paint_effective,
    resolve_effective,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from archmotion.core.camera import Camera
    from archmotion.core.graphic import Graphic
    from archmotion.core.property import CompiledTimeline
    from archmotion.core.scene import Scene
    from archmotion.render.theme import ThemeConfig


@dataclass
class FrameSpec:
    """Picklable data for rendering one frame."""

    frame_index: int
    width: int
    height: int
    fps: int
    graphics: list[VMobject]
    timeline: CompiledTimeline
    camera: Camera
    background_rgba: tuple[float, float, float, float] = DEFAULT_BACKGROUND_RGBA
    theme: ThemeConfig | None = None
    update_roots: list[Graphic] = field(default_factory=list)
    extra: dict[str, object] = field(default_factory=dict)


def render_frame(spec: FrameSpec) -> bytes:
    """Render a single frame → raw RGBA bytes."""
    from archmotion.render.canvas import SkiaCanvas, rgba_to_color4f

    canvas = SkiaCanvas(spec.width, spec.height)
    try:
        canvas.clear(rgba_to_color4f(spec.background_rgba))
        snapshot = spec.timeline.snapshot_at_frame(spec.frame_index)
        from archmotion.core.property import Property
        from archmotion.core.updaters import reset_render_values, set_render_values
        from archmotion.render.path_render import theme_style_for

        tracker_values = {
            target_id: values[Property.VALUE]
            for target_id, values in snapshot.scalars.items()
            if Property.VALUE in values
        }
        token = set_render_values(tracker_values)
        try:
            dt = 0.0 if spec.frame_index == 0 else 1.0 / spec.fps
            for root in spec.update_roots:
                root.update(dt)
            for graphic in spec.graphics:
                state = resolve_effective(
                    graphic,
                    snapshot.scalars.get(graphic.id),
                    snapshot.morphs.get(graphic.id),
                    spec.camera,
                    theme_style_for(graphic, spec.theme),
                    scalar_lookup=snapshot.scalars,
                    morph_contour_starts=snapshot.morph_contours.get(graphic.id),
                )
                paint_effective(canvas.native, state)
        finally:
            reset_render_values(token)
        return canvas.snapshot()
    finally:
        canvas.dispose()


def render_scene(
    scene: Scene,
    output_path: str,
    *,
    fps: int | None = None,
    crf: int = 20,
    on_progress: Callable[[int, int], None] | None = None,
) -> str:
    """Render the scene to ``output_path`` (MP4). Returns the path."""
    eff_fps = fps if fps is not None else scene.fps
    timeline = replace(scene.compile_timeline(), fps=eff_fps)
    graphics = [g for g in scene.all_graphics() if isinstance(g, VMobject)]
    width, height = scene.resolution

    total_frames = max(1, timeline.total_frames)
    from pathlib import Path

    from archmotion.render.ffmpeg import FFmpegPipe, cpu_encoder

    pipe = FFmpegPipe.open(
        Path(output_path),
        width,
        height,
        eff_fps,
        encoder=cpu_encoder(crf),
        crf=crf,
    )

    try:
        for frame_index in range(total_frames):
            spec = FrameSpec(
                frame_index=frame_index,
                width=width,
                height=height,
                fps=eff_fps,
                graphics=graphics,
                timeline=timeline,
                camera=scene.camera,
                background_rgba=_background(scene),
                theme=scene.theme,
                update_roots=scene.graphics,
            )
            frame_bytes = render_frame(spec)
            pipe.write_frame(frame_bytes)
            if on_progress is not None:
                on_progress(frame_index + 1, total_frames)
        pipe.close()
    except Exception:
        pipe.kill()
        raise

    return output_path


def _background(scene: Scene) -> tuple[float, float, float, float]:
    theme = getattr(scene, "theme", None)
    rgba = getattr(theme, "background_rgba", None) if theme is not None else None
    if rgba is not None:
        return tuple(rgba)
    return DEFAULT_BACKGROUND_RGBA
