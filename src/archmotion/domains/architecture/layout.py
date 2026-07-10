"""Architecture layout entry point for v2 scenes.

Bridges the generic layout resolver (:mod:`archmotion.layout.resolver`) with the
v2 architecture domain: it collects the architecture nodes + connections from a
:class:`~archmotion.core.scene.Scene`, resolves relative/absolute positions to
pixel coordinates, applies the resolved centers to the nodes, and regenerates
each connection's points from its A*/Manhattan route.

This is an **explicit, opt-in** step (call it before ``scene.render()`` /
``scene.to_lottie()``) so the generic ``core.Scene`` stays domain-agnostic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archmotion.layout.resolver import ResolvedLayout, resolve_layout

if TYPE_CHECKING:
    from archmotion.core.scene import Scene


def resolve_architecture(
    scene: Scene,
    *,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    corner_radius: float = 0.0,
) -> ResolvedLayout:
    """Resolve architecture layout in-place and return the resolved layout.

    Collects :class:`~archmotion.domains.architecture.primitives.Node` (and
    subclass) graphics plus :class:`~archmotion.domains.architecture.connections.Connection`
    graphics from ``scene``, runs the layout resolver, then:

    - moves each node so its bounding-box center matches the resolved box, and
    - regenerates each connection's points from its routed polyline (with
      optional rounded corners).

    Nodes without a position constraint (``.right_of()`` / ``.at()``) are
    auto-placed as roots by the resolver (same semantics as v1).

    Args:
        scene: The scene holding the architecture graphics.
        canvas_width: Canvas width (defaults to ``scene.resolution`` width).
        canvas_height: Canvas height (defaults to ``scene.resolution`` height).
        corner_radius: Default bend radius for connections whose own
            ``corner_radius`` is unset (0.0 = sharp corners).

    Returns:
        The :class:`~archmotion.layout.resolver.ResolvedLayout` (node boxes +
        connection routes).
    """
    from archmotion.domains.architecture.connections import Connection
    from archmotion.domains.architecture.primitives import Node

    graphics = scene.all_graphics()
    nodes = [g for g in graphics if isinstance(g, Node)]
    connections = [g for g in graphics if isinstance(g, Connection)]

    width = canvas_width if canvas_width is not None else int(scene.resolution[0])
    height = canvas_height if canvas_height is not None else int(scene.resolution[1])

    layout = resolve_layout(nodes, connections, width, height)

    # Apply resolved centers to nodes (move_to is idempotent on the transform).
    for node in nodes:
        box = layout.node_boxes.get(node.id)
        if box is not None:
            cx, cy = box.center
            node.move_to(cx, cy)

    # Regenerate connection geometry from the routed polylines.
    for conn in connections:
        route = layout.connection_routes.get(conn.id)
        if route is not None:
            radius = conn.corner_radius if conn.corner_radius else corner_radius
            conn.regenerate_points(route, corner_radius=radius)

    return layout
