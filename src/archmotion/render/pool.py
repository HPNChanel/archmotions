"""Single/parallel process orchestration for frame rendering (v2).

Architectural Note:
    This module manages the frame → :class:`~archmotion.render.ffmpeg.FFmpegPipe`
    pipeline. Windows and updater-driven scenes use a deterministic single
    process. Eligible scenes on other platforms may use ``Pool.imap()`` while
    preserving sequential FFmpeg input order.

    v2 IPC design (improves on v1):
        The immutable render context (graphics list + compiled timeline + camera +
        dimensions) is shared **once** with every worker via a Pool *initializer*
        (pickled at pool startup, not per frame). Each task then carries only a
        ``frame_index`` (and a SharedMemory slot name in shm mode). This avoids
        re-pickling the multi-MB graphics/timeline payload for every frame.

    Optional SharedMemory output ring:
        Workers write rendered RGBA bytes directly into pre-allocated
        :class:`~archmotion.render.shm.SharedMemoryRing` slots (zero-copy,
        zero-serialization). The main process reads from shared memory and pipes
        to FFmpeg. This mode is opt-in and falls back to standard pickle IPC if
        allocation fails.

    Zero-Disk I/O: raw RGBA bytes flow from workers → shared memory → FFmpeg stdin.
    No temporary files are ever written to disk.

    Worker Sizing:
        Windows defaults to one. Other platforms use
        ``min(cpu_count * WORKER_RATIO, MAX_WORKERS)`` unless explicitly set.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from archmotion.constants import MAX_WORKERS, WORKER_RATIO
from archmotion.render.ffmpeg import FFmpegPipe
from archmotion.render.frame import FrameSpec, render_frame
from archmotion.render.shm import (
    _DEFAULT_RING_SIZE,
    SharedMemoryRing,
    SharedMemorySlot,
    iter_shm_slots,
)

if TYPE_CHECKING:
    from archmotion.core.camera import Camera
    from archmotion.core.graphic import Graphic
    from archmotion.core.property import CompiledTimeline
    from archmotion.core.vmobject import VMobject
    from archmotion.render.theme import ThemeConfig

logger = logging.getLogger("archmotion.render")

# ──────────────────────────────────────────────
# Progress Callback
# ──────────────────────────────────────────────

ProgressCallback = Callable[[int, int], None]
"""Callback signature: ``(frames_completed, total_frames) -> None``."""


# ──────────────────────────────────────────────
# Export Result
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class ExportResult:
    """Result of a completed export operation.

    Attributes:
        output_path: Path to the created video file.
        total_frames: Number of frames rendered.
        encoder_label: Human-readable encoder name.
        file_size_bytes: Size of the output file in bytes.
        workers: Number of worker processes used.
        ipc_mode: IPC strategy used (``"shm"`` or ``"pickle"``).
    """

    output_path: Path
    total_frames: int
    encoder_label: str
    file_size_bytes: int
    workers: int
    ipc_mode: str


# ──────────────────────────────────────────────
# Shared Render Context (pickled once per worker at pool startup)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class RenderContext:
    """The immutable render payload shared with every worker once.

    Each worker builds a per-frame :class:`FrameSpec` from this context plus the
    ``frame_index`` it receives as its task. All fields are picklable
    (numpy arrays + frozen dataclasses + primitives).

    Attributes:
        graphics: The scene's paintable VMobjects (z-ordered).
        timeline: The compiled parametric timeline.
        camera: The output viewport.
        width / height: Output resolution in pixels.
        fps: Frame rate.
        background_rgba: Background colour as (r, g, b, a) floats in [0, 1].
    """

    graphics: tuple[VMobject, ...]
    timeline: CompiledTimeline
    camera: Camera
    width: int
    height: int
    fps: int
    background_rgba: tuple[float, float, float, float]
    theme: ThemeConfig | None = None
    update_roots: tuple[Graphic, ...] = ()


# Module-global context set once per worker process by the initializer.
_CTX: RenderContext | None = None


def _init_worker(ctx: RenderContext) -> None:
    """Pool initializer — store the shared context in a worker-local global."""
    global _CTX
    _CTX = ctx


def _build_spec(frame_index: int) -> FrameSpec:
    """Build a :class:`FrameSpec` for ``frame_index`` from the worker context."""
    assert _CTX is not None  # noqa: S101 — invariant: initializer ran first
    return FrameSpec(
        frame_index=frame_index,
        width=_CTX.width,
        height=_CTX.height,
        fps=_CTX.fps,
        graphics=list(_CTX.graphics),
        timeline=_CTX.timeline,
        camera=_CTX.camera,
        background_rgba=_CTX.background_rgba,
        theme=_CTX.theme,
        update_roots=list(_CTX.update_roots),
    )


def _render_index(frame_index: int) -> bytes:
    """Render a single frame → raw RGBA bytes (pickle IPC task)."""
    spec = _build_spec(frame_index)
    return render_frame(spec)


def _render_index_to_shm(args: tuple[int, str]) -> int:
    """Render a frame and write output to a SharedMemory slot (shm IPC task).

    Args:
        args: ``(frame_index, slot_name)``.

    Returns:
        The ``frame_index`` (lightweight int, cheap to pickle back).
    """
    frame_index, slot_name = args
    spec = _build_spec(frame_index)
    frame_bytes = render_frame(spec)

    slot = SharedMemorySlot(name=slot_name, frame_size=len(frame_bytes))
    try:
        slot.write(frame_bytes)
    finally:
        slot.close()

    return frame_index


# ──────────────────────────────────────────────
# Worker Count
# ──────────────────────────────────────────────


def compute_worker_count(workers: int | None = None) -> int:
    """Calculate the number of worker processes to use.

    When ``workers`` is None the formula is
    ``min(cpu_count * WORKER_RATIO, MAX_WORKERS)``, minimum 1.

    Args:
        workers: Explicit override (``None`` → auto-size).

    Returns:
        Number of worker processes.
    """
    if workers is not None:
        return max(1, workers)
    if sys.platform == "win32":
        # Spawn re-imports the user's scene module. A reliable default must not
        # require every first-time script to understand multiprocessing guards.
        return 1
    cpu_count = mp.cpu_count() or 4
    return max(1, min(int(cpu_count * WORKER_RATIO), MAX_WORKERS))


# ──────────────────────────────────────────────
# Parallel Render Pipeline
# ──────────────────────────────────────────────


def render_pool(
    scene: Scene,
    output_path: str,
    *,
    fps: int | None = None,
    crf: int = 20,
    workers: int | None = None,
    on_progress: ProgressCallback | None = None,
    use_shared_memory: bool = False,
) -> ExportResult:
    """Render ``scene`` to ``output_path`` (MP4) using a parallel worker pool.

    Pipeline:
        1. Compile the timeline + collect paintable graphics once.
        2. Build the shared :class:`RenderContext`.
        3. Open an :class:`FFmpegPipe` (auto-detect encoder).
        4. Allocate a :class:`SharedMemoryRing` (fallback to pickle on failure).
        5. ``Pool.imap`` distributes frame rendering across ``workers``.
        6. Stream frames to FFmpeg in order; fire ``on_progress`` per frame.

    Args:
        scene: The v2 :class:`~archmotion.core.scene.Scene`.
        output_path: Output ``.mp4`` file path.
        fps: Frame rate override (defaults to ``scene.fps``).
        crf: Constant-rate factor for the libx264 fallback encoder.
        workers: Explicit worker count (``None`` → auto-size).
        on_progress: Optional ``(completed, total)`` progress callback.
        use_shared_memory: Enable SharedMemory IPC (default; falls back on failure).

    Returns:
        :class:`ExportResult` with file path, frame count, and metadata.

    Raises:
        FFmpegNotFoundError: If FFmpeg cannot be found.
        FFmpegCrashError: If FFmpeg encoding fails.
    """
    from archmotion.core.vmobject import VMobject

    eff_fps = fps if fps is not None else scene.fps
    timeline = replace(scene.compile_timeline(), fps=eff_fps)
    graphics = tuple(g for g in scene.all_graphics() if isinstance(g, VMobject))
    width, height = scene.resolution
    bg = _background(scene)
    total_frames = max(1, timeline.total_frames)
    update_roots = tuple(scene.graphics)
    has_updaters = any(root.has_updaters for root in update_roots)

    ctx = RenderContext(
        graphics=graphics,
        timeline=timeline,
        camera=scene.camera,
        width=width,
        height=height,
        fps=eff_fps,
        background_rgba=bg,
        theme=scene.theme,
        update_roots=update_roots if has_updaters else (),
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    pipe = FFmpegPipe.open(
        output_path=out,
        width=width,
        height=height,
        fps=eff_fps,
        crf=crf,
    )

    worker_count = compute_worker_count(workers)
    if has_updaters and worker_count > 1:
        logger.warning(
            "Per-frame updaters require deterministic single-process rendering; using workers=1.",
        )
        worker_count = 1

    # SharedMemory output ring (zero-copy). Fall back to pickle on failure.
    ring: SharedMemoryRing | None = None
    frame_size = width * height * 4
    if use_shared_memory and worker_count > 1:
        try:
            ring = SharedMemoryRing(
                frame_size=frame_size,
                num_slots=min(worker_count + 1, _DEFAULT_RING_SIZE),
            )
        except OSError:
            logger.warning(
                "SharedMemory allocation failed — falling back to pickle IPC.",
            )
            ring = None

    ipc_mode = "shm" if ring is not None else "pickle"
    frames_written = 0

    try:
        if worker_count == 1:
            # Avoid multiprocessing entirely. This is also the default Windows
            # path, so ordinary user scripts do not recursively spawn.
            _init_worker(ctx)
            for frame_index in range(total_frames):
                pipe.write_frame(_render_index(frame_index))
                frames_written += 1
                if on_progress is not None:
                    on_progress(frames_written, total_frames)
        elif ring is not None:
            # ── SharedMemory pipeline ──
            with mp.Pool(
                processes=worker_count,
                initializer=_init_worker,
                initargs=(ctx,),
            ) as pool:
                # A slot cannot be reused until the main process has consumed
                # it. Dispatch one ring-sized batch at a time to make that
                # ownership explicit and eliminate overwrite races.
                for batch_start in range(0, total_frames, ring.num_slots):
                    batch_end = min(total_frames, batch_start + ring.num_slots)
                    tasks = list(iter_shm_slots(batch_end, ring))[batch_start:batch_end]
                    for frame_index in pool.imap(_render_index_to_shm, tasks):
                        frame_bytes = ring.read_slot(frame_index)
                        pipe.write_frame(frame_bytes)
                        frames_written += 1
                        if on_progress is not None:
                            on_progress(frames_written, total_frames)
        else:
            # ── Pickle fallback pipeline ──
            frame_indices = range(total_frames)
            with mp.Pool(
                processes=worker_count,
                initializer=_init_worker,
                initargs=(ctx,),
            ) as pool:
                for frame_bytes in pool.imap(_render_index, frame_indices):
                    pipe.write_frame(frame_bytes)
                    frames_written += 1
                    if on_progress is not None:
                        on_progress(frames_written, total_frames)

        pipe.close()
    except Exception:
        pipe.kill()
        raise
    finally:
        if ring is not None:
            ring.close()

    file_size = out.stat().st_size if out.exists() else 0

    return ExportResult(
        output_path=out,
        total_frames=frames_written,
        encoder_label=pipe.encoder.label,
        file_size_bytes=file_size,
        workers=worker_count,
        ipc_mode=ipc_mode,
    )


def _background(scene: Scene) -> tuple[float, float, float, float]:
    """Resolve the scene background colour as an RGBA float tuple in [0, 1]."""
    from archmotion.render.path_render import DEFAULT_BACKGROUND_RGBA

    theme = getattr(scene, "theme", None)
    rgba = getattr(theme, "background_rgba", None) if theme is not None else None
    if rgba is not None:
        return tuple(rgba)
    return DEFAULT_BACKGROUND_RGBA


# Forward reference for type checking only — avoids a circular import.
if TYPE_CHECKING:
    from archmotion.core.scene import Scene
