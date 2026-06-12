"""Frame Renderer -- orchestrates painting a single frame.

Architectural Note:
    render_frame() is called by each worker process in the multiprocessing
    pool. It is a pure function: given all inputs, it produces raw RGBA bytes.

    The function:
        1. Creates a SkiaCanvas
        2. Clears background
        3. Evaluates all active ScheduledActions at the frame's timestamp
        4. Paints connections (Z=10), then nodes (Z=20), then packets (Z=40)
        5. Extracts raw bytes and disposes the canvas

    This module is designed to be picklable for multiprocessing.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import NamedTuple

from archmotion._types import AnimatableProperty, PrimitiveType, Point
from archmotion.api.primitives import Node
from archmotion.layout.bbox import BoundingBox
from archmotion.renderer.canvas import SkiaCanvas, rgba_to_color4f
from archmotion.renderer.painters import (
    interpolate_path,
    paint_cache,
    paint_cloud,
    paint_connection,
    paint_database,
    paint_node,
    paint_packet,
    paint_queue,
    paint_user,
)
from archmotion.renderer.theme import ThemeConfig
from archmotion.timeline.compiler import CompiledTimeline, TransferMeta


# ──────────────────────────────────────────────
# Frame Job (picklable data for worker process)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class FrameSpec:
    """All data needed to render a single frame.

    This is designed to be picklable for multiprocessing.Pool.imap().

    Attributes:
        frame_index: Zero-based frame index.
        width: Canvas width (pixels).
        height: Canvas height (pixels).
        fps: Frames per second.
        theme: Theme configuration.
        node_boxes: Mapping from node_id -> BoundingBox.
        node_labels: Mapping from node_id -> label text.
        node_types: Mapping from node_id -> PrimitiveType.
        connection_routes: Mapping from conn_id -> routed polyline.
        connection_labels: Mapping from conn_id -> label text or None.
        compiled_actions: All ScheduledActions (as tuple for pickling).
        transfer_metas: Transfer metadata (as tuple for pickling).
    """

    frame_index: int
    width: int
    height: int
    fps: int
    theme: ThemeConfig
    node_boxes: dict[str, BoundingBox]
    node_labels: dict[str, str]
    node_types: dict[str, PrimitiveType]
    connection_routes: dict[str, list[Point]]
    connection_labels: dict[str, str | None]
    compiled_actions: tuple  # tuple[ScheduledAction, ...]
    transfer_metas: tuple  # tuple[TransferMeta, ...]


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def render_frame(spec: FrameSpec) -> bytes:
    """Render a single frame and return raw RGBA bytes.

    This function is designed to run in a multiprocessing worker.
    It is a pure function with no side effects.

    Args:
        spec: FrameSpec containing all data needed to render.

    Returns:
        Raw RGBA pixel bytes (width * height * 4).
    """
    canvas = SkiaCanvas(spec.width, spec.height)

    try:
        # 1. Clear background
        canvas.clear(rgba_to_color4f(spec.theme.background_rgba))

        # 2. Compute current timestamp
        current_time = spec.frame_index / spec.fps

        # 3. Collect animated properties for this frame
        #    {target_id: {property: value}}
        animated_state: dict[str, dict[AnimatableProperty, float]] = {}
        for action in spec.compiled_actions:
            if action.is_active_at(current_time):
                target = animated_state.setdefault(action.target_id, {})
                target[action.prop] = action.value_at(current_time)

        # 4. Paint layers in Z-index order

        # Layer Z=10: Connections
        for conn_id, route in spec.connection_routes.items():
            conn_opacity = _get_opacity(animated_state, conn_id)
            paint_connection(
                canvas=canvas,
                route=route,
                label=spec.connection_labels.get(conn_id),
                theme=spec.theme,
                opacity=conn_opacity,
            )

        # Layer Z=20: Nodes (dispatch table for shape routing)
        _PAINTER_DISPATCH = {
            PrimitiveType.DATABASE: paint_database,
            PrimitiveType.CLOUD: paint_cloud,
            PrimitiveType.QUEUE: paint_queue,
            PrimitiveType.CACHE: paint_cache,
            PrimitiveType.USER: paint_user,
        }

        for node_id, bbox in spec.node_boxes.items():
            node_opacity = _get_opacity(animated_state, node_id)
            node_glow = _get_glow(animated_state, node_id)
            label = spec.node_labels.get(node_id, "")

            # Scale animation: adjust bbox around center
            effective_bbox = _apply_scale(animated_state, node_id, bbox)

            # Color animation: override theme fill color
            effective_theme = _apply_color_shift(animated_state, node_id, spec.theme)

            node_type = spec.node_types.get(node_id, PrimitiveType.NODE)
            painter_fn = _PAINTER_DISPATCH.get(node_type, paint_node)
            painter_fn(
                canvas=canvas,
                bbox=effective_bbox,
                label=label,
                theme=effective_theme,
                opacity=node_opacity,
                glow_intensity=node_glow,
            )

        # Layer Z=40: Packets (Transfer animations)
        _paint_transfer_packets(
            canvas, spec, animated_state, current_time,
        )

        # 5. Extract bytes
        return canvas.snapshot()

    finally:
        canvas.dispose()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def _get_opacity(
    state: dict[str, dict[AnimatableProperty, float]],
    target_id: str,
) -> float:
    """Get animated opacity for a target, defaulting to 1.0."""
    props = state.get(target_id, {})
    return props.get(AnimatableProperty.OPACITY, 1.0)


def _get_glow(
    state: dict[str, dict[AnimatableProperty, float]],
    target_id: str,
) -> float:
    """Get animated glow intensity for a target, defaulting to 0.0."""
    props = state.get(target_id, {})
    return props.get(AnimatableProperty.GLOW_INTENSITY, 0.0)


def _apply_scale(
    state: dict[str, dict[AnimatableProperty, float]],
    target_id: str,
    bbox: BoundingBox,
) -> BoundingBox:
    """Apply animated SCALE to a bounding box, scaling around center.

    If no SCALE property is active, returns the original bbox unchanged.
    """
    props = state.get(target_id, {})
    scale = props.get(AnimatableProperty.SCALE)
    if scale is None or abs(scale - 1.0) < 0.001:
        return bbox

    cx, cy = bbox.center
    new_w = bbox.width * scale
    new_h = bbox.height * scale
    return BoundingBox(
        x=cx - new_w / 2,
        y=cy - new_h / 2,
        width=new_w,
        height=new_h,
    )


def _apply_color_shift(
    state: dict[str, dict[AnimatableProperty, float]],
    target_id: str,
    theme: 'ThemeConfig',
) -> 'ThemeConfig':
    """Apply animated COLOR_R/G/B to create a modified theme.

    If no color properties are active, returns the original theme unchanged.
    ThemeConfig is frozen, so we use copy + object.__setattr__ to override.
    """
    props = state.get(target_id, {})
    r = props.get(AnimatableProperty.COLOR_R)
    g = props.get(AnimatableProperty.COLOR_G)
    b = props.get(AnimatableProperty.COLOR_B)

    if r is None and g is None and b is None:
        return theme

    # Convert animated floats [0.0-1.0] to hex color
    cr = int(max(0, min(255, (r or 0.0) * 255)))
    cg = int(max(0, min(255, (g or 0.0) * 255)))
    cb = int(max(0, min(255, (b or 0.0) * 255)))
    new_fill = f"#{cr:02x}{cg:02x}{cb:02x}"

    # Create modified theme with new fill color (frozen dataclass workaround)
    modified = copy.copy(theme)
    object.__setattr__(modified, 'node_fill', new_fill)
    return modified


def _paint_transfer_packets(
    canvas: SkiaCanvas,
    spec: FrameSpec,
    animated_state: dict[str, dict[AnimatableProperty, float]],
    current_time: float,
) -> None:
    """Paint all active Transfer packets.

    For each TransferMeta, check if its packet_id has active PATH_PROGRESS,
    then interpolate position along the route and paint.
    """
    for meta in spec.transfer_metas:
        props = animated_state.get(meta.packet_id, {})
        progress = props.get(AnimatableProperty.PATH_PROGRESS)

        if progress is None:
            continue

        # Build full route from connection_ids
        full_route: list[Point] = []
        for conn_id in meta.connection_ids:
            route = spec.connection_routes.get(conn_id, [])
            if full_route and route:
                # Skip first point if it duplicates the last point of prev segment
                full_route.extend(route[1:] if route[0] == full_route[-1] else route)
            else:
                full_route.extend(route)

        if not full_route:
            continue

        # Interpolate position along route
        position = interpolate_path(full_route, progress)

        paint_packet(
            canvas=canvas,
            position=position,
            payload=meta.payload,
            theme=spec.theme,
            packet_color=meta.packet_color,
            opacity=1.0,
        )
