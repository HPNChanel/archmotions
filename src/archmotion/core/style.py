"""Visual style for Graphics (fill, stroke, glow).

A ``Style`` is pure data — it holds no rendering logic. Colors left as ``None``
mean "inherit from the active :class:`~archmotion.render.theme.ThemeConfig`" so
that a single theme can restyle every Graphic at paint time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from archmotion.core.color import normalize_color


@dataclass(frozen=True)
class Style:
    """Fill + stroke + glow configuration for a vector graphic.

    Attributes:
        fill_color: Fill color (hex/CSS name) or ``None`` to inherit theme.
        fill_opacity: Fill alpha [0.0, 1.0].
        stroke_color: Stroke color or ``None`` to inherit theme.
        stroke_width: Stroke width in pixels.
        stroke_opacity: Stroke alpha [0.0, 1.0].
        glow_color: Glow halo color or ``None`` (no glow).
        glow_blur: Glow blur radius in pixels (0 disables glow).
        corner_radius: Optional rounded-corner radius for box-like shapes.
    """

    fill_color: str | None = None
    fill_opacity: float = 1.0
    stroke_color: str | None = None
    stroke_width: float = 2.0
    stroke_opacity: float = 1.0
    glow_color: str | None = None
    glow_blur: float = 0.0
    corner_radius: float = 0.0

    def __post_init__(self) -> None:
        """Normalize colors and reject invalid numeric paint properties."""
        for field_name in ("fill_color", "stroke_color", "glow_color"):
            color = getattr(self, field_name)
            if color is not None:
                object.__setattr__(self, field_name, normalize_color(color))
        for field_name in ("fill_opacity", "stroke_opacity"):
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1")
        for field_name in ("stroke_width", "glow_blur", "corner_radius"):
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{field_name} must be a finite non-negative number")

    def with_fill(self, color: str | None, opacity: float | None = None) -> Style:
        """Return a copy with the fill updated."""
        return _replace(self, fill_color=color, fill_opacity=_or(opacity, self.fill_opacity))

    def with_stroke(
        self,
        color: str | None,
        width: float | None = None,
        opacity: float | None = None,
    ) -> Style:
        """Return a copy with the stroke updated."""
        return _replace(
            self,
            stroke_color=color,
            stroke_width=_or(width, self.stroke_width),
            stroke_opacity=_or(opacity, self.stroke_opacity),
        )

    def with_glow(self, color: str | None, blur: float | None = None) -> Style:
        """Return a copy with glow color and blur radius updated."""
        return _replace(
            self,
            glow_color=color,
            glow_blur=_or(blur, self.glow_blur),
        )


def _or(value: float | None, fallback: float) -> float:
    return fallback if value is None else value


def _replace(style: Style, **changes: object) -> Style:
    """dataclasses.replace shim that keeps Style frozen + typed."""
    return Style(
        fill_color=changes.get("fill_color", style.fill_color),  # type: ignore[arg-type]
        fill_opacity=changes.get("fill_opacity", style.fill_opacity),  # type: ignore[arg-type]
        stroke_color=changes.get("stroke_color", style.stroke_color),  # type: ignore[arg-type]
        stroke_width=changes.get("stroke_width", style.stroke_width),  # type: ignore[arg-type]
        stroke_opacity=changes.get("stroke_opacity", style.stroke_opacity),  # type: ignore[arg-type]
        glow_color=changes.get("glow_color", style.glow_color),  # type: ignore[arg-type]
        glow_blur=changes.get("glow_blur", style.glow_blur),  # type: ignore[arg-type]
        corner_radius=changes.get("corner_radius", style.corner_radius),  # type: ignore[arg-type]
    )
