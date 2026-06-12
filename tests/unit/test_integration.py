"""Integration tests for PLAN-006 -- Scene.render() full pipeline.

Tests cover:
    - Scene._collect_topology() auto-discovery and deduplication
    - Scene.render() pipeline wiring (mocked export for speed)
    - Empty timeline raises EmptyTimelineError
    - Post-render blocks further play() calls
    - Progress callback integration
    - .mp4 extension auto-append

Note:
    Real FFmpeg encoding is tested in test_exporter.py (100x100 resolution).
    These tests verify Scene orchestrates the 4 phases correctly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from archmotion.api.connections import Connection
from archmotion.api.primitives import Database, Node
from archmotion.api.scene import Scene
from archmotion.errors import EmptyTimelineError, TimelineError
from archmotion.exporter.pool import ExportResult
from archmotion.motions._animations import FadeIn, FadeOut, Pulse, Transfer


# ──────────────────────────────────────────────
# Helper: Tiny Scene Factory
# ──────────────────────────────────────────────


def _make_tiny_scene() -> tuple[Scene, Node, Node, Connection]:
    """Create a minimal 2-node scene for testing."""
    scene = Scene(resolution="720p", fps=30)
    server = Node("Server")
    db = Database("PostgreSQL").right_of(server, distance=2)
    conn = Connection(server, db, label="SQL")
    return scene, server, db, conn


def _mock_export_result(output_path: Path) -> ExportResult:
    """Create a mock ExportResult for test assertions."""
    # Touch the file so exists() checks pass
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"\x00" * 100)
    return ExportResult(
        output_path=output_path,
        total_frames=3,
        encoder_label="mock-libx264",
        file_size_bytes=100,
    )


# ──────────────────────────────────────────────
# Topology Discovery
# ──────────────────────────────────────────────


class TestCollectTopology:
    """Test Scene._collect_topology() auto-discovery."""

    def test_discovers_nodes_from_fadein(self):
        scene, server, db, conn = _make_tiny_scene()
        scene.play(FadeIn(server))
        scene.play(FadeIn(db))

        nodes, connections = scene._collect_topology()
        node_ids = {n.id for n in nodes}
        assert server.id in node_ids
        assert db.id in node_ids

    def test_discovers_connections_from_transfer(self):
        scene, server, db, conn = _make_tiny_scene()
        scene.play(FadeIn(server, db))
        scene.play(Transfer(conn, payload="SELECT *"))

        nodes, connections = scene._collect_topology()
        conn_ids = {c.id for c in connections}
        assert conn.id in conn_ids
        # Transfer auto-registers source/target nodes
        node_ids = {n.id for n in nodes}
        assert server.id in node_ids
        assert db.id in node_ids

    def test_discovers_from_pulse(self):
        scene, server, db, conn = _make_tiny_scene()
        scene.play(FadeIn(server))
        scene.play(Pulse(server))

        nodes, _ = scene._collect_topology()
        assert any(n.id == server.id for n in nodes)

    def test_deduplicates_nodes(self):
        scene, server, db, conn = _make_tiny_scene()
        scene.add_node(server)  # Explicit
        scene.play(FadeIn(server))  # From animation (duplicate)
        scene.play(Transfer(conn))  # From transfer (also references server)

        nodes, _ = scene._collect_topology()
        server_count = sum(1 for n in nodes if n.id == server.id)
        assert server_count == 1

    def test_deduplicates_connections(self):
        scene, server, db, conn = _make_tiny_scene()
        scene.add_connection(conn)
        scene.play(Transfer(conn))

        _, connections = scene._collect_topology()
        conn_count = sum(1 for c in connections if c.id == conn.id)
        assert conn_count == 1


# ──────────────────────────────────────────────
# Scene.render() Pipeline Wiring
# ──────────────────────────────────────────────


class TestSceneRender:
    """Test Scene.render() orchestrates all 4 phases correctly."""

    def test_empty_timeline_raises(self):
        scene = Scene()
        with pytest.raises(EmptyTimelineError):
            scene.render("nope.mp4")

    def test_post_render_blocks_play(self, tmp_path):
        """After render(), play() should raise TimelineError."""
        scene, server, db, conn = _make_tiny_scene()
        scene.play(FadeIn(server, db))

        mock_result = _mock_export_result(tmp_path / "mock.mp4")

        with patch("archmotion.api.scene.export_video", return_value=mock_result):
            scene.render(str(tmp_path / "test.mp4"))

        with pytest.raises(TimelineError):
            scene.play(FadeIn(server))

    def test_render_calls_all_phases(self, tmp_path):
        """Verify render() invokes resolve_layout, compile_timeline, export_video."""
        scene, server, db, conn = _make_tiny_scene()
        scene.play(FadeIn(server, db))
        scene.play(Transfer(conn, payload="Q", duration=0.2))

        mock_result = _mock_export_result(tmp_path / "test.mp4")

        with patch("archmotion.api.scene.export_video", return_value=mock_result) as mock_export, \
             patch("archmotion.api.scene.resolve_layout") as mock_layout, \
             patch("archmotion.api.scene.compile_timeline") as mock_timeline:

            # Setup return values
            from archmotion.layout.resolver import ResolvedLayout
            from archmotion.timeline.compiler import CompiledTimeline

            mock_layout.return_value = ResolvedLayout(
                node_boxes={}, connection_routes={},
                canvas_width=1280, canvas_height=720,
            )
            mock_timeline.return_value = CompiledTimeline(
                actions=(), total_duration=1.0, total_frames=30, fps=30,
            )

            scene.render(str(tmp_path / "test.mp4"))

            # All 3 pipeline functions were called
            mock_layout.assert_called_once()
            mock_timeline.assert_called_once()
            mock_export.assert_called_once()

    def test_render_passes_correct_layout_args(self, tmp_path):
        """Verify render() passes canvas dimensions to resolve_layout."""
        scene, server, db, conn = _make_tiny_scene()
        scene.play(FadeIn(server, db))

        mock_result = _mock_export_result(tmp_path / "test.mp4")

        with patch("archmotion.api.scene.export_video", return_value=mock_result) as mock_export, \
             patch("archmotion.api.scene.resolve_layout") as mock_layout, \
             patch("archmotion.api.scene.compile_timeline") as mock_timeline:

            from archmotion.layout.resolver import ResolvedLayout
            from archmotion.timeline.compiler import CompiledTimeline

            mock_layout.return_value = ResolvedLayout(
                node_boxes={}, connection_routes={},
                canvas_width=1280, canvas_height=720,
            )
            mock_timeline.return_value = CompiledTimeline(
                actions=(), total_duration=0.5, total_frames=15, fps=30,
            )

            scene.render(str(tmp_path / "test.mp4"))

            # Check layout was called with correct canvas dimensions (720p)
            call_kwargs = mock_layout.call_args
            assert call_kwargs.kwargs["canvas_width"] == 1280
            assert call_kwargs.kwargs["canvas_height"] == 720

    def test_render_passes_progress_callback(self, tmp_path):
        """Verify on_progress is forwarded to export_video."""
        scene, server, db, conn = _make_tiny_scene()
        scene.play(FadeIn(server))

        mock_result = _mock_export_result(tmp_path / "test.mp4")
        callback = MagicMock()

        with patch("archmotion.api.scene.export_video", return_value=mock_result) as mock_export, \
             patch("archmotion.api.scene.resolve_layout") as mock_layout, \
             patch("archmotion.api.scene.compile_timeline") as mock_timeline:

            from archmotion.layout.resolver import ResolvedLayout
            from archmotion.timeline.compiler import CompiledTimeline

            mock_layout.return_value = ResolvedLayout(
                node_boxes={}, connection_routes={},
                canvas_width=1280, canvas_height=720,
            )
            mock_timeline.return_value = CompiledTimeline(
                actions=(), total_duration=0.5, total_frames=15, fps=30,
            )

            scene.render(str(tmp_path / "p.mp4"), on_progress=callback)

            # Verify on_progress was forwarded
            call_kwargs = mock_export.call_args
            assert call_kwargs.kwargs["on_progress"] is callback

    def test_auto_appends_mp4_extension(self, tmp_path):
        """Output file should auto-get .mp4 extension."""
        scene, server, db, conn = _make_tiny_scene()
        scene.play(FadeIn(server))

        mock_result = _mock_export_result(tmp_path / "no_ext.mp4")

        with patch("archmotion.api.scene.export_video", return_value=mock_result) as mock_export, \
             patch("archmotion.api.scene.resolve_layout") as mock_layout, \
             patch("archmotion.api.scene.compile_timeline") as mock_timeline:

            from archmotion.layout.resolver import ResolvedLayout
            from archmotion.timeline.compiler import CompiledTimeline

            mock_layout.return_value = ResolvedLayout(
                node_boxes={}, connection_routes={},
                canvas_width=1280, canvas_height=720,
            )
            mock_timeline.return_value = CompiledTimeline(
                actions=(), total_duration=0.5, total_frames=15, fps=30,
            )

            result = scene.render(str(tmp_path / "no_ext"))

            # The output_path passed to export_video should end with .mp4
            call_kwargs = mock_export.call_args
            assert str(call_kwargs.kwargs["output_path"]).endswith(".mp4")
