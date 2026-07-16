"""Strict color normalization shared by authoring, YAML, and rendering."""

from __future__ import annotations

import re

_NAMED_COLORS: dict[str, str] = {
    "aqua": "#00ffff",
    "black": "#000000",
    "blue": "#0000ff",
    "cyan": "#00ffff",
    "fuchsia": "#ff00ff",
    "gray": "#808080",
    "green": "#008000",
    "grey": "#808080",
    "lime": "#00ff00",
    "magenta": "#ff00ff",
    "navy": "#000080",
    "olive": "#808000",
    "orange": "#ffa500",
    "pink": "#ffc0cb",
    "purple": "#800080",
    "red": "#ff0000",
    "silver": "#c0c0c0",
    "teal": "#008080",
    "white": "#ffffff",
    "yellow": "#ffff00",
}
_HEX_RE = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3}(?:[0-9a-fA-F]{2})?)?")


def normalize_color(color: str) -> str:
    """Return a normalized hex color or raise for unsupported input."""
    value = color.strip()
    named = _NAMED_COLORS.get(value.lower())
    if named is not None:
        return named
    if not _HEX_RE.fullmatch(value):
        names = ", ".join(sorted(_NAMED_COLORS))
        raise ValueError(f"color must use #RGB, #RRGGBB, #RRGGBBAA, or a supported name ({names})")
    return value.lower()


def color_to_rgba01(color: str, opacity: float = 1.0) -> tuple[float, float, float, float]:
    """Convert a supported color to float RGBA, multiplying alpha by opacity."""
    normalized = normalize_color(color).lstrip("#")
    if len(normalized) == 3:
        normalized = "".join(channel * 2 for channel in normalized)
    alpha = int(normalized[6:8], 16) / 255.0 if len(normalized) == 8 else 1.0
    return (
        int(normalized[0:2], 16) / 255.0,
        int(normalized[2:4], 16) / 255.0,
        int(normalized[4:6], 16) / 255.0,
        alpha * opacity,
    )


def color_to_rgb01(color: str) -> tuple[float, float, float]:
    """Convert a supported color to an RGB float triple."""
    red, green, blue, _alpha = color_to_rgba01(color)
    return (red, green, blue)


__all__ = ["color_to_rgb01", "color_to_rgba01", "normalize_color"]
