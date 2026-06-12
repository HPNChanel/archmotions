"""Unit tests for Manhattan routing algorithm."""

from __future__ import annotations

from archmotion.layout.bbox import BoundingBox
from archmotion.layout.router import manhattan_route


class TestManhattanRoute:
    """Tests for Lean Manhattan routing."""

    def _make_bbox(self, x: float, y: float, w: float = 100, h: float = 50) -> BoundingBox:
        return BoundingBox(x=x, y=y, width=w, height=h)

    def test_same_row_horizontal_line(self):
        """Nodes on same row → straight horizontal I-shape."""
        src = self._make_bbox(0, 0)
        tgt = self._make_bbox(300, 0)
        path = manhattan_route(src, tgt)
        assert len(path) == 2  # Straight line, no bend
        assert path[0] == src.right_anchor
        assert path[1] == tgt.left_anchor

    def test_same_column_vertical_line(self):
        """Nodes on same column → straight vertical I-shape."""
        src = self._make_bbox(0, 0)
        tgt = self._make_bbox(0, 200)
        path = manhattan_route(src, tgt)
        assert len(path) == 2
        assert path[0] == src.bottom_anchor
        assert path[1] == tgt.top_anchor

    def test_diagonal_l_shape(self):
        """Nodes diagonal → L-shape with 1 bend point."""
        src = self._make_bbox(0, 0)
        tgt = self._make_bbox(300, 200)
        path = manhattan_route(src, tgt)
        assert len(path) == 3  # src_anchor, bend, tgt_anchor

    def test_waypoints_override(self):
        """User waypoints bypass auto-routing."""
        src = self._make_bbox(0, 0)
        tgt = self._make_bbox(300, 200)
        wp = [(150.0, 0.0), (150.0, 200.0)]
        path = manhattan_route(src, tgt, waypoints=wp)
        # Should include: src_anchor + 2 waypoints + tgt_anchor = 4 points
        assert len(path) == 4

    def test_target_left_of_source(self):
        """Target to the left → uses left/right anchors correctly."""
        src = self._make_bbox(300, 0)
        tgt = self._make_bbox(0, 0)
        path = manhattan_route(src, tgt)
        assert path[0] == src.left_anchor
        assert path[-1] == tgt.right_anchor
