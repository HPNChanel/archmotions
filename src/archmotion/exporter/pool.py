"""Multiprocessing pool orchestration for parallel frame rendering.

Architectural Note:
    This module manages the Pool.imap() → FFmpegPipe.write_frame() pipeline.
    Frames are rendered in parallel by worker processes, then streamed to
    FFmpeg in sequential order (imap preserves order).

    v0.2.0 SharedMemory IPC:
        Workers write rendered RGBA bytes directly into pre-allocated
        SharedMemory ring buffer slots (zero-copy, zero-serialization).
        Main process reads from shared memory and pipes to FFmpeg.
        Falls back to standard pickle IPC if SharedMemory allocation fails.

    Zero-Disk I/O: Raw RGBA bytes flow from workers → shared memory → FFmpeg stdin.
    No temporary files are ever written to disk.

    Worker Sizing:
        workers = min(cpu_count * WORKER_RATIO, MAX_WORKERS)
        This leaves headroom for the OS, FFmpeg encoding, and the main process.
"""

from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from archmotion._types import PrimitiveType, Point
from archmotion.constants import MAX_WORKERS, WORKER_RATIO
from archmotion.exporter.ffmpeg import FFmpegPipe
from archmotion.exporter.shm import (
    SharedMemoryRing,
    _DEFAULT_RING_SIZE,
    iter_shm_render_args,
    render_frame_to_shm,
)
from archmotion.layout.resolver import ResolvedLayout
from archmotion.renderer.frame import FrameSpec, render_frame
from archmotion.renderer.theme import ThemeConfig
from archmotion.timeline.compiler import CompiledTimeline


# ──────────────────────────────────────────────
# Render Progress Callback
# ──────────────────────────────────────────────

ProgressCallback = Callable[[int, int], None]
"""Callback signature: (frames_completed, total_frames) -> None."""


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
    """

    output_path: Path
    total_frames: int
    encoder_label: str
    file_size_bytes: int


# ──────────────────────────────────────────────
# Worker Count
# ──────────────────────────────────────────────


def compute_worker_count() -> int:
    """Calculate the optimal number of worker processes.

    Formula: min(cpu_count * WORKER_RATIO, MAX_WORKERS), minimum 1.

    Returns:
        Number of worker processes to use.
    """
    cpu_count = mp.cpu_count() or 4
    return max(1, min(int(cpu_count * WORKER_RATIO), MAX_WORKERS))


# ──────────────────────────────────────────────
# Frame Spec Factory
# ──────────────────────────────────────────────


def build_frame_specs(
    timeline: CompiledTimeline,
    layout: ResolvedLayout,
    theme: ThemeConfig,
    node_labels: dict[str, str],
    node_types: dict[str, PrimitiveType],
    connection_labels: dict[str, str | None],
) -> list[FrameSpec]:
    """Build the list of FrameSpecs for all frames in the timeline.

    Each FrameSpec is a self-contained, picklable data object that
    a worker process can render independently.

    Args:
        timeline: Compiled timeline with actions and metas.
        layout: Resolved layout with bounding boxes and routes.
        theme: Visual theme configuration.
        node_labels: Mapping from node_id -> label text.
        node_types: Mapping from node_id -> PrimitiveType.
        connection_labels: Mapping from conn_id -> label text or None.

    Returns:
        List of FrameSpec objects, one per frame.
    """
    specs: list[FrameSpec] = []

    for frame_index in range(timeline.total_frames):
        spec = FrameSpec(
            frame_index=frame_index,
            width=layout.canvas_width,
            height=layout.canvas_height,
            fps=timeline.fps,
            theme=theme,
            node_boxes=layout.node_boxes,
            node_labels=node_labels,
            node_types=node_types,
            connection_routes=layout.connection_routes,
            connection_labels=connection_labels,
            compiled_actions=timeline.actions,
            transfer_metas=timeline.transfer_metas,
        )
        specs.append(spec)

    return specs


# ──────────────────────────────────────────────
# Export Pipeline
# ──────────────────────────────────────────────


def export_video(
    timeline: CompiledTimeline,
    layout: ResolvedLayout,
    theme: ThemeConfig,
    node_labels: dict[str, str],
    node_types: dict[str, PrimitiveType],
    connection_labels: dict[str, str | None],
    output_path: Path,
    on_progress: ProgressCallback | None = None,
    ffmpeg_path: str | None = None,
    encoder_override: object | None = None,
    use_shared_memory: bool = True,
) -> ExportResult:
    """Execute the full render + export pipeline.

    Pipeline (SharedMemory mode):
        1. Build FrameSpecs for all frames
        2. Allocate SharedMemory ring buffer (4 slots × frame_size)
        3. Open FFmpegPipe (auto-detect encoder)
        4. Create multiprocessing Pool
        5. Pool.imap(render_frame_to_shm, args) → write to ring slot
        6. Main process reads slot → pipe to FFmpeg
        7. Close ring buffer and FFmpeg pipe

    Fallback (Pickle mode):
        If SharedMemory allocation fails or ``use_shared_memory=False``,
        falls back to standard Pool.imap(render_frame) → bytes → FFmpeg.

    Args:
        timeline: Compiled timeline from Phase 3.
        layout: Resolved layout from Phase 2.
        theme: Visual theme config.
        node_labels: Node ID → label text mapping.
        node_types: Node ID → PrimitiveType mapping.
        connection_labels: Connection ID → label text mapping.
        output_path: Output .mp4 file path.
        on_progress: Optional callback for progress reporting.
        ffmpeg_path: FFmpeg binary path (auto-detected if None).
        encoder_override: Force a specific EncoderConfig (auto-detected if None).
        use_shared_memory: Enable SharedMemory IPC (default True, fallback on failure).

    Returns:
        ExportResult with file path, frame count, and metadata.

    Raises:
        FFmpegNotFoundError: If FFmpeg cannot be found.
        FFmpegCrashError: If FFmpeg encoding fails.
        RenderError: If frame rendering fails.
    """
    # 1. Build frame specs
    specs = build_frame_specs(
        timeline=timeline,
        layout=layout,
        theme=theme,
        node_labels=node_labels,
        node_types=node_types,
        connection_labels=connection_labels,
    )

    total_frames = len(specs)

    # 2. Open FFmpeg pipe
    pipe = FFmpegPipe.open(
        output_path=output_path,
        width=layout.canvas_width,
        height=layout.canvas_height,
        fps=timeline.fps,
        ffmpeg_path=ffmpeg_path,
        encoder=encoder_override,  # type: ignore[arg-type]
    )

    # 3. Determine worker count
    worker_count = compute_worker_count()

    # 4. Choose IPC strategy
    frame_size = layout.canvas_width * layout.canvas_height * 4
    ring: SharedMemoryRing | None = None

    if use_shared_memory:
        try:
            ring = SharedMemoryRing(
                frame_size=frame_size,
                num_slots=min(worker_count + 1, _DEFAULT_RING_SIZE),
            )
        except OSError:
            # SharedMemory allocation failed — fallback to pickle
            ring = None

    try:
        frames_written = 0

        if ring is not None:
            # ── SharedMemory Pipeline ──
            shm_args = list(iter_shm_render_args(specs, ring))

            with mp.Pool(processes=worker_count) as pool:
                for frame_index in pool.imap(render_frame_to_shm, shm_args):
                    # Read frame from shared memory (zero-copy read)
                    frame_bytes = ring.read_slot(frame_index)
                    pipe.write_frame(frame_bytes)
                    frames_written += 1

                    if on_progress is not None:
                        on_progress(frames_written, total_frames)
        else:
            # ── Pickle Fallback Pipeline ──
            with mp.Pool(processes=worker_count) as pool:
                for frame_bytes in pool.imap(render_frame, specs):
                    pipe.write_frame(frame_bytes)
                    frames_written += 1

                    if on_progress is not None:
                        on_progress(frames_written, total_frames)

        # 6. Finalize FFmpeg
        pipe.close()

    except Exception:
        pipe.kill()
        raise
    finally:
        # 7. Always clean up shared memory
        if ring is not None:
            ring.close()

    # Build result
    file_size = output_path.stat().st_size if output_path.exists() else 0

    return ExportResult(
        output_path=output_path,
        total_frames=frames_written,
        encoder_label=pipe.encoder.label,
        file_size_bytes=file_size,
    )

