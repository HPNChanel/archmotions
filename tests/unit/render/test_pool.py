"""Tests for the parallel render pool orchestrator (render/pool.py).

Pure-logic tests (worker sizing) run unconditionally. Integration tests that
exercise real rendering are gated on skia + ffmpeg availability.
"""

from __future__ import annotations

import multiprocessing as mp
import sys

import pytest

from archmotion.render.pool import compute_worker_count

skia = pytest.importorskip("skia", reason="skia-python not installed")


def _tiny_scene():
    """A minimal 3-frame scene for integration smoke tests."""
    from archmotion.animation import FadeIn
    from archmotion.core.scene import Scene
    from archmotion.domains.architecture import Node

    scene = Scene(resolution=(120, 90), fps=10)
    node = Node("A", center=(60.0, 45.0))
    scene.add(node)
    scene.play(FadeIn(node, run_time=0.3))
    return scene


class TestComputeWorkerCount:
    def test_explicit_override(self):
        assert compute_worker_count(4) == 4

    def test_minimum_one(self):
        assert compute_worker_count(0) == 1

    def test_auto_sized(self):
        workers = compute_worker_count(None)
        cpu = mp.cpu_count() or 4
        expected = 1 if sys.platform == "win32" else max(1, min(int(cpu * 0.75), 14))
        assert workers == expected


class TestRenderPoolIntegration:
    """Real end-to-end MP4 rendering (skia + ffmpeg required)."""

    def test_shm_mode_produces_mp4(self, tmp_path):
        from archmotion.render.pool import render_pool

        scene = _tiny_scene()
        out = tmp_path / "shm.mp4"
        result = render_pool(scene, str(out), workers=2)
        assert out.exists()
        assert out.stat().st_size > 0
        assert result.total_frames >= 1
        assert result.output_path == out

    def test_pickle_fallback_mode(self, tmp_path):
        from archmotion.render.pool import render_pool

        scene = _tiny_scene()
        out = tmp_path / "pickle.mp4"
        result = render_pool(scene, str(out), workers=2, use_shared_memory=False)
        assert out.exists()
        assert result.ipc_mode == "pickle"

    def test_single_worker(self, tmp_path):
        from archmotion.render.pool import render_pool

        scene = _tiny_scene()
        out = tmp_path / "single.mp4"
        result = render_pool(scene, str(out), workers=1)
        assert out.exists()
        assert result.workers == 1

    def test_progress_callback_fires(self, tmp_path):
        from archmotion.render.pool import render_pool

        scene = _tiny_scene()
        out = tmp_path / "progress.mp4"
        seen: list[tuple[int, int]] = []
        result = render_pool(
            scene, str(out), workers=2, on_progress=lambda c, t: seen.append((c, t))
        )
        assert len(seen) == result.total_frames
        # Last callback reports completion.
        assert seen[-1][0] == result.total_frames
        assert seen[-1][1] == result.total_frames
