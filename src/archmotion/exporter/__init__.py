"""Export Pipeline (v2) — Lottie, SVG, HTML.

Public API:
    build_lottie() -- Build Lottie JSON dict from a v2 Scene
    build_svg()    -- Build animated SVG string from a v2 Scene
    build_html()   -- Build a self-contained interactive HTML player

These are scene-driven (consume a :class:`~archmotion.core.scene.Scene`
directly) and skia-free. MP4 video rendering lives in ``archmotion.render.frame``.
"""

from __future__ import annotations

from archmotion.exporter.html_v2 import build_html
from archmotion.exporter.lottie_v2 import build_lottie
from archmotion.exporter.svg_v2 import build_svg

__all__ = [
    "build_html",
    "build_lottie",
    "build_svg",
]
