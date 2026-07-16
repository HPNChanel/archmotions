"""Animated SVG export for v2.0 scenes (pure Python — no skia).

Emits a self-contained ``<svg>`` whose shapes are derived from each
:class:`~archmotion.core.vmobject.VMobject`'s final resolved state, plus CSS
``@keyframes`` for the opacity / fill / stroke / transform animations in the
timeline. Point morphs (``Transform``) are represented by their end state
(SVG/CSS cannot easily keyframe arbitrary point arrays without JS).
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

import numpy as np

from archmotion.core.property import Property, PropertyAction
from archmotion.core.vmobject import VMobject
from archmotion.render.path_render import (
    DEFAULT_BACKGROUND_RGBA,
    resolve_effective,
    theme_style_for,
)

if TYPE_CHECKING:
    from archmotion.core.scene import Scene


def build_svg(scene: Scene, *, title: str = "ArchMotion Scene") -> str:
    """Build a self-contained animated SVG string for ``scene``."""
    timeline = scene.compile_timeline()
    graphics = [g for g in scene.all_graphics() if isinstance(g, VMobject)]
    width, height = scene.resolution

    bg = _bg_hex(scene)
    shape_markup: list[str] = []
    keyframes: list[str] = []
    snapshot = timeline.snapshot_at(timeline.total_duration)

    for index, graphic in enumerate(graphics):
        cls = f"am{index}"
        final = resolve_effective(
            graphic,
            snapshot.scalars.get(graphic.id),
            snapshot.morphs.get(graphic.id),
            scene.camera,
            theme_style_for(graphic, scene.theme),
            scalar_lookup=snapshot.scalars,
            morph_contour_starts=snapshot.morph_contours.get(graphic.id),
        )
        d = _points_to_svg_d(final.points, final.contour_starts)
        transform = _matrix_attr(final.matrix)
        shape_markup.append(
            f'  <path class="{cls}" d="{d}" fill="{final.fill_color}" '
            f'fill-opacity="{_fmt(final.fill_opacity)}" stroke="{final.stroke_color}" '
            f'stroke-width="{_fmt(final.stroke_width)}" '
            f'stroke-opacity="{_fmt(final.stroke_opacity)}" '
            f'opacity="{_fmt(final.opacity)}" transform="{transform}" />'
        )
        kf = _keyframes_for(
            graphic.id,
            cls,
            timeline.property_actions,
            timeline.total_duration,
        )
        if kf:
            keyframes.append(kf)

    css = "\n".join(keyframes)
    style_block = f"<style>\n{css}\n</style>\n" if css else ""

    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f"  <title>{escape(title)}</title>\n"
        f'  <rect width="{width}" height="{height}" fill="{bg}" />\n'
        f"{style_block}" + "\n".join(shape_markup) + "\n</svg>\n"
    )


def _points_to_svg_d(points: object, contour_starts: list[int]) -> str:
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    if pts.shape[0] == 0:
        return ""
    starts = [*list(contour_starts), pts.shape[0]]
    parts: list[str] = []
    for ci in range(len(contour_starts)):
        start = contour_starts[ci]
        end = starts[ci + 1]
        if end <= start:
            continue
        parts.append(f"M{_fmt(pts[start][0])},{_fmt(pts[start][1])}")
        j = start + 1
        while j + 2 < end:
            parts.append(
                f"C{_fmt(pts[j][0])},{_fmt(pts[j][1])} "
                f"{_fmt(pts[j + 1][0])},{_fmt(pts[j + 1][1])} "
                f"{_fmt(pts[j + 2][0])},{_fmt(pts[j + 2][1])}"
            )
            j += 3
        if j < end:
            parts.append(f"L{_fmt(pts[j][0])},{_fmt(pts[j][1])}")
        if _is_closed(pts, start, end):
            parts.append("Z")
    return " ".join(parts)


def _matrix_attr(matrix: object) -> str:
    m = np.asarray(matrix, dtype=np.float64)
    a, b = m[0][0], m[1][0]
    c, d = m[0][1], m[1][1]
    e, f = m[0][2], m[1][2]
    return f"matrix({_fmt(a)},{_fmt(b)},{_fmt(c)},{_fmt(d)},{_fmt(e)},{_fmt(f)})"


def _keyframes_for(
    target_id: str,
    cls: str,
    actions: tuple[PropertyAction, ...],
    duration: float,
) -> str:
    """Emit CSS @keyframes for opacity/fill on a single graphic."""
    opacity_kfs: list[str] = []
    for a in actions:
        if a.target_id != target_id:
            continue
        if a.prop == Property.OPACITY:
            opacity_kfs.append(f"{_pct(a.start_time, duration)}{{opacity:{_fmt(a.start_value)}}}")
            opacity_kfs.append(f"{_pct(a.end_time, duration)}{{opacity:{_fmt(a.end_value)}}}")
    out: list[str] = []
    if opacity_kfs and duration > 0:
        rule = (
            f"@keyframes {cls}_op {{ {' '.join(opacity_kfs)} }}\n"
            f".{cls} {{ animation: {cls}_op {_fmt(duration)}s ease both; }}"
        )
        out.append(rule)
    return "\n".join(out)


def _is_closed(points: object, start: int, end: int) -> bool:
    """Infer whether the final cubic returns to the contour's first anchor."""
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    return end - start >= 4 and bool(np.allclose(pts[start], pts[end - 1]))


def _pct(t: float, duration: float) -> str:
    if duration <= 0:
        return "0%"
    return f"{max(0.0, min(1.0, t / duration)) * 100:.1f}%"


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _bg_hex(scene: Scene) -> str:
    theme = getattr(scene, "theme", None)
    rgba = getattr(theme, "background_rgba", None) if theme is not None else None
    if rgba is None:
        rgba = DEFAULT_BACKGROUND_RGBA
    r = round(rgba[0] * 255)
    g = round(rgba[1] * 255)
    b = round(rgba[2] * 255)
    return f"#{r:02x}{g:02x}{b:02x}"
