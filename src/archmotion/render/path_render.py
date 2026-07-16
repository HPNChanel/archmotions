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
    from archmotion.core.graphic import Graphic
    from archmotion.core.style import Style
    from archmotion.core.vmobject import VMobject
    from archmotion.render.theme import ThemeConfig


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
    *,
    scalar_lookup: dict[str, dict[Property, float]] | None = None,
    morph_contour_starts: tuple[int, ...] | None = None,
) -> EffectiveState:
    """Compute the effective render state for a graphic at one timestamp."""
    scalars = scalars or {}

    raw_points = graphic.points
    if morph_points is not None:
        pts = np.asarray(morph_points, dtype=np.float64).reshape(-1, 2)
    else:
        pts = raw_points

    contour_starts = list(morph_contour_starts) if morph_contour_starts else graphic.contour_starts

    lookup = scalar_lookup or {graphic.id: scalars}
    family = [*graphic.ancestors(), graphic]

    # Compose local transforms recursively.  Full affine components emitted by
    # ``.animate`` override the authored (already-final) local transform at the
    # requested timestamp, preserving parent/child hierarchy.
    world = Transform.identity()
    for member in family:
        member_scalars = lookup.get(member.id, {})
        world = world.compose(_local_transform(member, member_scalars))

    # Legacy recipe properties (scale/rotation/absolute position) are post-world
    # transforms.  Applying ancestor transforms first makes group animations
    # affect every descendant without duplicating timeline actions.
    post = Transform.identity()
    for member in family:
        member_scalars = lookup.get(member.id, {})
        post = post.compose(_legacy_animation_transform(member, member_scalars))

    final = camera.view.compose(post).compose(world)

    style = graphic.style
    defaults = theme_defaults

    opacity = 1.0
    for member in family:
        member_scalars = lookup.get(member.id, {})
        opacity *= member_scalars.get(Property.OPACITY, member.opacity)
    fill_color = _resolve_color(
        scalars,
        Property.FILL_R,
        Property.FILL_G,
        Property.FILL_B,
        _inherited_color(family, "fill_color"),
        defaults,
    )
    fill_opacity = scalars.get(
        Property.FILL_OPACITY,
        _inherited_product(family, "fill_opacity"),
    )
    stroke_color = _resolve_color(
        scalars,
        Property.STROKE_R,
        Property.STROKE_G,
        Property.STROKE_B,
        _inherited_color(family, "stroke_color"),
        defaults,
    )
    inherited_stroke_width = _inherited_value(family, "stroke_width", style.stroke_width)
    stroke_width = scalars.get(Property.STROKE_WIDTH, inherited_stroke_width)
    stroke_opacity = scalars.get(
        Property.STROKE_OPACITY,
        _inherited_product(family, "stroke_opacity"),
    )
    glow_color = _inherited_color(family, "glow_color")
    glow_intensity = scalars.get(Property.GLOW_INTENSITY, 0.0 if style.glow_blur <= 0 else 1.0)
    create_progress = min(
        (lookup.get(member.id, {}).get(Property.CREATE_PROGRESS, 1.0) for member in family),
        default=1.0,
    )

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


_AFFINE_PROPS = (
    Property.TRANSFORM_A,
    Property.TRANSFORM_B,
    Property.TRANSFORM_C,
    Property.TRANSFORM_D,
    Property.TRANSFORM_TX,
    Property.TRANSFORM_TY,
)


def _local_transform(
    graphic: Graphic,
    scalars: dict[Property, float],
) -> Transform:
    """Resolve a graphic's authored or timeline-overridden local transform."""
    if not any(prop in scalars for prop in _AFFINE_PROPS):
        return graphic.transform
    matrix = np.asarray(graphic.transform.matrix, dtype=np.float64).copy()
    defaults = (
        matrix[0, 0],
        matrix[1, 0],
        matrix[0, 1],
        matrix[1, 1],
        matrix[0, 2],
        matrix[1, 2],
    )
    a, b, c, d, tx, ty = (
        scalars.get(prop, float(default))
        for prop, default in zip(_AFFINE_PROPS, defaults, strict=True)
    )
    return Transform([[a, c, tx], [b, d, ty], [0.0, 0.0, 1.0]])


def _legacy_animation_transform(
    graphic: Graphic,
    scalars: dict[Property, float],
) -> Transform:
    """Resolve recipe-scale/rotation/position properties in canvas space."""
    bbox = graphic.bounding_box()
    cx, cy = bbox.center
    pos_x = scalars.get(Property.POSITION_X)
    pos_y = scalars.get(Property.POSITION_Y)
    progress = scalars.get(Property.PATH_PROGRESS)
    if progress is not None:
        connection = getattr(graphic, "connection", None)
        if connection is not None:
            route_x, route_y = connection.point_at_progress(progress)
            pos_x = route_x if pos_x is None else pos_x
            pos_y = route_y if pos_y is None else pos_y

    transform = Transform.identity()
    if pos_x is not None or pos_y is not None:
        transform = Transform.translation(
            (pos_x - cx) if pos_x is not None else 0.0,
            (pos_y - cy) if pos_y is not None else 0.0,
        ).compose(transform)
    scale = scalars.get(Property.SCALE, 1.0)
    rotation = scalars.get(Property.ROTATION, 0.0)
    if abs(scale - 1.0) > 1e-6 or abs(rotation) > 1e-6:
        around_center = (
            Transform.translation(cx, cy)
            .compose(Transform.rotation(rotation))
            .compose(Transform.scaling(scale))
            .compose(Transform.translation(-cx, -cy))
        )
        transform = around_center.compose(transform)
    return transform


def _inherited_color(family: list[Graphic], field: str) -> str | None:
    """Return the nearest explicitly configured color in the family chain."""
    for member in reversed(family):
        value = getattr(member.style, field)
        if value is not None:
            return str(value)
    return None


def _inherited_product(family: list[Graphic], field: str) -> float:
    """Multiply alpha-like style fields through the family chain."""
    value = 1.0
    for member in family:
        value *= float(getattr(member.style, field))
    return value


def _inherited_value(family: list[Graphic], field: str, fallback: float) -> float:
    """Use a parent's value when that parent explicitly supplies the style."""
    for member in reversed(family[:-1]):
        style = member.style
        if style.stroke_color is not None:
            return float(getattr(style, field))
    return float(fallback)


def theme_style_for(graphic: Graphic, theme: ThemeConfig | None) -> Style | None:
    """Map theme tokens to a domain-aware fallback Style."""
    if theme is None:
        return None
    from archmotion.core.style import Style
    from archmotion.domains.architecture.connections import Connection
    from archmotion.domains.architecture.packet import Packet
    from archmotion.domains.architecture.primitives import Database, Node
    from archmotion.domains.text.text import Text

    if isinstance(graphic, Text):
        return Style(
            fill_color=theme.font_color,
            stroke_color=None,
            stroke_width=0.0,
        )
    if isinstance(graphic, Packet):
        return Style(
            fill_color=theme.packet_color,
            stroke_color=theme.packet_color,
            stroke_width=1.0,
        )
    if isinstance(graphic, Connection):
        return Style(
            fill_color=theme.conn_stroke,
            fill_opacity=0.0,
            stroke_color=theme.conn_stroke,
            stroke_width=theme.conn_stroke_width,
        )
    if isinstance(graphic, Database):
        return Style(
            fill_color=theme.db_fill,
            stroke_color=theme.db_border,
            stroke_width=theme.node_border_width,
        )
    if isinstance(graphic, Node):
        return Style(
            fill_color=theme.node_fill,
            stroke_color=theme.node_border,
            stroke_width=theme.node_border_width,
        )
    return Style(fill_color=theme.node_fill, stroke_color=theme.node_border)


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
                float(pts[j][0]),
                float(pts[j][1]),
                float(pts[j + 1][0]),
                float(pts[j + 1][1]),
                float(pts[j + 2][0]),
                float(pts[j + 2][1]),
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
        float(matrix[0][0]),
        float(matrix[0][1]),
        float(matrix[0][2]),
        float(matrix[1][0]),
        float(matrix[1][1]),
        float(matrix[1][2]),
        0.0,
        0.0,
        1.0,
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
    """Return the first fraction of a path across all of its contours."""
    import skia

    measure = skia.PathMeasure(path, False)
    lengths: list[float] = []
    while True:
        lengths.append(float(measure.getLength()))
        if not measure.nextContour():
            break
    total = sum(lengths)
    if total <= 0:
        return path
    remaining = total * max(0.0, min(1.0, progress))
    dst = skia.Path()
    measure = skia.PathMeasure(path, False)
    for length in lengths:
        take = min(length, remaining)
        if take > 0:
            measure.getSegment(0.0, take, dst, True)
        remaining -= take
        if remaining <= 0 or not measure.nextContour():
            break
    return dst


def _hex4f(hex_color: str, opacity: float = 1.0) -> object:
    from archmotion.render.canvas import hex_to_color4f

    return hex_to_color4f(hex_color, opacity)
