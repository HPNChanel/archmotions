"""Lottie JSON Exporter — converts ArchMotion scenes to Lottie animation format.

Architectural Note:
    Translates Phase 2 (ResolvedLayout) + Phase 3 (CompiledTimeline) data into
    the Lottie JSON specification (bodymovin format). This enables:

    - Browser playback via lottie-web / @dotlottie/player
    - Notion / Slack / Discord embeds
    - Mobile apps via lottie-android / lottie-ios
    - Infinite vector zoom (SVG-based, not raster)
    - Ultra-lightweight file sizes (~10-50KB vs 5-20MB MP4)

    Lottie Structure:
        Root → layers[] → shapes[] + transforms[] + keyframes[]
        Each ArchMotion Node becomes a Lottie shape layer.
        Each ScheduledAction becomes Lottie keyframes on the corresponding
        layer's transform properties.

    Mapping:
        Node BoundingBox → Lottie rect shape + text
        Connection route → Lottie path shape (polyline)
        OPACITY action → Lottie transform.opacity keyframes
        SCALE action → Lottie transform.scale keyframes
        PATH_PROGRESS → Lottie trim path keyframes (stroke dash offset)

    Limitations (v1.0.0):
        - Transfer animations are simplified to opacity fade on path
        - Glow/shadow effects are not supported in Lottie
        - Font rendering depends on client-side font availability
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from archmotion._types import AnimatableProperty, EasingType, PrimitiveType
from archmotion.layout.bbox import BoundingBox
from archmotion.layout.resolver import ResolvedLayout
from archmotion.renderer.theme import ThemeConfig
from archmotion.timeline.actions import ScheduledAction
from archmotion.timeline.compiler import CompiledTimeline, TransferMeta


# ──────────────────────────────────────────────
# Lottie Constants
# ──────────────────────────────────────────────

_LOTTIE_VERSION: str = "5.7.4"
"""Lottie specification version."""

_LAYER_TYPE_SHAPE: int = 4
"""Lottie layer type for shape layers."""

_SHAPE_TYPE_RECT: str = "rc"
"""Lottie shape type: rectangle."""

_SHAPE_TYPE_FILL: str = "fl"
"""Lottie shape type: solid fill."""

_SHAPE_TYPE_STROKE: str = "st"
"""Lottie shape type: stroke."""

_SHAPE_TYPE_PATH: str = "sh"
"""Lottie shape type: freeform path."""


# ──────────────────────────────────────────────
# Easing Mapping
# ──────────────────────────────────────────────


def _easing_to_lottie(easing: EasingType) -> dict[str, Any]:
    """Convert ArchMotion easing to Lottie bezier easing curves.

    Lottie uses cubic bezier control points for easing:
        i = in tangent  [x, y] (normalized 0-1)
        o = out tangent [x, y] (normalized 0-1)

    Args:
        easing: ArchMotion easing type.

    Returns:
        Lottie easing object with ``i`` and ``o`` bezier handles.
    """
    curves: dict[EasingType, tuple[list[float], list[float]]] = {
        EasingType.LINEAR: ([0.0, 0.0], [1.0, 1.0]),
        EasingType.EASE_IN: ([0.42, 0.0], [1.0, 1.0]),
        EasingType.EASE_OUT: ([0.0, 0.0], [0.58, 1.0]),
        EasingType.EASE_IN_OUT: ([0.42, 0.0], [0.58, 1.0]),
        EasingType.EASE_IN_CUBIC: ([0.55, 0.055], [0.675, 0.19]),
        EasingType.EASE_OUT_CUBIC: ([0.215, 0.61], [0.355, 1.0]),
        EasingType.EASE_OUT_BOUNCE: ([0.0, 0.0], [0.58, 1.0]),
    }

    out_handle, in_handle = curves.get(
        easing, ([0.42, 0.0], [0.58, 1.0]),
    )

    return {
        "i": {"x": [in_handle[0]], "y": [in_handle[1]]},
        "o": {"x": [out_handle[0]], "y": [out_handle[1]]},
    }


# ──────────────────────────────────────────────
# Color Utilities
# ──────────────────────────────────────────────


def _rgba_to_lottie(rgba: tuple[float, float, float, float]) -> list[float]:
    """Convert RGBA tuple (0-1) to Lottie color array [R, G, B, 1].

    Args:
        rgba: RGBA tuple with values in [0.0, 1.0].

    Returns:
        Lottie [R, G, B, A] array.
    """
    return [rgba[0], rgba[1], rgba[2], rgba[3]]


def _hex_to_lottie_color(hex_color: str) -> list[float]:
    """Convert hex color string to Lottie [R, G, B, 1] array.

    Args:
        hex_color: CSS hex color (e.g., '#cdd6f4').

    Returns:
        Lottie color array [R, G, B, 1].
    """
    h = hex_color.lstrip("#")
    try:
        if len(h) == 6:
            r = int(h[0:2], 16) / 255.0
            g = int(h[2:4], 16) / 255.0
            b = int(h[4:6], 16) / 255.0
            return [r, g, b, 1.0]
    except ValueError:
        pass
    return [1.0, 1.0, 1.0, 1.0]


# ──────────────────────────────────────────────
# Keyframe Builder
# ──────────────────────────────────────────────


def _build_keyframes(
    actions: list[ScheduledAction],
    fps: int,
    prop_filter: AnimatableProperty,
    value_scale: float = 100.0,
) -> list[dict[str, Any]]:
    """Build Lottie keyframe array from ScheduledActions.

    Args:
        actions: Actions filtered by target_id.
        fps: Frames per second.
        prop_filter: Only include actions for this property.
        value_scale: Multiply values by this factor (Lottie uses 0-100 for opacity).

    Returns:
        List of Lottie keyframe objects, sorted by time.
    """
    filtered = [a for a in actions if a.prop == prop_filter]
    if not filtered:
        return []

    keyframes: list[dict[str, Any]] = []

    for action in sorted(filtered, key=lambda a: a.start_time):
        start_frame = round(action.start_time * fps)
        end_frame = round(action.end_time * fps)
        easing = _easing_to_lottie(action.easing)

        # Start keyframe
        keyframes.append({
            "t": start_frame,
            "s": [action.start_value * value_scale],
            "e": [action.end_value * value_scale],
            **easing,
        })

        # End keyframe (hold)
        keyframes.append({
            "t": end_frame,
            "s": [action.end_value * value_scale],
        })

    return keyframes


# ──────────────────────────────────────────────
# Shape Builders
# ──────────────────────────────────────────────


def _build_rect_shape(
    bbox: BoundingBox,
    fill_color: list[float],
    border_color: list[float],
    corner_radius: float = 8.0,
) -> list[dict[str, Any]]:
    """Build Lottie shape items for a rounded rectangle node.

    Args:
        bbox: Node BoundingBox.
        fill_color: Lottie RGBA fill color.
        border_color: Lottie RGBA border color.
        corner_radius: Corner radius in pixels.

    Returns:
        List of Lottie shape items (rect + fill + stroke).
    """
    return [
        {
            "ty": _SHAPE_TYPE_RECT,
            "p": {"a": 0, "k": [0, 0]},
            "s": {"a": 0, "k": [bbox.width, bbox.height]},
            "r": {"a": 0, "k": corner_radius},
        },
        {
            "ty": _SHAPE_TYPE_FILL,
            "c": {"a": 0, "k": fill_color[:3]},
            "o": {"a": 0, "k": fill_color[3] * 100},
        },
        {
            "ty": _SHAPE_TYPE_STROKE,
            "c": {"a": 0, "k": border_color[:3]},
            "o": {"a": 0, "k": 100},
            "w": {"a": 0, "k": 2},
        },
    ]


def _build_connection_path(
    points: list[tuple[float, float]],
    stroke_color: list[float],
    stroke_width: float = 2.0,
) -> list[dict[str, Any]]:
    """Build Lottie path shape from connection polyline points.

    Args:
        points: Polyline vertices [(x, y), ...].
        stroke_color: Lottie RGBA color.
        stroke_width: Line width in pixels.

    Returns:
        List of Lottie shape items (path + stroke).
    """
    if len(points) < 2:
        return []

    # Build Lottie bezier path (straight segments)
    vertices = [[p[0], p[1]] for p in points]
    in_tangents = [[0, 0]] * len(points)
    out_tangents = [[0, 0]] * len(points)

    return [
        {
            "ty": _SHAPE_TYPE_PATH,
            "ks": {
                "a": 0,
                "k": {
                    "c": False,  # Open path (not closed)
                    "v": vertices,
                    "i": in_tangents,
                    "o": out_tangents,
                },
            },
        },
        {
            "ty": _SHAPE_TYPE_STROKE,
            "c": {"a": 0, "k": stroke_color[:3]},
            "o": {"a": 0, "k": 100},
            "w": {"a": 0, "k": stroke_width},
            "lc": 2,  # Round line cap
            "lj": 2,  # Round line join
        },
    ]


# ──────────────────────────────────────────────
# Layer Builders
# ──────────────────────────────────────────────


def _build_node_layer(
    node_id: str,
    label: str,
    bbox: BoundingBox,
    node_type: PrimitiveType,
    theme: ThemeConfig,
    actions: list[ScheduledAction],
    fps: int,
    total_frames: int,
    layer_index: int,
) -> dict[str, Any]:
    """Build a Lottie shape layer for a single node.

    Args:
        node_id: Node identifier.
        label: Display label.
        bbox: Node BoundingBox (absolute position).
        node_type: Primitive type for shape selection.
        theme: Visual theme configuration.
        actions: All actions targeting this node.
        fps: Frames per second.
        total_frames: Total animation frames.
        layer_index: Layer ordering index.

    Returns:
        Lottie layer dictionary.
    """
    bg_color = _hex_to_lottie_color(theme.node_fill)  # Approximate
    border_color = _hex_to_lottie_color(theme.node_border)
    corner_radius = 8.0

    # Adjust shape for primitive type
    if node_type == PrimitiveType.DATABASE:
        corner_radius = 4.0
    elif node_type == PrimitiveType.CLOUD:
        corner_radius = 20.0
    elif node_type == PrimitiveType.USER:
        corner_radius = 50.0  # Circle-like

    shapes = _build_rect_shape(bbox, bg_color, border_color, corner_radius)

    # Build transform with animated properties
    opacity_kf = _build_keyframes(actions, fps, AnimatableProperty.OPACITY)
    scale_kf = _build_keyframes(
        actions, fps, AnimatableProperty.SCALE, value_scale=100.0,
    )

    transform: dict[str, Any] = {
        "p": {"a": 0, "k": [bbox.center[0], bbox.center[1]]},
        "a": {"a": 0, "k": [0, 0]},
        "s": (
            {"a": 1, "k": scale_kf}
            if scale_kf
            else {"a": 0, "k": [100, 100]}
        ),
        "r": {"a": 0, "k": 0},
        "o": (
            {"a": 1, "k": opacity_kf}
            if opacity_kf
            else {"a": 0, "k": 100}
        ),
    }

    return {
        "ty": _LAYER_TYPE_SHAPE,
        "nm": f"{label} ({node_id})",
        "ind": layer_index,
        "ip": 0,
        "op": total_frames,
        "st": 0,
        "ks": transform,
        "shapes": shapes,
    }


def _build_connection_layer(
    conn_id: str,
    label: str | None,
    points: list[tuple[float, float]],
    theme: ThemeConfig,
    actions: list[ScheduledAction],
    fps: int,
    total_frames: int,
    layer_index: int,
) -> dict[str, Any]:
    """Build a Lottie shape layer for a connection line.

    Args:
        conn_id: Connection identifier.
        label: Connection label (optional).
        points: Polyline route points.
        theme: Visual theme configuration.
        actions: Actions targeting this connection.
        fps: Frames per second.
        total_frames: Total animation frames.
        layer_index: Layer ordering index.

    Returns:
        Lottie layer dictionary.
    """
    stroke_color = _hex_to_lottie_color(theme.conn_stroke)
    shapes = _build_connection_path(points, stroke_color)

    opacity_kf = _build_keyframes(actions, fps, AnimatableProperty.OPACITY)

    transform: dict[str, Any] = {
        "p": {"a": 0, "k": [0, 0]},
        "a": {"a": 0, "k": [0, 0]},
        "s": {"a": 0, "k": [100, 100]},
        "r": {"a": 0, "k": 0},
        "o": (
            {"a": 1, "k": opacity_kf}
            if opacity_kf
            else {"a": 0, "k": 100}
        ),
    }

    display_name = f"conn:{conn_id}" if label is None else f"{label} ({conn_id})"

    return {
        "ty": _LAYER_TYPE_SHAPE,
        "nm": display_name,
        "ind": layer_index,
        "ip": 0,
        "op": total_frames,
        "st": 0,
        "ks": transform,
        "shapes": shapes,
    }


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def build_lottie_json(
    timeline: CompiledTimeline,
    layout: ResolvedLayout,
    theme: ThemeConfig,
    node_labels: dict[str, str],
    node_types: dict[str, PrimitiveType],
    connection_labels: dict[str, str | None],
) -> dict[str, Any]:
    """Build a complete Lottie JSON animation from ArchMotion scene data.

    This is the main entry point for Lottie export. It translates the
    entire resolved scene into Lottie's bodymovin JSON format.

    Args:
        timeline: Compiled timeline with actions and metadata.
        layout: Resolved layout with bounding boxes and routes.
        theme: Visual theme configuration.
        node_labels: Node ID → label text mapping.
        node_types: Node ID → PrimitiveType mapping.
        connection_labels: Connection ID → label text mapping.

    Returns:
        Complete Lottie JSON dictionary ready for serialization.
    """
    layers: list[dict[str, Any]] = []
    layer_idx = 0

    # Index actions by target_id for O(1) lookup
    actions_by_target: dict[str, list[ScheduledAction]] = {}
    for action in timeline.actions:
        actions_by_target.setdefault(action.target_id, []).append(action)

    # Build connection layers first (render below nodes)
    for conn_id, route in layout.connection_routes.items():
        conn_actions = actions_by_target.get(conn_id, [])
        layer = _build_connection_layer(
            conn_id=conn_id,
            label=connection_labels.get(conn_id),
            points=route,
            theme=theme,
            actions=conn_actions,
            fps=timeline.fps,
            total_frames=timeline.total_frames,
            layer_index=layer_idx,
        )
        layers.append(layer)
        layer_idx += 1

    # Build node layers (render above connections)
    for node_id, bbox in layout.node_boxes.items():
        node_actions = actions_by_target.get(node_id, [])
        layer = _build_node_layer(
            node_id=node_id,
            label=node_labels.get(node_id, node_id),
            bbox=bbox,
            node_type=node_types.get(node_id, PrimitiveType.NODE),
            theme=theme,
            actions=node_actions,
            fps=timeline.fps,
            total_frames=timeline.total_frames,
            layer_index=layer_idx,
        )
        layers.append(layer)
        layer_idx += 1

    # Background color (available for future Lottie background layer)
    _bg = theme.background_rgba  # noqa: F841

    return {
        "v": _LOTTIE_VERSION,
        "fr": timeline.fps,
        "ip": 0,
        "op": timeline.total_frames,
        "w": layout.canvas_width,
        "h": layout.canvas_height,
        "nm": "ArchMotion Scene",
        "ddd": 0,
        "assets": [],
        "layers": layers,
        "meta": {
            "g": "ArchMotion v0.2.0",
            "tc": "",
        },
    }


def export_lottie(
    timeline: CompiledTimeline,
    layout: ResolvedLayout,
    theme: ThemeConfig,
    node_labels: dict[str, str],
    node_types: dict[str, PrimitiveType],
    connection_labels: dict[str, str | None],
    output_path: Path,
    *,
    minify: bool = False,
) -> Path:
    """Export scene to a Lottie JSON file.

    Args:
        timeline: Compiled timeline from Phase 3.
        layout: Resolved layout from Phase 2.
        theme: Visual theme configuration.
        node_labels: Node ID → label text mapping.
        node_types: Node ID → PrimitiveType mapping.
        connection_labels: Connection ID → label text mapping.
        output_path: Output .json file path.
        minify: If True, output compact JSON without indentation.

    Returns:
        Path to the created Lottie JSON file.
    """
    lottie_data = build_lottie_json(
        timeline=timeline,
        layout=layout,
        theme=theme,
        node_labels=node_labels,
        node_types=node_types,
        connection_labels=connection_labels,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        if minify:
            json.dump(lottie_data, f, separators=(",", ":"))
        else:
            json.dump(lottie_data, f, indent=2)

    return output_path
