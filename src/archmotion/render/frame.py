"""Frame rendering + MP4 export for v2.0 scenes (skia-lazy).

``render_scene`` compiles the timeline, paints each frame via the generic
:class:`~archmotion.render.path_render` renderer, and pipes raw RGBA frames into
FFmpeg (``imageio-ffmpeg``) to produce an MP4. ``render_frame`` is a picklable
single-frame function so the same data can later be farmed to a worker pool.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from archmotion.core.vmobject import VMobject
from archmotion.render.path_render import (
    DEFAULT_BACKGROUND_RGBA,
    paint_effective,
    resolve_effective,
)

if TYPE_CHECKING:
    from archmotion.core.camera import Camera
    from archmotion.core.property import CompiledTimeline, FrameSnapshot
    from archmotion.core.scene import Scene


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
    extra: dict[str, object] = field(default_factory=dict)


def render_frame(spec: FrameSpec) -> bytes:
    """Render a single frame → raw RGBA bytes."""
    from archmotion.renderer.canvas import SkiaCanvas, rgba_to_color4f

    canvas = SkiaCanvas(spec.width, spec.height)
    try:
        canvas.clear(rgba_to_color4f(spec.background_rgba))
        snapshot = spec.timeline.snapshot_at_frame(spec.frame_index)
        for graphic in spec.graphics:
            state = resolve_effective(
                graphic,
                snapshot.scalars.get(graphic.id),
                snapshot.morphs.get(graphic.id),
                spec.camera,
            )
            paint_effective(canvas.native, state)
        return canvas.snapshot()
    finally:
        canvas.dispose()


def render_scene(
    scene: Scene,
    output_path: str,
    *,
    fps: int | None = None,
    crf: int = 20,
) -> str:
    """Render the scene to ``output_path`` (MP4). Returns the path."""
    import imageio_ffmpeg

    eff_fps = fps if fps is not None else scene.fps
    timeline = scene.compile_timeline()
    graphics = [g for g in scene.all_graphics() if isinstance(g, VMobject)]
    width, height = scene.resolution

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgba",
        "-s", f"{width}x{height}",
        "-r", str(eff_fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(crf),
        "-preset", "veryfast",
        output_path,
    ]

    total_frames = max(1, timeline.total_frames)
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if proc.stdin is None:
        msg = "Failed to open FFmpeg stdin pipe."
        raise RuntimeError(msg)
    stdin = proc.stdin

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
            )
            frame_bytes = render_frame(spec)
            stdin.write(frame_bytes)
        stdin.close()
        stderr = proc.communicate(timeout=300)[1]
        if proc.returncode != 0:
            msg = f"FFmpeg failed (code {proc.returncode}):\n{stderr.decode(errors='replace')}"
            raise RuntimeError(msg)
    finally:
        if proc.poll() is None:
            proc.kill()

    return output_path


def _background(scene: Scene) -> tuple[float, float, float, float]:
    theme = getattr(scene, "theme", None)
    rgba = getattr(theme, "background_rgba", None) if theme is not None else None
    if rgba is not None:
        return tuple(rgba)
    return DEFAULT_BACKGROUND_RGBA
