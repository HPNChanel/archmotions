"""Painter functions for drawing scene objects onto Skia canvas.

Architectural Note:
    Each painter draws a specific primitive type using Skia commands.
    Painters are stateless functions that receive:
        - SkiaCanvas (for draw calls)
        - BoundingBox (position + size)
        - ThemeConfig (colors + fonts)
        - opacity (from animated OPACITY property)

    Z-index ordering is handled by the frame renderer calling
    painters in the correct order (connections -> nodes -> effects).

    This module does NOT import skia directly -- it uses SkiaCanvas
    and the color utilities from canvas.py.
"""

from __future__ import annotations

import math

import skia

from archmotion._types import Point
from archmotion.layout.bbox import BoundingBox
from archmotion.renderer.canvas import SkiaCanvas, hex_to_color4f, make_font
from archmotion.renderer.theme import ThemeConfig


# ──────────────────────────────────────────────
# Node Painter
# ──────────────────────────────────────────────


def paint_node(
    canvas: SkiaCanvas,
    bbox: BoundingBox,
    label: str,
    theme: ThemeConfig,
    opacity: float = 1.0,
    glow_intensity: float = 0.0,
) -> None:
    """Draw a rectangular node with shadow, fill, border, and label.

    Args:
        canvas: SkiaCanvas wrapper.
        bbox: Absolute pixel BoundingBox.
        label: Node label text.
        theme: Visual theme config.
        opacity: Node opacity [0.0, 1.0] from FadeIn/FadeOut.
        glow_intensity: Pulse glow intensity [0.0, 1.0].
    """
    native = canvas.native
    rect = skia.Rect.MakeXYWH(bbox.x, bbox.y, bbox.width, bbox.height)
    radius = theme.node_corner_radius

    # Opacity layer
    if opacity < 1.0:
        canvas.save_layer(opacity)

    # Shadow
    sdx, sdy = theme.node_shadow_offset
    shadow_rect = skia.Rect.MakeXYWH(
        bbox.x + sdx, bbox.y + sdy, bbox.width, bbox.height,
    )
    shadow_paint = skia.Paint()
    shadow_paint.setAntiAlias(True)
    shadow_paint.setColor4f(hex_to_color4f(theme.node_shadow_color))
    native.drawRoundRect(shadow_rect, radius, radius, shadow_paint)

    # Fill
    fill_paint = skia.Paint()
    fill_paint.setAntiAlias(True)
    fill_paint.setColor4f(hex_to_color4f(theme.node_fill))
    native.drawRoundRect(rect, radius, radius, fill_paint)

    # Border
    border_paint = skia.Paint()
    border_paint.setAntiAlias(True)
    border_paint.setColor4f(hex_to_color4f(theme.node_border))
    border_paint.setStyle(skia.Paint.kStroke_Style)
    border_paint.setStrokeWidth(theme.node_border_width)
    native.drawRoundRect(rect, radius, radius, border_paint)

    # Label (centered)
    font = make_font(theme.font_family, theme.font_size)
    text_paint = skia.Paint()
    text_paint.setAntiAlias(True)
    text_paint.setColor4f(hex_to_color4f(theme.font_color))

    text_width = font.measureText(label)
    text_x = bbox.x + (bbox.width - text_width) / 2
    text_y = bbox.y + bbox.height / 2 + theme.font_size * 0.35
    native.drawString(label, text_x, text_y, font, text_paint)

    # Glow effect (Pulse)
    if glow_intensity > 0.01:
        _paint_glow(native, bbox, theme, glow_intensity)

    if opacity < 1.0:
        canvas.restore()


# ──────────────────────────────────────────────
# Database Painter
# ──────────────────────────────────────────────


def paint_database(
    canvas: SkiaCanvas,
    bbox: BoundingBox,
    label: str,
    theme: ThemeConfig,
    opacity: float = 1.0,
    glow_intensity: float = 0.0,
) -> None:
    """Draw a cylinder-shaped database node.

    The cylinder is composed of:
        - A rectangle body
        - An elliptical top cap
        - An elliptical bottom cap
        - Label text centered in the body

    Args:
        canvas: SkiaCanvas wrapper.
        bbox: Absolute pixel BoundingBox.
        label: Database label text.
        theme: Visual theme config.
        opacity: Opacity from animation.
        glow_intensity: Pulse glow intensity.
    """
    native = canvas.native
    cap_height = bbox.height * 0.15  # Ellipse cap height

    if opacity < 1.0:
        canvas.save_layer(opacity)

    # Shadow
    sdx, sdy = theme.node_shadow_offset
    shadow_paint = skia.Paint()
    shadow_paint.setAntiAlias(True)
    shadow_paint.setColor4f(hex_to_color4f(theme.node_shadow_color))
    shadow_rect = skia.Rect.MakeXYWH(
        bbox.x + sdx, bbox.y + sdy + cap_height,
        bbox.width, bbox.height - cap_height,
    )
    native.drawRect(shadow_rect, shadow_paint)

    # Body fill (rectangle between caps)
    body_rect = skia.Rect.MakeXYWH(
        bbox.x, bbox.y + cap_height,
        bbox.width, bbox.height - 2 * cap_height,
    )
    fill_paint = skia.Paint()
    fill_paint.setAntiAlias(True)
    fill_paint.setColor4f(hex_to_color4f(theme.db_fill))
    native.drawRect(body_rect, fill_paint)

    # Bottom ellipse cap
    bottom_oval = skia.Rect.MakeXYWH(
        bbox.x, bbox.y + bbox.height - 2 * cap_height,
        bbox.width, 2 * cap_height,
    )
    native.drawOval(bottom_oval, fill_paint)

    # Top ellipse cap (filled)
    top_oval = skia.Rect.MakeXYWH(
        bbox.x, bbox.y, bbox.width, 2 * cap_height,
    )
    native.drawOval(top_oval, fill_paint)

    # Top ellipse border
    border_paint = skia.Paint()
    border_paint.setAntiAlias(True)
    border_paint.setColor4f(hex_to_color4f(theme.db_border))
    border_paint.setStyle(skia.Paint.kStroke_Style)
    border_paint.setStrokeWidth(theme.node_border_width)
    native.drawOval(top_oval, border_paint)

    # Body side borders
    native.drawLine(
        bbox.x, bbox.y + cap_height,
        bbox.x, bbox.y + bbox.height - cap_height,
        border_paint,
    )
    native.drawLine(
        bbox.x + bbox.width, bbox.y + cap_height,
        bbox.x + bbox.width, bbox.y + bbox.height - cap_height,
        border_paint,
    )

    # Bottom ellipse border
    native.drawOval(bottom_oval, border_paint)

    # Label (centered in body)
    font = make_font(theme.font_family, theme.font_size)
    text_paint = skia.Paint()
    text_paint.setAntiAlias(True)
    text_paint.setColor4f(hex_to_color4f(theme.font_color))

    text_width = font.measureText(label)
    text_x = bbox.x + (bbox.width - text_width) / 2
    text_y = bbox.y + bbox.height / 2 + theme.font_size * 0.35
    native.drawString(label, text_x, text_y, font, text_paint)

    # Glow effect
    if glow_intensity > 0.01:
        _paint_glow(native, bbox, theme, glow_intensity)

    if opacity < 1.0:
        canvas.restore()


# ──────────────────────────────────────────────
# Connection Painter
# ──────────────────────────────────────────────


def paint_connection(
    canvas: SkiaCanvas,
    route: list[Point],
    label: str | None,
    theme: ThemeConfig,
    opacity: float = 1.0,
) -> None:
    """Draw a connection polyline with optional arrowhead and label.

    Args:
        canvas: SkiaCanvas wrapper.
        route: List of (x, y) points from Manhattan routing.
        label: Optional connection label text.
        theme: Visual theme config.
        opacity: Opacity from animation.
    """
    if len(route) < 2:
        return

    native = canvas.native

    if opacity < 1.0:
        canvas.save_layer(opacity)

    # Line segments
    line_paint = skia.Paint()
    line_paint.setAntiAlias(True)
    line_paint.setColor4f(hex_to_color4f(theme.conn_stroke))
    line_paint.setStrokeWidth(theme.conn_stroke_width)
    line_paint.setStyle(skia.Paint.kStroke_Style)
    line_paint.setStrokeCap(skia.Paint.kRound_Cap)
    line_paint.setStrokeJoin(skia.Paint.kRound_Join)

    # Rounded corners for Manhattan routing bends
    if theme.conn_corner_radius > 0.01:
        line_paint.setPathEffect(skia.CornerPathEffect.Make(theme.conn_corner_radius))

    path = skia.Path()
    path.moveTo(*route[0])
    for point in route[1:]:
        path.lineTo(*point)
    native.drawPath(path, line_paint)

    # Arrowhead at the last segment
    _paint_arrowhead(native, route[-2], route[-1], theme)

    # Label at midpoint of the route
    if label:
        mid_idx = len(route) // 2
        if mid_idx > 0:
            mx = (route[mid_idx - 1][0] + route[mid_idx][0]) / 2
            my = (route[mid_idx - 1][1] + route[mid_idx][1]) / 2
        else:
            mx, my = route[0]

        font = make_font(theme.font_family, theme.packet_label_size)
        label_paint = skia.Paint()
        label_paint.setAntiAlias(True)
        label_paint.setColor4f(hex_to_color4f(theme.font_color, opacity=0.7))

        text_width = font.measureText(label)
        native.drawString(label, mx - text_width / 2, my - 8, font, label_paint)

    if opacity < 1.0:
        canvas.restore()


def _paint_arrowhead(
    native: skia.Canvas,
    from_pt: Point,
    to_pt: Point,
    theme: ThemeConfig,
) -> None:
    """Draw a filled triangle arrowhead at the end of a connection.

    Args:
        native: Raw skia.Canvas.
        from_pt: Second-to-last point (direction reference).
        to_pt: Last point (arrow tip).
        theme: Theme config for arrow size and color.
    """
    dx = to_pt[0] - from_pt[0]
    dy = to_pt[1] - from_pt[1]
    length = math.sqrt(dx * dx + dy * dy)

    if length < 0.01:
        return

    # Normalize direction
    ux = dx / length
    uy = dy / length

    # Arrow wings (perpendicular to direction)
    arrow_size = theme.conn_arrow_size
    wing1_x = to_pt[0] - ux * arrow_size - uy * arrow_size * 0.4
    wing1_y = to_pt[1] - uy * arrow_size + ux * arrow_size * 0.4
    wing2_x = to_pt[0] - ux * arrow_size + uy * arrow_size * 0.4
    wing2_y = to_pt[1] - uy * arrow_size - ux * arrow_size * 0.4

    path = skia.Path()
    path.moveTo(to_pt[0], to_pt[1])
    path.lineTo(wing1_x, wing1_y)
    path.lineTo(wing2_x, wing2_y)
    path.close()

    paint = skia.Paint()
    paint.setAntiAlias(True)
    paint.setColor4f(hex_to_color4f(theme.conn_stroke))
    native.drawPath(path, paint)


# ──────────────────────────────────────────────
# Packet Painter
# ──────────────────────────────────────────────


def paint_packet(
    canvas: SkiaCanvas,
    position: Point,
    payload: str,
    theme: ThemeConfig,
    packet_color: str | None = None,
    opacity: float = 1.0,
) -> None:
    """Draw a packet circle at a position along a connection path.

    Args:
        canvas: SkiaCanvas wrapper.
        position: Current (x, y) position on the path.
        payload: Text label for the packet.
        theme: Visual theme config.
        packet_color: Override color (None = theme default).
        opacity: Packet opacity.
    """
    native = canvas.native
    color_hex = packet_color or theme.packet_color
    radius = theme.packet_size / 2

    if opacity < 1.0:
        canvas.save_layer(opacity)

    # Glow halo
    glow_paint = skia.Paint()
    glow_paint.setAntiAlias(True)
    glow_paint.setColor4f(hex_to_color4f(color_hex, opacity=0.3))
    native.drawCircle(position[0], position[1], radius * 2.5, glow_paint)

    # Solid packet
    packet_paint = skia.Paint()
    packet_paint.setAntiAlias(True)
    packet_paint.setColor4f(hex_to_color4f(color_hex))
    native.drawCircle(position[0], position[1], radius, packet_paint)

    # Payload label above packet
    if payload:
        font = make_font(theme.font_family, theme.packet_label_size)
        text_paint = skia.Paint()
        text_paint.setAntiAlias(True)
        text_paint.setColor4f(hex_to_color4f(theme.font_color, opacity=0.9))

        text_width = font.measureText(payload)
        native.drawString(
            payload,
            position[0] - text_width / 2,
            position[1] - radius * 2.5 - 4,
            font,
            text_paint,
        )

    if opacity < 1.0:
        canvas.restore()


# ──────────────────────────────────────────────
# Glow Effect (shared by Node and Database)
# ──────────────────────────────────────────────


def _paint_glow(
    native: skia.Canvas,
    bbox: BoundingBox,
    theme: ThemeConfig,
    intensity: float,
) -> None:
    """Paint a glow halo around a bounding box (for Pulse animation).

    Args:
        native: Raw skia.Canvas.
        bbox: Node bounding box.
        theme: Theme config for glow radius.
        intensity: Glow intensity [0.0, 1.0].
    """
    glow_radius = theme.glow_blur_radius * intensity
    cx, cy = bbox.center

    # Radial glow circle
    glow_paint = skia.Paint()
    glow_paint.setAntiAlias(True)
    glow_paint.setColor4f(hex_to_color4f(theme.packet_color, opacity=intensity * 0.4))
    native.drawCircle(cx, cy, max(bbox.width, bbox.height) / 2 + glow_radius, glow_paint)


# ──────────────────────────────────────────────
# Path Interpolation (for Transfer packets)
# ──────────────────────────────────────────────


def interpolate_path(route: list[Point], progress: float) -> Point:
    """Compute position along a polyline at a given progress [0.0, 1.0].

    Used to determine where a Transfer packet should be drawn
    at a given frame timestamp.

    Args:
        route: Ordered list of (x, y) waypoints.
        progress: Normalized progress along the route [0.0, 1.0].

    Returns:
        Interpolated (x, y) position.
    """
    if not route:
        return (0.0, 0.0)
    if progress <= 0.0:
        return route[0]
    if progress >= 1.0:
        return route[-1]

    # Compute total path length
    segment_lengths: list[float] = []
    total_length = 0.0
    for i in range(len(route) - 1):
        dx = route[i + 1][0] - route[i][0]
        dy = route[i + 1][1] - route[i][1]
        seg_len = math.sqrt(dx * dx + dy * dy)
        segment_lengths.append(seg_len)
        total_length += seg_len

    if total_length < 0.01:
        return route[0]

    # Find which segment the progress falls in
    target_dist = progress * total_length
    accumulated = 0.0

    for i, seg_len in enumerate(segment_lengths):
        if accumulated + seg_len >= target_dist:
            # Interpolate within this segment
            local_progress = (target_dist - accumulated) / seg_len if seg_len > 0 else 0.0
            x = route[i][0] + (route[i + 1][0] - route[i][0]) * local_progress
            y = route[i][1] + (route[i + 1][1] - route[i][1]) * local_progress
            return (x, y)
        accumulated += seg_len

    return route[-1]


# ──────────────────────────────────────────────
# Cloud Painter (3-arc cloud shape)
# ──────────────────────────────────────────────


def paint_cloud(
    canvas: SkiaCanvas,
    bbox: BoundingBox,
    label: str,
    theme: ThemeConfig,
    opacity: float = 1.0,
    glow_intensity: float = 0.0,
) -> None:
    """Draw a cloud-shaped node with 3 arc humps on top and flat bottom.

    Args:
        canvas: SkiaCanvas wrapper.
        bbox: Absolute pixel BoundingBox.
        label: Cloud label text.
        theme: Visual theme config.
        opacity: Node opacity [0.0, 1.0].
        glow_intensity: Pulse glow intensity [0.0, 1.0].
    """
    native = canvas.native

    if opacity < 1.0:
        canvas.save_layer(opacity)

    # Cloud shape: 3 overlapping ellipses merged into a path
    cx = bbox.x + bbox.width / 2
    cy = bbox.y + bbox.height / 2
    w = bbox.width
    h = bbox.height

    path = skia.Path()

    # Bottom flat line
    bottom_y = bbox.y + h * 0.75
    top_y = bbox.y + h * 0.20

    # Start from bottom-left
    path.moveTo(bbox.x + w * 0.15, bottom_y)

    # Left arc (small bump)
    path.cubicTo(
        bbox.x - w * 0.05, bottom_y - h * 0.15,
        bbox.x - w * 0.05, top_y + h * 0.15,
        bbox.x + w * 0.20, top_y,
    )

    # Center-left arc (medium bump)
    path.cubicTo(
        bbox.x + w * 0.20, bbox.y - h * 0.05,
        bbox.x + w * 0.40, bbox.y - h * 0.05,
        cx, top_y - h * 0.05,
    )

    # Center-right arc (large bump — tallest)
    path.cubicTo(
        bbox.x + w * 0.60, bbox.y - h * 0.10,
        bbox.x + w * 0.85, bbox.y + h * 0.05,
        bbox.x + w * 0.85, top_y + h * 0.10,
    )

    # Right arc (drops down to bottom)
    path.cubicTo(
        bbox.x + w * 1.05, top_y + h * 0.20,
        bbox.x + w * 1.05, bottom_y - h * 0.10,
        bbox.x + w * 0.85, bottom_y,
    )

    # Close bottom
    path.lineTo(bbox.x + w * 0.15, bottom_y)
    path.close()

    # Glow effect
    if glow_intensity > 0:
        _draw_glow(native, path, theme, glow_intensity)

    # Shadow
    shadow_paint = skia.Paint()
    shadow_paint.setColor4f(skia.Color4f(0, 0, 0, 0.3))
    shadow_paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 4.0))
    shadow_paint.setAntiAlias(True)
    native.save()
    native.translate(2, 2)
    native.drawPath(path, shadow_paint)
    native.restore()

    # Fill
    fill_paint = skia.Paint()
    fill_paint.setColor4f(hex_to_color4f(theme.node_fill))
    fill_paint.setAntiAlias(True)
    native.drawPath(path, fill_paint)

    # Border
    border_paint = skia.Paint()
    border_paint.setColor4f(hex_to_color4f(theme.node_border))
    border_paint.setStyle(skia.Paint.kStroke_Style)
    border_paint.setStrokeWidth(theme.node_border_width)
    border_paint.setAntiAlias(True)
    native.drawPath(path, border_paint)

    # Label text (centered)
    if label:
        font = make_font(theme.font_family, theme.font_size)
        text_paint = skia.Paint()
        text_paint.setColor4f(hex_to_color4f(theme.font_color))
        text_paint.setAntiAlias(True)
        text_width = font.measureText(label)
        text_x = cx - text_width / 2
        text_y = cy + theme.font_size / 3
        native.drawString(label, text_x, text_y, font, text_paint)

    if opacity < 1.0:
        native.restore()


# ──────────────────────────────────────────────
# Queue Painter (parallelogram shape)
# ──────────────────────────────────────────────


def paint_queue(
    canvas: SkiaCanvas,
    bbox: BoundingBox,
    label: str,
    theme: ThemeConfig,
    opacity: float = 1.0,
    glow_intensity: float = 0.0,
) -> None:
    """Draw a parallelogram-shaped node representing a message queue.

    The parallelogram is skewed to the right, with small arrow indicators
    on left and right edges to suggest message flow direction.

    Args:
        canvas: SkiaCanvas wrapper.
        bbox: Absolute pixel BoundingBox.
        label: Queue label text.
        theme: Visual theme config.
        opacity: Node opacity [0.0, 1.0].
        glow_intensity: Pulse glow intensity [0.0, 1.0].
    """
    native = canvas.native

    if opacity < 1.0:
        canvas.save_layer(opacity)

    # Skew offset (how much the parallelogram leans)
    skew = bbox.width * 0.12

    # Build parallelogram path
    path = skia.Path()
    path.moveTo(bbox.x + skew, bbox.y)                          # Top-left (shifted right)
    path.lineTo(bbox.x + bbox.width, bbox.y)                    # Top-right
    path.lineTo(bbox.x + bbox.width - skew, bbox.y + bbox.height)  # Bottom-right (shifted left)
    path.lineTo(bbox.x, bbox.y + bbox.height)                   # Bottom-left
    path.close()

    # Glow
    if glow_intensity > 0:
        _draw_glow(native, path, theme, glow_intensity)

    # Shadow
    shadow_paint = skia.Paint()
    shadow_paint.setColor4f(skia.Color4f(0, 0, 0, 0.3))
    shadow_paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 4.0))
    shadow_paint.setAntiAlias(True)
    native.save()
    native.translate(2, 2)
    native.drawPath(path, shadow_paint)
    native.restore()

    # Fill
    fill_paint = skia.Paint()
    fill_paint.setColor4f(hex_to_color4f(theme.node_fill))
    fill_paint.setAntiAlias(True)
    native.drawPath(path, fill_paint)

    # Border
    border_paint = skia.Paint()
    border_paint.setColor4f(hex_to_color4f(theme.node_border))
    border_paint.setStyle(skia.Paint.kStroke_Style)
    border_paint.setStrokeWidth(theme.node_border_width)
    border_paint.setAntiAlias(True)
    native.drawPath(path, border_paint)

    # Arrow indicators (small chevrons on left and right edges)
    cx = bbox.x + bbox.width / 2
    cy = bbox.y + bbox.height / 2
    arrow_size = min(bbox.height * 0.15, 6.0)
    arrow_paint = skia.Paint()
    arrow_paint.setColor4f(hex_to_color4f(theme.font_color, opacity=0.5))
    arrow_paint.setStyle(skia.Paint.kStroke_Style)
    arrow_paint.setStrokeWidth(1.5)
    arrow_paint.setAntiAlias(True)

    # Right arrow on right edge
    rx = bbox.x + bbox.width - skew / 2 - arrow_size * 2
    native.drawLine(rx, cy - arrow_size, rx + arrow_size, cy, arrow_paint)
    native.drawLine(rx + arrow_size, cy, rx, cy + arrow_size, arrow_paint)

    # Label text
    if label:
        font = make_font(theme.font_family, theme.font_size)
        text_paint = skia.Paint()
        text_paint.setColor4f(hex_to_color4f(theme.font_color))
        text_paint.setAntiAlias(True)
        text_width = font.measureText(label)
        text_x = cx - text_width / 2
        text_y = cy + theme.font_size / 3
        native.drawString(label, text_x, text_y, font, text_paint)

    if opacity < 1.0:
        native.restore()


# ──────────────────────────────────────────────
# Cache Painter (diamond shape)
# ──────────────────────────────────────────────


def paint_cache(
    canvas: SkiaCanvas,
    bbox: BoundingBox,
    label: str,
    theme: ThemeConfig,
    opacity: float = 1.0,
    glow_intensity: float = 0.0,
) -> None:
    """Draw a diamond-shaped node representing a cache layer.

    The diamond is a 45-degree rotated square, inscribed within the bbox.

    Args:
        canvas: SkiaCanvas wrapper.
        bbox: Absolute pixel BoundingBox.
        label: Cache label text.
        theme: Visual theme config.
        opacity: Node opacity [0.0, 1.0].
        glow_intensity: Pulse glow intensity [0.0, 1.0].
    """
    native = canvas.native

    if opacity < 1.0:
        canvas.save_layer(opacity)

    cx = bbox.x + bbox.width / 2
    cy = bbox.y + bbox.height / 2
    hw = bbox.width / 2   # half width
    hh = bbox.height / 2  # half height

    # Diamond path (4 points: top, right, bottom, left)
    path = skia.Path()
    path.moveTo(cx, bbox.y)                # Top
    path.lineTo(bbox.x + bbox.width, cy)   # Right
    path.lineTo(cx, bbox.y + bbox.height)  # Bottom
    path.lineTo(bbox.x, cy)                # Left
    path.close()

    # Glow
    if glow_intensity > 0:
        _draw_glow(native, path, theme, glow_intensity)

    # Shadow
    shadow_paint = skia.Paint()
    shadow_paint.setColor4f(skia.Color4f(0, 0, 0, 0.3))
    shadow_paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 4.0))
    shadow_paint.setAntiAlias(True)
    native.save()
    native.translate(2, 2)
    native.drawPath(path, shadow_paint)
    native.restore()

    # Fill
    fill_paint = skia.Paint()
    fill_paint.setColor4f(hex_to_color4f(theme.node_fill))
    fill_paint.setAntiAlias(True)
    native.drawPath(path, fill_paint)

    # Border
    border_paint = skia.Paint()
    border_paint.setColor4f(hex_to_color4f(theme.node_border))
    border_paint.setStyle(skia.Paint.kStroke_Style)
    border_paint.setStrokeWidth(theme.node_border_width)
    border_paint.setAntiAlias(True)
    native.drawPath(path, border_paint)

    # Label text (centered)
    if label:
        font = make_font(theme.font_family, theme.font_size)
        text_paint = skia.Paint()
        text_paint.setColor4f(hex_to_color4f(theme.font_color))
        text_paint.setAntiAlias(True)
        text_width = font.measureText(label)
        text_x = cx - text_width / 2
        text_y = cy + theme.font_size / 3
        native.drawString(label, text_x, text_y, font, text_paint)

    if opacity < 1.0:
        native.restore()


# ──────────────────────────────────────────────
# User Painter (person icon: circle head + triangle body)
# ──────────────────────────────────────────────


def paint_user(
    canvas: SkiaCanvas,
    bbox: BoundingBox,
    label: str,
    theme: ThemeConfig,
    opacity: float = 1.0,
    glow_intensity: float = 0.0,
) -> None:
    """Draw a person-icon node representing a human actor.

    Layout: circle head (top 40%) + trapezoid body (bottom 40%) + label below.

    Args:
        canvas: SkiaCanvas wrapper.
        bbox: Absolute pixel BoundingBox.
        label: User label text.
        theme: Visual theme config.
        opacity: Node opacity [0.0, 1.0].
        glow_intensity: Pulse glow intensity [0.0, 1.0].
    """
    native = canvas.native

    if opacity < 1.0:
        canvas.save_layer(opacity)

    cx = bbox.x + bbox.width / 2
    icon_top = bbox.y + bbox.height * 0.05

    # Head: circle (top 35% of bbox height)
    head_radius = min(bbox.width * 0.22, bbox.height * 0.18)
    head_cy = icon_top + head_radius + 2

    # Body: trapezoid (below head, ~40% of bbox height)
    body_top = head_cy + head_radius + 3
    body_bottom = bbox.y + bbox.height * 0.72
    body_half_top = head_radius * 0.8
    body_half_bottom = min(bbox.width * 0.35, head_radius * 1.6)

    # Combined path for glow
    person_path = skia.Path()
    person_path.addCircle(cx, head_cy, head_radius)
    body_path = skia.Path()
    body_path.moveTo(cx - body_half_top, body_top)
    body_path.lineTo(cx + body_half_top, body_top)
    body_path.lineTo(cx + body_half_bottom, body_bottom)
    body_path.lineTo(cx - body_half_bottom, body_bottom)
    body_path.close()
    person_path.addPath(body_path)

    # Glow
    if glow_intensity > 0:
        _draw_glow(native, person_path, theme, glow_intensity)

    # Shadow
    shadow_paint = skia.Paint()
    shadow_paint.setColor4f(skia.Color4f(0, 0, 0, 0.3))
    shadow_paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 3.0))
    shadow_paint.setAntiAlias(True)
    native.save()
    native.translate(2, 2)
    native.drawPath(person_path, shadow_paint)
    native.restore()

    # Fill (head + body)
    fill_color = hex_to_color4f(theme.node_fill)
    fill_paint = skia.Paint()
    fill_paint.setColor4f(fill_color)
    fill_paint.setAntiAlias(True)
    native.drawCircle(cx, head_cy, head_radius, fill_paint)
    native.drawPath(body_path, fill_paint)

    # Border (head + body)
    border_paint = skia.Paint()
    border_paint.setColor4f(hex_to_color4f(theme.node_border))
    border_paint.setStyle(skia.Paint.kStroke_Style)
    border_paint.setStrokeWidth(theme.node_border_width)
    border_paint.setAntiAlias(True)
    native.drawCircle(cx, head_cy, head_radius, border_paint)
    native.drawPath(body_path, border_paint)

    # Label text (below body)
    if label:
        font = make_font(theme.font_family, theme.font_size)
        text_paint = skia.Paint()
        text_paint.setColor4f(hex_to_color4f(theme.font_color))
        text_paint.setAntiAlias(True)
        text_width = font.measureText(label)
        text_x = cx - text_width / 2
        text_y = body_bottom + theme.font_size + 2
        native.drawString(label, text_x, text_y, font, text_paint)

    if opacity < 1.0:
        native.restore()


# ──────────────────────────────────────────────
# Shared Glow Helper
# ──────────────────────────────────────────────


def _draw_glow(
    native: object,
    path: object,
    theme: ThemeConfig,
    intensity: float,
) -> None:
    """Draw a glow effect around an arbitrary path.

    Args:
        native: Skia native canvas.
        path: Skia Path to glow around.
        theme: Theme config for glow color.
        intensity: Glow intensity [0.0, 1.0].
    """
    glow_paint = skia.Paint()
    glow_paint.setColor4f(hex_to_color4f(theme.packet_color, opacity=intensity * 0.6))
    glow_paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 8.0))
    glow_paint.setAntiAlias(True)
    native.drawPath(path, glow_paint)

