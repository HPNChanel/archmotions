"""Legacy re-export of the theme configuration.

The canonical implementation now lives in :mod:`archmotion.render.theme`.
This module re-exports it so existing ``archmotion.renderer.theme`` imports
keep working during the v1→v2 transition.
"""

from __future__ import annotations

from archmotion.render.theme import THEMES, ThemeConfig, get_theme

__all__ = ["THEMES", "ThemeConfig", "get_theme"]
