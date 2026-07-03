"""Phase 4a -- Rendering Engine (Canvas, Painters, Frame).

Public API:
    render_frame()  -- Render a single frame to raw RGBA bytes
    FrameSpec       -- Data container for frame rendering inputs
    SkiaCanvas      -- Managed Skia Surface wrapper
    ThemeConfig     -- Visual theme configuration
    get_theme()     -- Theme registry lookup

Note:
    ``ThemeConfig`` and ``get_theme()`` are pure-Python and always available.
    ``render_frame``, ``FrameSpec``, and ``SkiaCanvas`` require the optional
    ``skia`` package and are imported lazily on first access. This keeps the
    non-rendering pipeline (YAML, layout, timeline, Lottie/SVG/HTML export)
    usable without ``skia`` installed — e.g. in Pyodide or restricted envs.
"""

from __future__ import annotations

from typing import Any

from archmotion.renderer.theme import ThemeConfig, get_theme

__all__ = [
    "FrameSpec",
    "SkiaCanvas",
    "ThemeConfig",
    "get_theme",
    "render_frame",
]

# Symbols that depend on the optional `skia` package, mapped to their
# defining submodule. Resolved on first attribute access via __getattr__.
_LAZY_SUBMODULES: dict[str, str] = {
    "FrameSpec": "archmotion.renderer.frame",
    "render_frame": "archmotion.renderer.frame",
    "SkiaCanvas": "archmotion.renderer.canvas",
}


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """Lazily import skia-dependent renderer symbols on first access.

    Raises:
        AttributeError: If ``name`` is not a lazy renderer symbol.
    """
    submodule = _LAZY_SUBMODULES.get(name)
    if submodule is None:
        msg = f"module 'archmotion.renderer' has no attribute {name!r}"
        raise AttributeError(msg)
    import importlib

    value = getattr(importlib.import_module(submodule), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Support ``dir()`` and IDE autocompletion of lazy symbols."""
    return sorted(set(__all__) | set(globals()))
