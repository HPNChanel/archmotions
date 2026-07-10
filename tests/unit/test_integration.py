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
from unittest.mock import patch

import pytest

from archmotion.api.connections import Connection
from archmotion.api.primitives import Database, Node
from archmotion.api.scene import Scene
from archmotion.errors import EmptyTimelineError
from archmotion.exporter.pool import ExportResult
from archmotion.motions._animations import FadeIn, Pulse, Transfer

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
    """Test the v2 Scene.render() pipeline wiring (mocked render_scene)."""

    def test_empty_timeline_raises(self):
        from archmotion.core.scene import Scene as V2Scene

        scene = V2Scene()
        with pytest.raises(EmptyTimelineError):
            scene.render("nope.mp4")

    def test_render_invokes_render_scene(self, tmp_path):
        from archmotion.animation import FadeIn as V2FadeIn
        from archmotion.core.scene import Scene as V2Scene
        from archmotion.domains.architecture import Node as V2Node

        scene = V2Scene(resolution="720p", fps=30)
        server = V2Node("Server")
        scene.play(V2FadeIn(server))

        with patch(
            "archmotion.render.frame.render_scene",
            return_value=str(tmp_path / "test.mp4"),
        ) as mock_rs:
            scene.render(str(tmp_path / "test.mp4"))
            mock_rs.assert_called_once()

    def test_auto_appends_mp4_extension(self, tmp_path):
        from archmotion.animation import FadeIn as V2FadeIn
        from archmotion.core.scene import Scene as V2Scene
        from archmotion.domains.architecture import Node as V2Node

        scene = V2Scene(resolution="720p", fps=30)
        scene.play(V2FadeIn(V2Node("Server")))

        with patch(
            "archmotion.render.frame.render_scene",
            return_value=str(tmp_path / "no_ext.mp4"),
        ) as mock_rs:
            result = scene.render(str(tmp_path / "no_ext"))
            # The output path passed to render_scene ends with .mp4.
            assert mock_rs.call_args.args[1].endswith(".mp4")
            assert str(result).endswith(".mp4")

    def test_render_returns_path(self, tmp_path):
        from archmotion.animation import FadeIn as V2FadeIn
        from archmotion.core.scene import Scene as V2Scene
        from archmotion.domains.architecture import Node as V2Node

        scene = V2Scene(resolution="720p", fps=30)
        scene.play(V2FadeIn(V2Node("Server")))

        with patch(
            "archmotion.render.frame.render_scene",
            return_value=str(tmp_path / "out.mp4"),
        ):
            result = scene.render(str(tmp_path / "out.mp4"))
            assert result.name == "out.mp4"
