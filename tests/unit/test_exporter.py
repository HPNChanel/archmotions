"""Unit tests for Phase 4b -- Exporter (FFmpeg + Pool).

Tests cover:
    - FFmpeg binary resolution (get_ffmpeg_path)
    - Encoder detection (detect_encoder)
    - Worker count calculation (compute_worker_count)
    - FrameSpec factory (build_frame_specs)
    - FFmpegPipe lifecycle (open/write/close)
    - ExportResult data structure
    - export_video integration (with tiny 2-frame render)
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from archmotion._types import PrimitiveType
from archmotion.constants import MAX_WORKERS
from archmotion.exporter.ffmpeg import (
    LIBX264_CONFIG,
    NVENC_CONFIG,
    FFmpegPipe,
    detect_encoder,
    get_ffmpeg_path,
)
from archmotion.exporter.pool import (
    ExportResult,
    build_frame_specs,
    compute_worker_count,
    export_video,
)
from archmotion.layout.bbox import BoundingBox
from archmotion.layout.resolver import ResolvedLayout
from archmotion.renderer.theme import ThemeConfig
from archmotion.timeline.actions import ScheduledAction
from archmotion._types import AnimatableProperty
from archmotion.timeline.compiler import CompiledTimeline


# ──────────────────────────────────────────────
# FFmpeg Path Resolution
# ──────────────────────────────────────────────


class TestGetFFmpegPath:
    """Test 3-tier FFmpeg binary resolution."""

    def test_finds_ffmpeg_on_system(self):
        """FFmpeg should be available on CI or dev machines."""
        path = get_ffmpeg_path()
        assert path is not None
        assert len(path) > 0

    def test_env_variable_override(self, tmp_path):
        """FFMPEG_BINARY env var should take priority."""
        # Create a fake executable
        fake_exe = tmp_path / "ffmpeg_test.exe"
        fake_exe.write_text("fake")

        with patch.dict(os.environ, {"FFMPEG_BINARY": str(fake_exe)}):
            result = get_ffmpeg_path()
            assert result == str(fake_exe)


# ──────────────────────────────────────────────
# Encoder Detection
# ──────────────────────────────────────────────


class TestDetectEncoder:
    """Test NVENC/libx264 auto-detection."""

    def test_returns_encoder_config(self):
        """Should return a valid EncoderConfig."""
        ffmpeg_path = get_ffmpeg_path()
        config = detect_encoder(ffmpeg_path)
        assert config.name in ("h264_nvenc", "libx264")
        assert len(config.options) > 0

    def test_fallback_on_invalid_path(self):
        """Invalid FFmpeg path should fallback to libx264."""
        config = detect_encoder("/nonexistent/ffmpeg")
        assert config == LIBX264_CONFIG


# ──────────────────────────────────────────────
# Worker Count
# ──────────────────────────────────────────────


class TestComputeWorkerCount:
    """Test worker count calculation."""

    def test_returns_positive_integer(self):
        count = compute_worker_count()
        assert count >= 1
        assert count <= MAX_WORKERS

    def test_respects_max_workers_cap(self):
        """Even with 100 cores, should not exceed MAX_WORKERS."""
        with patch("archmotion.exporter.pool.mp.cpu_count", return_value=100):
            count = compute_worker_count()
            assert count <= MAX_WORKERS

    def test_handles_none_cpu_count(self):
        """If cpu_count returns None, should use fallback."""
        with patch("archmotion.exporter.pool.mp.cpu_count", return_value=None):
            count = compute_worker_count()
            assert count >= 1


# ──────────────────────────────────────────────
# FrameSpec Factory
# ──────────────────────────────────────────────


class TestBuildFrameSpecs:
    """Test FrameSpec list construction."""

    def _make_timeline(self, total_frames: int = 10, fps: int = 60) -> CompiledTimeline:
        return CompiledTimeline(
            actions=(),
            total_duration=total_frames / fps,
            total_frames=total_frames,
            fps=fps,
            transfer_metas=(),
        )

    def _make_layout(self) -> ResolvedLayout:
        return ResolvedLayout(
            node_boxes={"n1": BoundingBox(100, 100, 150, 50)},
            connection_routes={},
            canvas_width=400,
            canvas_height=300,
        )

    def test_correct_count(self):
        timeline = self._make_timeline(total_frames=10)
        layout = self._make_layout()
        specs = build_frame_specs(
            timeline, layout, ThemeConfig(),
            {"n1": "Server"}, {"n1": PrimitiveType.NODE}, {},
        )
        assert len(specs) == 10

    def test_frame_index_sequential(self):
        timeline = self._make_timeline(total_frames=5)
        layout = self._make_layout()
        specs = build_frame_specs(
            timeline, layout, ThemeConfig(),
            {"n1": "S"}, {"n1": PrimitiveType.NODE}, {},
        )
        for i, spec in enumerate(specs):
            assert spec.frame_index == i

    def test_specs_contain_node_data(self):
        timeline = self._make_timeline(total_frames=1)
        layout = self._make_layout()
        specs = build_frame_specs(
            timeline, layout, ThemeConfig(),
            {"n1": "API"}, {"n1": PrimitiveType.NODE}, {},
        )
        assert "n1" in specs[0].node_boxes
        assert specs[0].node_labels["n1"] == "API"


# ──────────────────────────────────────────────
# FFmpegPipe Lifecycle
# ──────────────────────────────────────────────


class TestFFmpegPipe:
    """Test FFmpegPipe open/write/close lifecycle."""

    def test_open_and_close(self, tmp_path):
        """FFmpegPipe should open and close without error."""
        output = tmp_path / "test_open.mp4"
        pipe = FFmpegPipe.open(
            output_path=output,
            width=100,
            height=100,
            fps=30,
            encoder=LIBX264_CONFIG,  # Force CPU encoder for test reliability
        )
        # Write one tiny frame (black)
        pipe.write_frame(b"\x00" * (100 * 100 * 4))
        pipe.close()

        assert output.exists()
        assert output.stat().st_size > 0

    def test_encoder_property(self, tmp_path):
        output = tmp_path / "test_enc.mp4"
        pipe = FFmpegPipe.open(
            output_path=output, width=100, height=100, fps=30,
            encoder=LIBX264_CONFIG,
        )
        assert pipe.encoder.name == "libx264"
        pipe.write_frame(b"\x00" * (100 * 100 * 4))
        pipe.close()


# ──────────────────────────────────────────────
# Integration: export_video (tiny render)
# ──────────────────────────────────────────────


class TestExportVideo:
    """Integration test: render 2 frames and export to MP4."""

    def test_tiny_export(self, tmp_path):
        """Render 2 frames (100x100) with a single node."""
        output = tmp_path / "tiny_export.mp4"

        bbox = BoundingBox(x=10, y=10, width=80, height=30)
        layout = ResolvedLayout(
            node_boxes={"n1": bbox},
            connection_routes={},
            canvas_width=100,
            canvas_height=100,
        )

        action = ScheduledAction(
            target_id="n1",
            prop=AnimatableProperty.OPACITY,
            start_time=0.0,
            end_time=1.0,
            start_value=0.0,
            end_value=1.0,
        )

        timeline = CompiledTimeline(
            actions=(action,),
            total_duration=2 / 30,  # 2 frames at 30fps
            total_frames=2,
            fps=30,
        )

        progress_calls: list[tuple[int, int]] = []

        def on_progress(done: int, total: int) -> None:
            progress_calls.append((done, total))

        result = export_video(
            timeline=timeline,
            layout=layout,
            theme=ThemeConfig(),
            node_labels={"n1": "Test"},
            node_types={"n1": PrimitiveType.NODE},
            connection_labels={},
            output_path=output,
            on_progress=on_progress,
            encoder_override=LIBX264_CONFIG,  # Force CPU for test reliability
        )

        # Verify result
        assert isinstance(result, ExportResult)
        assert result.total_frames == 2
        assert result.output_path == output
        assert result.file_size_bytes > 0
        assert output.exists()

        # Progress callback fired for each frame
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2)
        assert progress_calls[1] == (2, 2)
