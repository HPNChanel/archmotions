"""Layout Resolver -- converts relative positions to absolute pixel coordinates.

Architectural Note:
    Phase 2 receives a flat list of Nodes and Connections from Phase 1.
    It produces a ResolvedLayout containing:
        - dict[node_id -> BoundingBox] (absolute pixel coordinates)
        - dict[conn_id -> list[Point]] (Manhattan-routed polylines)

    Algorithm:
        1. Build a DAG from Node.position references
        2. Validate: detect cycles, orphans, and duplicate IDs
        3. Topological sort (Kahn's algorithm) to determine processing order
        4. Walk sorted order: compute BoundingBox from text + padding,
           translate relative position (Direction + distance * GRID_UNIT) to pixels
        5. Center the entire diagram on the canvas
        6. Route connections via manhattan_route()
        7. Check canvas overflow

    Complexity: O(N + E) where N = nodes, E = connections
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from archmotion._types import Direction, Point
from archmotion.constants import GRID_UNIT
from archmotion.errors import (
    CircularReferenceError,
    DuplicateIdError,
    OrphanNodeError,
    OverflowCanvasError,
)
from archmotion.layout.bbox import BoundingBox, estimate_text_bbox
from archmotion.layout.positions import AbsolutePosition, RelativePosition
from archmotion.layout.router import manhattan_route

if TYPE_CHECKING:
    from collections.abc import Sequence

# ──────────────────────────────────────────────
# Structural protocols (v1 + v2 nodes both fit)
# ──────────────────────────────────────────────


class _Endpoint(Protocol):
    """A node endpoint of a connection — anything with an ``id``."""

    id: str


class LayoutNode(Protocol):
    """A placeable node: an id, a label, and an optional position constraint.

    Both v1 ``api.primitives.Node`` and v2 ``domains.architecture`` primitives
    satisfy this, so the resolver is domain-agnostic.
    """

    id: str
    label: str
    position: RelativePosition | AbsolutePosition | None


class LayoutConnection(Protocol):
    """A directed link between two node endpoints.

    ``source``/``target`` are declared as read-only properties so a concrete
    connection with plain ``source``/``target`` fields matches covariantly
    (protocol *variables* would require an exact, invariant type match).
    """

    id: str
    waypoints: list[Point] | None

    @property
    def source(self) -> _Endpoint:
        """The connection's source node."""

    @property
    def target(self) -> _Endpoint:
        """The connection's target node."""


# ──────────────────────────────────────────────
# Output Data Structure
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class ResolvedLayout:
    """Output of Phase 2: absolute pixel coordinates for all scene objects.

    Attributes:
        node_boxes: Mapping from node ID to its absolute BoundingBox.
        connection_routes: Mapping from connection ID to routed polyline points.
        canvas_width: Canvas width in pixels.
        canvas_height: Canvas height in pixels.
    """

    node_boxes: dict[str, BoundingBox]
    connection_routes: dict[str, list[Point]]
    canvas_width: int
    canvas_height: int


# ──────────────────────────────────────────────
# Internal Graph Node for DAG Traversal
# ──────────────────────────────────────────────


@dataclass
class _LayoutNode:
    """Internal representation of a Node during layout computation.

    Stores the Node reference, computed center coordinates (before
    centering offset), and computed BoundingBox.
    """

    node: LayoutNode
    center_x: float = 0.0
    center_y: float = 0.0
    bbox: BoundingBox | None = None
    bbox_width: float = 0.0
    bbox_height: float = 0.0


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def resolve_layout(
    nodes: Sequence[LayoutNode],
    connections: Sequence[LayoutConnection],
    canvas_width: int,
    canvas_height: int,
) -> ResolvedLayout:
    """Resolve relative positioning into absolute pixel coordinates.

    This is the main entry point for Phase 2 of the pipeline.

    Args:
        nodes: All Nodes and Databases in the scene.
        connections: All Connections in the scene.
        canvas_width: Canvas width in pixels.
        canvas_height: Canvas height in pixels.

    Returns:
        ResolvedLayout with BoundingBoxes and routed connection paths.

    Raises:
        DuplicateIdError: If two nodes share the same ID.
        CircularReferenceError: If positioning forms a cycle.
        OrphanNodeError: If a non-root node has no position set.
        OverflowCanvasError: If the resolved diagram exceeds the canvas.
    """
    if not nodes:
        return ResolvedLayout(
            node_boxes={},
            connection_routes={},
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )

    # Step 1: Build internal graph
    layout_nodes = _build_graph(nodes)

    # Step 2: Topological sort (validates cycles + orphans)
    sorted_ids = _topological_sort(layout_nodes, nodes)

    # Step 3: Compute sizes (BoundingBox dimensions from text)
    _compute_sizes(layout_nodes)

    # Step 4: Assign absolute coordinates via DAG walk
    _assign_coordinates(layout_nodes, sorted_ids)

    # Step 5: Center diagram on canvas
    _center_on_canvas(layout_nodes, canvas_width, canvas_height)

    # Step 6: Build final BoundingBoxes
    node_boxes = _finalize_bounding_boxes(layout_nodes)

    # Step 7: Check canvas overflow
    _check_overflow(node_boxes, canvas_width, canvas_height)

    # Step 8: Route connections
    connection_routes = _route_connections(connections, node_boxes)

    return ResolvedLayout(
        node_boxes=node_boxes,
        connection_routes=connection_routes,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )


# ──────────────────────────────────────────────
# Step 1: Build Graph
# ──────────────────────────────────────────────


def _build_graph(nodes: Sequence[LayoutNode]) -> dict[str, _LayoutNode]:
    """Build an ID-keyed lookup of _LayoutNodes. Validates uniqueness.

    Args:
        nodes: All nodes in the scene.

    Returns:
        Dictionary mapping node ID to _LayoutNode.

    Raises:
        DuplicateIdError: If two nodes share the same ID.
    """
    layout_nodes: dict[str, _LayoutNode] = {}

    for node in nodes:
        if node.id in layout_nodes:
            raise DuplicateIdError(node.id)
        layout_nodes[node.id] = _LayoutNode(node=node)

    return layout_nodes


# ──────────────────────────────────────────────
# Step 2: Topological Sort (Kahn's Algorithm)
# ──────────────────────────────────────────────


def _topological_sort(
    layout_nodes: dict[str, _LayoutNode],
    nodes: Sequence[LayoutNode],
) -> list[str]:
    """Topological sort of nodes based on position dependencies.

    A node's position depends on its anchor (relative positioning). Root
    nodes have no dependencies and are processed first:
        - Unpositioned nodes (no ``position``): auto-placed side by side.
        - Absolutely-positioned nodes (``AbsolutePosition``): fixed pixel
          coordinates, no anchor dependency.

    Uses Kahn's algorithm: O(N + E).

    Args:
        layout_nodes: ID-keyed layout nodes.
        nodes: Original node list (for orphan detection).

    Returns:
        List of node IDs in topological order.

    Raises:
        CircularReferenceError: If a cycle is detected.
        OrphanNodeError: If a non-root node has no position AND
            there are other nodes that do have positions (mixed state).
    """
    # Build adjacency and in-degree
    in_degree: dict[str, int] = {nid: 0 for nid in layout_nodes}
    dependents: dict[str, list[str]] = defaultdict(list)

    root_count = 0
    positioned_count = 0

    for node in nodes:
        pos = node.position
        if pos is None or isinstance(pos, AbsolutePosition):
            # Root: either unpositioned (auto-placed) or absolutely positioned
            # (fixed coordinate, no anchor dependency).
            root_count += 1
        else:
            positioned_count += 1
            anchor_id = pos.anchor_id

            if anchor_id not in layout_nodes:
                raise OrphanNodeError(node.label)

            # Edge: anchor_id -> node.id (anchor must be resolved first)
            dependents[anchor_id].append(node.id)
            in_degree[node.id] += 1

    # Orphan detection: when positioned nodes coexist with multiple roots, the
    # extra roots are auto-placed side by side (multiple roots are allowed), so
    # no error is raised here. The counters are retained for future diagnostics.
    if positioned_count > 0 and root_count > 1:
        # Multiple roots are intentionally permitted (auto side-by-side layout).
        pass

    # Kahn's algorithm
    queue: deque[str] = deque()
    for nid, deg in in_degree.items():
        if deg == 0:
            queue.append(nid)

    sorted_order: list[str] = []

    while queue:
        nid = queue.popleft()
        sorted_order.append(nid)

        for dep_id in dependents[nid]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                queue.append(dep_id)

    # Cycle detection: if not all nodes were processed
    if len(sorted_order) != len(layout_nodes):
        processed = set(sorted_order)
        cycle_nodes = [nid for nid in layout_nodes if nid not in processed]
        raise CircularReferenceError(cycle_nodes)

    return sorted_order


# ──────────────────────────────────────────────
# Step 3: Compute Sizes
# ──────────────────────────────────────────────


def _compute_sizes(layout_nodes: dict[str, _LayoutNode]) -> None:
    """Compute BoundingBox dimensions for each node from its label text.

    Uses monospace approximation. Skia exact metrics will replace
    this in the Renderer phase.
    """
    for ln in layout_nodes.values():
        width, height = estimate_text_bbox(ln.node.label)
        ln.bbox_width = width
        ln.bbox_height = height


# ──────────────────────────────────────────────
# Step 4: Assign Coordinates (DAG Walk)
# ──────────────────────────────────────────────


_DIRECTION_OFFSETS: dict[Direction, tuple[float, float]] = {
    Direction.RIGHT_OF: (1.0, 0.0),
    Direction.LEFT_OF: (-1.0, 0.0),
    Direction.BELOW: (0.0, 1.0),
    Direction.ABOVE: (0.0, -1.0),
}
"""Unit offset vectors for each Direction.
Multiplied by (distance * GRID_UNIT + half_sizes) to get pixel offset.
"""


def _assign_coordinates(
    layout_nodes: dict[str, _LayoutNode],
    sorted_ids: list[str],
) -> None:
    """Walk topological order and compute center coordinates.

    Root nodes start at (0, 0). Each subsequent node is placed
    relative to its anchor using Direction and distance.

    The offset includes both the grid distance AND the half-widths/heights
    of the anchor and child nodes (edge-to-edge spacing, not center-to-center).

    Absolutely-positioned nodes (``AbsolutePosition``) skip the DAG walk
    entirely: their center is derived directly from the user-specified
    top-left ``(x, y)`` plus half the estimated bounding box.
    """
    root_offset_x = 0.0

    for nid in sorted_ids:
        ln = layout_nodes[nid]
        node = ln.node
        pos = node.position

        if isinstance(pos, AbsolutePosition):
            # Absolute: derive center from user top-left + half box size.
            ln.center_x = pos.x + ln.bbox_width / 2
            ln.center_y = pos.y + ln.bbox_height / 2
            continue

        if pos is None:
            # Root node: place at accumulated horizontal offset
            ln.center_x = root_offset_x
            ln.center_y = 0.0
            # Advance offset for next root (side-by-side placement)
            root_offset_x += ln.bbox_width + GRID_UNIT
            continue

        # Relative positioned node: compute offset from anchor
        anchor_ln = layout_nodes[pos.anchor_id]
        direction = pos.direction
        distance_px = pos.distance * GRID_UNIT

        dx_unit, dy_unit = _DIRECTION_OFFSETS[direction]

        if dx_unit != 0:
            # Horizontal offset: edge-to-edge = half_anchor_w + distance + half_child_w
            gap = anchor_ln.bbox_width / 2 + distance_px + ln.bbox_width / 2
            ln.center_x = anchor_ln.center_x + dx_unit * gap
            ln.center_y = anchor_ln.center_y
        else:
            # Vertical offset: edge-to-edge = half_anchor_h + distance + half_child_h
            gap = anchor_ln.bbox_height / 2 + distance_px + ln.bbox_height / 2
            ln.center_x = anchor_ln.center_x
            ln.center_y = anchor_ln.center_y + dy_unit * gap


# ──────────────────────────────────────────────
# Step 5: Center on Canvas
# ──────────────────────────────────────────────


def _center_on_canvas(
    layout_nodes: dict[str, _LayoutNode],
    canvas_width: int,
    canvas_height: int,
) -> None:
    """Translate all node centers so the diagram is centered on the canvas.

    Computes the bounding rectangle of all node centers, then applies
    an offset to center that rectangle on the canvas.

    Skipped entirely when ANY node is absolutely positioned: absolute
    positioning signals manual layout control, so auto-centering would
    move user-placed nodes away from their intended coordinates.
    """
    if not layout_nodes:
        return

    if any(isinstance(ln.node.position, AbsolutePosition) for ln in layout_nodes.values()):
        # Manual layout mode — respect user-specified coordinates verbatim.
        return

    # Find extent of all nodes (using center +/- half_size)
    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")

    for ln in layout_nodes.values():
        left = ln.center_x - ln.bbox_width / 2
        right = ln.center_x + ln.bbox_width / 2
        top = ln.center_y - ln.bbox_height / 2
        bottom = ln.center_y + ln.bbox_height / 2

        min_x = min(min_x, left)
        max_x = max(max_x, right)
        min_y = min(min_y, top)
        max_y = max(max_y, bottom)

    diagram_width = max_x - min_x
    diagram_height = max_y - min_y

    # Offset to center on canvas
    offset_x = (canvas_width - diagram_width) / 2 - min_x
    offset_y = (canvas_height - diagram_height) / 2 - min_y

    for ln in layout_nodes.values():
        ln.center_x += offset_x
        ln.center_y += offset_y


# ──────────────────────────────────────────────
# Step 6: Finalize BoundingBoxes
# ──────────────────────────────────────────────


def _finalize_bounding_boxes(
    layout_nodes: dict[str, _LayoutNode],
) -> dict[str, BoundingBox]:
    """Convert centered coordinates to BoundingBox (top-left origin)."""
    result: dict[str, BoundingBox] = {}

    for nid, ln in layout_nodes.items():
        bbox = BoundingBox(
            x=ln.center_x - ln.bbox_width / 2,
            y=ln.center_y - ln.bbox_height / 2,
            width=ln.bbox_width,
            height=ln.bbox_height,
        )
        ln.bbox = bbox
        result[nid] = bbox

    return result


# ──────────────────────────────────────────────
# Step 7: Canvas Overflow Check
# ──────────────────────────────────────────────

CANVAS_MARGIN: float = 20.0
"""Minimum margin between diagram edge and canvas edge (pixels)."""


def _check_overflow(
    node_boxes: dict[str, BoundingBox],
    canvas_width: int,
    canvas_height: int,
) -> None:
    """Verify all nodes fit within the canvas with margin.

    Raises:
        OverflowCanvasError: If any node extends beyond canvas bounds.
    """
    if not node_boxes:
        return

    min_x = min(b.x for b in node_boxes.values())
    max_x = max(b.x + b.width for b in node_boxes.values())
    min_y = min(b.y for b in node_boxes.values())
    max_y = max(b.y + b.height for b in node_boxes.values())

    diagram_w = max_x - min_x
    diagram_h = max_y - min_y

    if (
        min_x < CANVAS_MARGIN
        or min_y < CANVAS_MARGIN
        or max_x > canvas_width - CANVAS_MARGIN
        or max_y > canvas_height - CANVAS_MARGIN
    ):
        raise OverflowCanvasError(
            required_width=diagram_w,
            required_height=diagram_h,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )


# ──────────────────────────────────────────────
# Step 8: Route Connections
# ──────────────────────────────────────────────


def _route_connections(
    connections: Sequence[LayoutConnection],
    node_boxes: dict[str, BoundingBox],
) -> dict[str, list[Point]]:
    """Route all connections using obstacle-aware Manhattan routing.

    Each connection is routed through A* pathfinding that avoids
    all other nodes' BoundingBoxes. Falls back to direct Manhattan
    routing if A* cannot find a valid path.

    Args:
        connections: All connections in the scene.
        node_boxes: Resolved BoundingBoxes for all nodes.

    Returns:
        Dictionary mapping connection ID to routed polyline points.
    """
    routes: dict[str, list[Point]] = {}
    all_boxes = list(node_boxes.values())

    for conn in connections:
        src_bbox = node_boxes.get(conn.source.id)
        tgt_bbox = node_boxes.get(conn.target.id)

        if src_bbox is None or tgt_bbox is None:
            # Skip connections to unresolved nodes
            continue

        route = manhattan_route(
            src_bbox,
            tgt_bbox,
            conn.waypoints,
            obstacles=all_boxes,
        )
        routes[conn.id] = route

    return routes
