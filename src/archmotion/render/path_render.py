"""Generic vector-graphic renderer (v2.0).

Replaces v1.0's per-type painter functions with ONE renderer that paints any
:class:`~archmotion.core.vmobject.VMobject` from its Bezier point array. Two
layers:

- :func:`resolve_effective` — pure-Python/numpy: computes the per-graphic
  effective points, affine matrix, opacity and resolved style from the graphic's
  base state + a timeline snapshot. **Skia-free and unit-testable.**
- :func:`paint_effective` — the skia draw calls (lazy import, exercised in CI).

The transform composes as ``camera.view ∘ animScale ∘ animRotate ∘ animTranslate
∘ graphic.transform`` so authored transforms and animated transforms combine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from archmotion.core.property import Property
from archmotion.core.transform import Transform

if TYPE_CHECKING:
    from archmotion.core.camera import Camera
    from archmotion.core.style import Style
    from archmotion.core.vmobject import VMobject


DEFAULT_FILL = "#3b82f6"
DEFAULT_STROKE = "#e5e7eb"
DEFAULT_BACKGROUND_RGBA = (0.06, 0.07, 0.10, 1.0)


@dataclass
class EffectiveState:
    """Everything needed to paint one graphic at one timestamp."""

    points: object  # NDArray (N, 2)
    contour_starts: list[int]
    matrix: object  # 3x3 affine (NDArray)
    opacity: float
    fill_color: str
    fill_opacity: float
    stroke_color: str
    stroke_width: float
    stroke_opacity: float
    glow_color: str | None
    glow_intensity: float
    create_progress: float


def resolve_effective(
    graphic: VMobject,
    scalars: dict[Property, float] | None,
    morph_points: object | None,
    camera: Camera,
    theme_defaults: Style | None = None,
) -> EffectiveState:
    """Compute the effective render state for a graphic at one timestamp."""
    scalars = scalars or {}

    raw_points = graphic.points
    if morph_points is not None:
        pts = np.asarray(morph_points, dtype=np.float64).reshape(-1, 2)
    else:
        pts = raw_points

    contour_starts = graphic.contour_starts

    # Authored transform applied to points (for center computation).
    authored_matrix = graphic.transform.matrix

    # Center of the (authored-transformed) points for animated scale/rotate.
    if pts.shape[0] > 0:
        authored_pts = Transform(authored_matrix).apply_to_points(pts)
        cx = float(authored_pts[:, 0].mean())
        cy = float(authored_pts[:, 1].mean())
    else:
        cx, cy = 0.0, 0.0

    anim = Transform.identity()
    pos_x = scalars.get(Property.POSITION_X)
    pos_y = scalars.get(Property.POSITION_Y)
    # A packet travelling along a connection derives its position from
    # PATH_PROGRESS (its connection's resolved route).
    path_progress = scalars.get(Property.PATH_PROGRESS)
    if path_progress is not None:
        connection = getattr(graphic, "connection", None)
        if connection is not None:
            route_x, route_y = connection.point_at_progress(path_progress)
            if pos_x is None:
                pos_x = route_x
            if pos_y is None:
                pos_y = route_y
    if pos_x is not None or pos_y is not None:
        tx = pos_x - cx if pos_x is not None else 0.0
        ty = pos_y - cy if pos_y is not None else 0.0
        anim = Transform.translation(tx, ty).compose(anim)

    scale = scalars.get(Property.SCALE)
    if scale is not None and abs(scale - 1.0) > 1e-6:
        to_origin = Transform.translation(-cx, -cy)
        back = Transform.translation(cx, cy)
        anim = back.compose(Transform.scaling(scale)).compose(to_origin).compose(anim)

    rotation = scalars.get(Property.ROTATION)
    if rotation is not None and abs(rotation) > 1e-6:
        to_origin = Transform.translation(-cx, -cy)
        back = Transform.translation(cx, cy)
        anim = back.compose(Transform.rotation(rotation)).compose(to_origin).compose(anim)

    final = camera.view.compose(anim).compose(graphic.transform)

    style = graphic.style
    defaults = theme_defaults

    opacity = scalars.get(Property.OPACITY, graphic.opacity)
    fill_color = _resolve_color(
        scalars, Property.FILL_R, Property.FILL_G, Property.FILL_B, style.fill_color, defaults
    )
    fill_opacity = scalars.get(Property.FILL_OPACITY, style.fill_opacity)
    stroke_color = _resolve_color(
        scalars,
        Property.STROKE_R,
        Property.STROKE_G,
        Property.STROKE_B,
        style.stroke_color,
        defaults,
    )
    stroke_width = scalars.get(Property.STROKE_WIDTH, style.stroke_width)
    stroke_opacity = scalars.get(Property.STROKE_OPACITY, style.stroke_opacity)
    glow_color = style.glow_color
    glow_intensity = scalars.get(Property.GLOW_INTENSITY, 0.0 if style.glow_blur <= 0 else 1.0)
    create_progress = scalars.get(Property.CREATE_PROGRESS, 1.0)

    return EffectiveState(
        points=pts,
        contour_starts=contour_starts,
        matrix=final.matrix,
        opacity=opacity,
        fill_color=fill_color,
        fill_opacity=fill_opacity,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        stroke_opacity=stroke_opacity,
        glow_color=glow_color,
        glow_intensity=glow_intensity,
        create_progress=create_progress,
    )


def _resolve_color(
    scalars: dict[Property, float],
    r_prop: Property,
    g_prop: Property,
    b_prop: Property,
    fallback: str | None,
    defaults: Style | None,
) -> str:
    if r_prop in scalars or g_prop in scalars or b_prop in scalars:
        r = round(scalars.get(r_prop, 1.0) * 255)
        g = round(scalars.get(g_prop, 1.0) * 255)
        b = round(scalars.get(b_prop, 1.0) * 255)
        return f"#{_clamp(r):02x}{_clamp(g):02x}{_clamp(b):02x}"
    if fallback is not None:
        return fallback
    if defaults is not None:
        if r_prop == Property.FILL_R and defaults.fill_color:
            return defaults.fill_color
        if r_prop == Property.STROKE_R and defaults.stroke_color:
            return defaults.stroke_color
    return DEFAULT_FILL if r_prop == Property.FILL_R else DEFAULT_STROKE


def _clamp(v: int) -> int:
    return max(0, min(255, v))


# ── skia painting (lazy) ─────────────────────────────────────────


def build_skia_path(points: object, contour_starts: list[int]) -> object:
    """Build a ``skia.Path`` from a point array + contour starts."""
    import skia

    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    path = skia.Path()
    starts = [*list(contour_starts), pts.shape[0]]
    for ci in range(len(contour_starts)):
        start = contour_starts[ci]
        end = starts[ci + 1]
        if end <= start:
            continue
        path.moveTo(float(pts[start][0]), float(pts[start][1]))
        j = start + 1
        while j + 2 < end:
            path.cubicTo(
                float(pts[j][0]), float(pts[j][1]),
                float(pts[j + 1][0]), float(pts[j + 1][1]),
                float(pts[j + 2][0]), float(pts[j + 2][1]),
            )
            j += 3
        if j < end:
            path.lineTo(float(pts[j][0]), float(pts[j][1]))
    return path


def paint_effective(native: Any, state: EffectiveState) -> None:  # noqa: ANN401
    """Paint one resolved graphic onto a raw ``skia.Canvas`` (native)."""
    import skia

    pts = np.asarray(state.points, dtype=np.float64).reshape(-1, 2)
    if pts.shape[0] < 2:
        return

    path = build_skia_path(state.points, state.contour_starts)

    # Create animation: trim the path to draw only `create_progress`.
    if state.create_progress < 0.999:
        path = _trim_path(path, state.create_progress)

    # Opacity layer.
    needs_layer = state.opacity < 0.999
    if needs_layer:
        paint_alpha = skia.Paint()
        paint_alpha.setAlphaf(state.opacity)
        native.saveLayer(None, paint_alpha)

    matrix = np.asarray(state.matrix, dtype=np.float64)
    m = [
        float(matrix[0][0]), float(matrix[0][1]), float(matrix[0][2]),
        float(matrix[1][0]), float(matrix[1][1]), float(matrix[1][2]),
        0.0, 0.0, 1.0,
    ]
    native.save()
    native.concat(skia.Matrix(m))

    # Glow halo.
    if state.glow_color and state.glow_intensity > 0.01:
        glow = skia.Paint()
        glow.setAntiAlias(True)
        glow.setColor4f(_hex4f(state.glow_color, state.glow_intensity * 0.5))
        glow.setStyle(skia.Paint.kStroke_Style)
        glow.setStrokeWidth(state.stroke_width + 8.0)
        glow.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 8.0))
        native.drawPath(path, glow)

    # Fill.
    if state.fill_opacity > 0.01 and state.fill_color:
        fill = skia.Paint()
        fill.setAntiAlias(True)
        fill.setColor4f(_hex4f(state.fill_color, state.fill_opacity))
        fill.setStyle(skia.Paint.kFill_Style)
        native.drawPath(path, fill)

    # Stroke.
    if state.stroke_opacity > 0.01 and state.stroke_width > 0 and state.stroke_color:
        stroke = skia.Paint()
        stroke.setAntiAlias(True)
        stroke.setColor4f(_hex4f(state.stroke_color, state.stroke_opacity))
        stroke.setStyle(skia.Paint.kStroke_Style)
        stroke.setStrokeWidth(state.stroke_width)
        stroke.setStrokeJoin(skia.Paint.kRound_Join)
        native.drawPath(path, stroke)

    native.restore()
    if needs_layer:
        native.restore()


def _trim_path(path: object, progress: float) -> object:
    """Return the first ``progress`` fraction of a skia path (for Create)."""
    import skia

    measure = skia.PathMeasure(path, False)
    total = measure.getLength()
    if total <= 0:
        return path
    dst = skia.Path()
    measure.getSegment(0.0, total * max(0.0, min(1.0, progress)), dst, True)
    return dst


def _hex4f(hex_color: str, opacity: float = 1.0) -> object:
    from archmotion.render.canvas import hex_to_color4f

    return hex_to_color4f(hex_color, opacity)
