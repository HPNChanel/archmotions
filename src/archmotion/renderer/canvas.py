"""Legacy re-export of the Skia canvas abstraction.

The canonical implementation now lives in :mod:`archmotion.render.canvas`.
This module re-exports it so existing ``archmotion.renderer.canvas`` imports
keep working during the v1→v2 transition.
"""

from __future__ import annotations

from archmotion.render.canvas import (
    SkiaCanvas,
    hex_to_color4f,
    make_font,
    rgba_to_color4f,
)

__all__ = ["SkiaCanvas", "hex_to_color4f", "make_font", "rgba_to_color4f"]
