"""Integration tests for the v2 Scene pipeline.

Tests cover:
    - Topology auto-registration via play() (targets + deduplication)
    - Scene.render() pipeline wiring (mocked render_scene for speed)
    - Empty timeline raises EmptyTimelineError
    - .mp4 extension auto-append

Note:
    Real FFmpeg encoding is exercised by the MP4 render smoke test.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from archmotion.animation import FadeIn, Transfer
from archmotion.core.scene import Scene
from archmotion.domains.architecture import Connection, Database, Node
from archmotion.errors import EmptyTimelineError

# ──────────────────────────────────────────────
# Topology Discovery (v2: targets auto-register in play())
# ──────────────────────────────────────────────


class TestTopologyDiscovery:
    """Test that play() auto-registers targets in the scene graph."""

    def test_discovers_nodes_from_fadein(self):
        scene = Scene(resolution="720p", fps=30)
        server = Node("Server")
        db = Database("PostgreSQL")
        scene.play(FadeIn(server, db))

        ids = {g.id for g in scene.all_graphics()}
        assert server.id in ids
        assert db.id in ids

    def test_deduplicates_nodes(self):
        scene = Scene(resolution="720p", fps=30)
        server = Node("Server")
        scene.add(server)  # explicit
        scene.play(FadeIn(server))  # from animation (duplicate)

        count = sum(1 for g in scene.all_graphics() if g.id == server.id)
        assert count == 1


# ──────────────────────────────────────────────
# Scene.render() Pipeline Wiring
# ──────────────────────────────────────────────


def _make_scene() -> Scene:
    scene = Scene(resolution="720p", fps=30)
    server = Node("Server")
    scene.play(FadeIn(server))
    return scene


def _export_result(path) -> object:
    """Build a lightweight ExportResult-like object for mocking render_pool."""
    from pathlib import Path

    from archmotion.render.pool import ExportResult

    return ExportResult(
        output_path=Path(str(path)),
        total_frames=1,
        encoder_label="CPU (libx264)",
        file_size_bytes=0,
        workers=1,
        ipc_mode="pickle",
    )


class TestSceneRender:
    """Test the v2 Scene.render() pipeline wiring (mocked render_pool)."""

    def test_empty_timeline_raises(self):
        scene = Scene()
        with pytest.raises(EmptyTimelineError):
            scene.render("nope.mp4")

    def test_render_invokes_render_pool(self, tmp_path):
        scene = _make_scene()
        with patch(
            "archmotion.render.pool.render_pool",
            return_value=_export_result(tmp_path / "test.mp4"),
        ) as mock_rp:
            scene.render(str(tmp_path / "test.mp4"))
            mock_rp.assert_called_once()

    def test_workers_one_uses_single_process(self, tmp_path):
        """``workers=1`` routes through the single-process ``render_scene``."""
        scene = _make_scene()
        with patch(
            "archmotion.render.frame.render_scene",
            return_value=str(tmp_path / "single.mp4"),
        ) as mock_rs:
            scene.render(str(tmp_path / "single.mp4"), workers=1)
            mock_rs.assert_called_once()

    def test_auto_appends_mp4_extension(self, tmp_path):
        scene = _make_scene()
        with patch(
            "archmotion.render.pool.render_pool",
            return_value=_export_result(tmp_path / "no_ext.mp4"),
        ) as mock_rp:
            result = scene.render(str(tmp_path / "no_ext"))
            assert mock_rp.call_args.args[1].endswith(".mp4")
            assert str(result).endswith(".mp4")

    def test_render_returns_path(self, tmp_path):
        scene = _make_scene()
        with patch(
            "archmotion.render.pool.render_pool",
            return_value=_export_result(tmp_path / "out.mp4"),
        ):
            result = scene.render(str(tmp_path / "out.mp4"))
            assert result.name == "out.mp4"

    def test_transfer_registers_packet(self, tmp_path):
        """A Transfer auto-creates a Packet that is registered in the scene."""
        scene = Scene(resolution="720p", fps=30)
        a = Node("A")
        b = Node("B")
        conn = Connection(a, b)
        scene.add(a, b, conn)
        scene.play(FadeIn(a, b, conn))
        scene.play(Transfer(conn, payload="GET"))

        # The scene now contains the auto-created packet graphic.
        ids = {g.id for g in scene.all_graphics()}
        assert {a.id, b.id, conn.id}.issubset(ids)
        assert len(ids) >= 4  # + packet
