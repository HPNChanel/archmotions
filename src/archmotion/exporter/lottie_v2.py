"""Lottie JSON export for v2.0 scenes (pure Python — no skia).

Each :class:`~archmotion.core.vmobject.VMobject` becomes a Lottie shape layer:
its Bezier point array converts to a Lottie ``"ks"`` shape (anchors +
relative in/out tangents), and opacity animations become Lottie keyframes.
Transform/fill/morph keyframing is a follow-up; the final resolved geometry is
emitted so the export is always valid and playable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from archmotion.core.property import Property, PropertyAction
from archmotion.core.transform import Transform
from archmotion.core.vmobject import VMobject
from archmotion.render.path_render import resolve_effective, theme_style_for

if TYPE_CHECKING:
    from archmotion.core.scene import Scene


def build_lottie(scene: Scene, *, title: str = "ArchMotion") -> dict[str, Any]:
    """Build a Lottie dict for ``scene``."""
    timeline = scene.compile_timeline()
    graphics = [g for g in scene.all_graphics() if isinstance(g, VMobject)]
    width, height = scene.resolution
    fps = scene.fps
    total_frames = max(1, timeline.total_frames)

    # Lottie paints layer 0 on top; our z_order ascends bottom→top.
    layers: list[dict[str, Any]] = []
    snap = timeline.snapshot_at(timeline.total_duration)
    for index, graphic in enumerate(reversed(graphics)):
        state = resolve_effective(
            graphic,
            snap.scalars.get(graphic.id),
            snap.morphs.get(graphic.id),
            scene.camera,
            theme_style_for(graphic, scene.theme),
            scalar_lookup=snap.scalars,
            morph_contour_starts=snap.morph_contours.get(graphic.id),
        )
        world_pts = np.asarray(state.points, dtype=np.float64).reshape(-1, 2)
        world = Transform(state.matrix).apply_to_points(world_pts)
        shapes = _shapes_for(state, world)
        layers.append(
            {
                "ddd": 0,
                "ind": index,
                "ty": 4,
                "nm": f"{type(graphic).__name__} {index}",
                "sr": 1,
                "ks": {
                    "o": _opacity_prop(graphic.id, timeline.property_actions, fps),
                    "r": {"a": 0, "k": 0},
                    "p": {"a": 0, "k": [0, 0]},
                    "a": {"a": 0, "k": [0, 0]},
                    "s": {"a": 0, "k": [100, 100]},
                },
                "shapes": shapes,
                "ip": 0,
                "op": total_frames,
                "st": 0,
                "bm": 0,
            }
        )

    return {
        "v": "5.7.0",
        "fr": fps,
        "ip": 0,
        "op": total_frames,
        "w": width,
        "h": height,
        "nm": title,
        "ddd": 0,
        "assets": [],
        "layers": layers,
    }


def _shapes_for(state: object, world: object) -> list[dict[str, Any]]:
    pts = np.asarray(world, dtype=np.float64).reshape(-1, 2)
    paths = _bezier_shapes(pts, state.contour_starts)  # type: ignore[attr-defined]
    fill_color = _hex_to_rgb01(state.fill_color)  # type: ignore[attr-defined]
    return [
        *paths,
        {
            "ty": "fl",
            "c": {"a": 0, "k": list(fill_color)},
            "o": {"a": 0, "k": round(state.fill_opacity * 100, 1)},  # type: ignore[attr-defined]
            "r": 1,
            "bm": 0,
            "nm": "Fill",
        },
        {
            "ty": "st",
            "c": {"a": 0, "k": list(_hex_to_rgb01(state.stroke_color))},  # type: ignore[attr-defined]
            "o": {"a": 0, "k": round(state.stroke_opacity * 100, 1)},  # type: ignore[attr-defined]
            "w": {"a": 0, "k": state.stroke_width},  # type: ignore[attr-defined]
            "lc": 2,
            "lj": 2,
            "bm": 0,
            "nm": "Stroke",
        },
    ]


def _bezier_shapes(pts: object, contour_starts: list[int]) -> list[dict[str, Any]]:
    """Convert every VMobject contour into a valid Lottie path shape."""
    arr = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    if arr.shape[0] == 0:
        return []

    shapes: list[dict[str, Any]] = []
    starts = [*list(contour_starts), arr.shape[0]]
    for ci in range(len(contour_starts)):
        start = contour_starts[ci]
        end = starts[ci + 1]
        if end - start < 1:
            continue
        contour = arr[start:end]
        segment_count = (contour.shape[0] - 1) // 3
        anchors = [contour[0], *[contour[3 * i] for i in range(1, segment_count + 1)]]
        closed = segment_count > 0 and np.allclose(anchors[0], anchors[-1])
        if closed:
            anchors.pop()
        vertices = [[float(point[0]), float(point[1])] for point in anchors]
        in_tangents = [[0.0, 0.0] for _ in vertices]
        out_tangents = [[0.0, 0.0] for _ in vertices]
        for segment in range(segment_count):
            source_index = segment
            target_index = (segment + 1) % len(vertices)
            if source_index >= len(vertices) or (not closed and target_index == 0):
                continue
            source = np.asarray(anchors[source_index])
            target = np.asarray(anchors[target_index])
            h1 = contour[1 + 3 * segment]
            h2 = contour[2 + 3 * segment]
            out_tangents[source_index] = [
                float(h1[0] - source[0]),
                float(h1[1] - source[1]),
            ]
            in_tangents[target_index] = [
                float(h2[0] - target[0]),
                float(h2[1] - target[1]),
            ]
        shapes.append(
            {
                "ty": "sh",
                "ks": {
                    "a": 0,
                    "k": {
                        "i": in_tangents,
                        "o": out_tangents,
                        "v": vertices,
                        "c": closed,
                    },
                },
                "nm": f"Path {ci + 1}",
            }
        )
    return shapes


def _opacity_prop(
    target_id: str,
    actions: tuple[PropertyAction, ...],
    fps: int,
) -> dict[str, Any]:
    """Build the Lottie opacity property (0-100) with keyframes if animated."""
    kfs: list[dict[str, Any]] = []
    for a in actions:
        if a.target_id == target_id and a.prop == Property.OPACITY:
            kfs.append(
                {"t": max(0, round(a.start_time * fps)), "s": [round(a.start_value * 100, 1)]}
            )
            kfs.append({"t": round(a.end_time * fps), "s": [round(a.end_value * 100, 1)]})
    if not kfs:
        return {"a": 0, "k": 100}
    kfs.sort(key=lambda k: k["t"])
    # Lottie keyframes: all but the last need an easing handle ("o"/"i").
    for kf in kfs[:-1]:
        kf["o"] = {"x": [0.5], "y": [0.0]}
        kf["i"] = {"x": [0.5], "y": [1.0]}
    return {"a": 1, "k": kfs}


def _hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return (1.0, 1.0, 1.0)
    try:
        return (int(c[0:2], 16) / 255.0, int(c[2:4], 16) / 255.0, int(c[4:6], 16) / 255.0)
    except ValueError:
        return (1.0, 1.0, 1.0)
