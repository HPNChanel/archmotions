"""Phase 4a -- Rendering Engine (Canvas, Painters, Frame).

Public API:
    render_frame()  -- Render a single frame to raw RGBA bytes
    FrameSpec       -- Data container for frame rendering inputs
    SkiaCanvas      -- Managed Skia Surface wrapper
    ThemeConfig     -- Visual theme configuration
    get_theme()     -- Theme registry lookup
"""

from archmotion.renderer.frame import FrameSpec, render_frame
from archmotion.renderer.theme import ThemeConfig, get_theme

__all__ = [
    "FrameSpec",
    "SkiaCanvas",
    "ThemeConfig",
    "get_theme",
    "render_frame",
]
