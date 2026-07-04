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
from archmotion.render.path_render import resolve_effective

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
    for index, graphic in enumerate(reversed(graphics)):
        snap = timeline.snapshot_at(timeline.total_duration)
        state = resolve_effective(
            graphic,
            snap.scalars.get(graphic.id),
            snap.morphs.get(graphic.id),
            scene.camera,
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
    shape = _bezier_shape(pts, state.contour_starts)  # type: ignore[attr-defined]
    fill_color = _hex_to_rgb01(state.fill_color)  # type: ignore[attr-defined]
    return [
        shape,
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


def _bezier_shape(pts: object, contour_starts: list[int]) -> dict[str, Any]:
    """Convert a point array + contour starts into a Lottie bezier shape."""
    arr = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    if arr.shape[0] == 0:
        return {
            "ty": "sh",
            "ks": {"a": 0, "k": {"a": [], "i": [], "o": [], "c": False}},
            "nm": "Shape",
        }

    # Flatten all contours into one vertex list (multi-contour → merged shape).
    anchors: list[float] = []
    in_t: list[float] = []
    out_t: list[float] = []
    starts = [*list(contour_starts), arr.shape[0]]
    for ci in range(len(contour_starts)):
        start = contour_starts[ci]
        end = starts[ci + 1]
        if end - start < 1:
            continue
        n_seg = (end - start - 1) // 3
        verts = [arr[start + 3 * m] for m in range(n_seg + 1)]
        for vi, vertex in enumerate(verts):
            anchors.extend([float(vertex[0]), float(vertex[1])])
            # Out-tangent of this vertex.
            if vi < n_seg:
                h1 = arr[start + 1 + 3 * vi]
                out_t.extend([float(h1[0] - vertex[0]), float(h1[1] - vertex[1])])
            else:
                out_t.extend([0.0, 0.0])
            # In-tangent of this vertex.
            if vi > 0:
                h2 = arr[start + 2 + 3 * (vi - 1)]
                in_t.extend([float(h2[0] - vertex[0]), float(h2[1] - vertex[1])])
            else:
                in_t.extend([0.0, 0.0])

    return {
        "ty": "sh",
        "ks": {"a": 0, "k": {"a": anchors, "i": in_t, "o": out_t, "c": True}},
        "nm": "Path",
    }


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
            kfs.append(
                {"t": round(a.end_time * fps), "s": [round(a.end_value * 100, 1)]}
            )
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
