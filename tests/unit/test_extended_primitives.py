"""Unit tests for PLAN-007 -- Extended Primitives (Cloud, Queue, Cache, User).

Tests cover:
    - Class construction + PrimitiveType verification
    - Fluent positioning API inheritance (.right_of, .below, etc.)
    - Cloud.provider field
    - Painter smoke tests (no crash rendering)
    - Painter with opacity and glow
    - render_frame() dispatch table routing
    - Backward compatibility (Node/Database still work)
"""

from __future__ import annotations

import pytest

from archmotion._types import PrimitiveType
from archmotion.api.primitives import Cache, Cloud, Database, Node, Queue, User
from archmotion.layout.bbox import BoundingBox
from archmotion.renderer.canvas import SkiaCanvas
from archmotion.renderer.frame import FrameSpec, render_frame
from archmotion.renderer.painters import (
    paint_cache,
    paint_cloud,
    paint_queue,
    paint_user,
)
from archmotion.renderer.theme import ThemeConfig


# ──────────────────────────────────────────────
# Class Construction + PrimitiveType
# ──────────────────────────────────────────────


class TestCloudPrimitive:
    """Test Cloud class construction and attributes."""

    def test_primitive_type(self):
        cloud = Cloud("AWS S3")
        assert cloud.primitive_type == PrimitiveType.CLOUD

    def test_inherits_node(self):
        cloud = Cloud("CloudFront")
        assert isinstance(cloud, Node)

    def test_provider_default_none(self):
        cloud = Cloud("Lambda")
        assert cloud.provider is None

    def test_provider_explicit(self):
        cloud = Cloud("S3 Bucket", provider="aws")
        assert cloud.provider == "aws"

    def test_label_validation(self):
        with pytest.raises(ValueError):
            Cloud("")


class TestQueuePrimitive:
    """Test Queue class construction."""

    def test_primitive_type(self):
        queue = Queue("Kafka")
        assert queue.primitive_type == PrimitiveType.QUEUE

    def test_inherits_node(self):
        queue = Queue("RabbitMQ")
        assert isinstance(queue, Node)

    def test_label_validation(self):
        with pytest.raises(ValueError):
            Queue("   ")


class TestCachePrimitive:
    """Test Cache class construction."""

    def test_primitive_type(self):
        cache = Cache("Redis")
        assert cache.primitive_type == PrimitiveType.CACHE

    def test_inherits_node(self):
        cache = Cache("Memcached")
        assert isinstance(cache, Node)


class TestUserPrimitive:
    """Test User class construction."""

    def test_primitive_type(self):
        user = User("Client")
        assert user.primitive_type == PrimitiveType.USER

    def test_inherits_node(self):
        user = User("Admin")
        assert isinstance(user, Node)


# ──────────────────────────────────────────────
# Positioning API Inheritance
# ──────────────────────────────────────────────


class TestPositioningInheritance:
    """Verify all new primitives inherit fluent positioning from Node."""

    def test_cloud_right_of(self):
        api = Node("API")
        s3 = Cloud("S3").right_of(api, distance=3)
        assert s3.position is not None
        assert s3.position.anchor_id == api.id

    def test_queue_below(self):
        api = Node("API")
        kafka = Queue("Kafka").below(api, distance=2)
        assert kafka.position is not None

    def test_cache_left_of(self):
        api = Node("API")
        redis = Cache("Redis").left_of(api)
        assert redis.position is not None

    def test_user_above(self):
        api = Node("API")
        client = User("Client").above(api)
        assert client.position is not None


# ──────────────────────────────────────────────
# Painter Smoke Tests
# ──────────────────────────────────────────────


class TestPainterSmoke:
    """Smoke tests: each painter renders without crashing."""

    @pytest.fixture()
    def canvas_and_theme(self):
        canvas = SkiaCanvas(200, 200)
        theme = ThemeConfig()
        yield canvas, theme
        canvas.dispose()

    @pytest.fixture()
    def bbox(self):
        return BoundingBox(x=20, y=20, width=120, height=60)

    def test_paint_cloud_no_crash(self, canvas_and_theme, bbox):
        canvas, theme = canvas_and_theme
        paint_cloud(canvas, bbox, "AWS S3", theme)

    def test_paint_queue_no_crash(self, canvas_and_theme, bbox):
        canvas, theme = canvas_and_theme
        paint_queue(canvas, bbox, "Kafka", theme)

    def test_paint_cache_no_crash(self, canvas_and_theme, bbox):
        canvas, theme = canvas_and_theme
        paint_cache(canvas, bbox, "Redis", theme)

    def test_paint_user_no_crash(self, canvas_and_theme, bbox):
        canvas, theme = canvas_and_theme
        paint_user(canvas, bbox, "Client", theme)

    def test_paint_cloud_with_opacity(self, canvas_and_theme, bbox):
        canvas, theme = canvas_and_theme
        paint_cloud(canvas, bbox, "CDN", theme, opacity=0.5)

    def test_paint_queue_with_glow(self, canvas_and_theme, bbox):
        canvas, theme = canvas_and_theme
        paint_queue(canvas, bbox, "SQS", theme, glow_intensity=0.7)

    def test_paint_cache_with_opacity(self, canvas_and_theme, bbox):
        canvas, theme = canvas_and_theme
        paint_cache(canvas, bbox, "Memcached", theme, opacity=0.3)

    def test_paint_user_with_glow(self, canvas_and_theme, bbox):
        canvas, theme = canvas_and_theme
        paint_user(canvas, bbox, "Admin", theme, glow_intensity=0.5)


# ──────────────────────────────────────────────
# Render Dispatch (render_frame routes to correct painter)
# ──────────────────────────────────────────────


class TestRenderDispatch:
    """Verify render_frame() dispatches to the correct painter for each type."""

    def _make_spec(self, node_type: PrimitiveType) -> FrameSpec:
        return FrameSpec(
            frame_index=0,
            width=200,
            height=200,
            fps=30,
            theme=ThemeConfig(),
            node_boxes={"n1": BoundingBox(20, 20, 120, 60)},
            node_labels={"n1": "Test"},
            node_types={"n1": node_type},
            connection_routes={},
            connection_labels={},
            compiled_actions=(),
            transfer_metas=(),
        )

    def test_dispatch_cloud(self):
        result = render_frame(self._make_spec(PrimitiveType.CLOUD))
        assert len(result) == 200 * 200 * 4

    def test_dispatch_queue(self):
        result = render_frame(self._make_spec(PrimitiveType.QUEUE))
        assert len(result) == 200 * 200 * 4

    def test_dispatch_cache(self):
        result = render_frame(self._make_spec(PrimitiveType.CACHE))
        assert len(result) == 200 * 200 * 4

    def test_dispatch_user(self):
        result = render_frame(self._make_spec(PrimitiveType.USER))
        assert len(result) == 200 * 200 * 4


# ──────────────────────────────────────────────
# Backward Compatibility
# ──────────────────────────────────────────────


class TestBackwardCompatibility:
    """Verify existing Node/Database still work after adding new types."""

    def test_node_still_works(self):
        node = Node("Server")
        assert node.primitive_type == PrimitiveType.NODE

    def test_database_still_works(self):
        db = Database("PostgreSQL")
        assert db.primitive_type == PrimitiveType.DATABASE

    def test_render_node_unchanged(self):
        spec = FrameSpec(
            frame_index=0, width=100, height=100, fps=30,
            theme=ThemeConfig(),
            node_boxes={"n1": BoundingBox(10, 10, 80, 40)},
            node_labels={"n1": "API"}, node_types={"n1": PrimitiveType.NODE},
            connection_routes={}, connection_labels={},
            compiled_actions=(), transfer_metas=(),
        )
        result = render_frame(spec)
        assert len(result) == 100 * 100 * 4

    def test_render_database_unchanged(self):
        spec = FrameSpec(
            frame_index=0, width=100, height=100, fps=30,
            theme=ThemeConfig(),
            node_boxes={"db1": BoundingBox(10, 10, 80, 40)},
            node_labels={"db1": "PG"}, node_types={"db1": PrimitiveType.DATABASE},
            connection_routes={}, connection_labels={},
            compiled_actions=(), transfer_metas=(),
        )
        result = render_frame(spec)
        assert len(result) == 100 * 100 * 4
