"""Phase 4b -- Export Pipeline (MP4, Lottie, SVG, HTML).

Public API:
    export_video()       -- Render all frames + encode to MP4
    export_lottie()      -- Export to Lottie JSON
    export_svg()         -- Export to animated SVG
    export_html_player() -- Export to interactive HTML player
    ExportResult         -- Output metadata
    FFmpegPipe           -- Managed FFmpeg subprocess
    get_ffmpeg_path      -- FFmpeg binary resolution
    detect_encoder       -- NVENC/libx264 auto-detection

Note:
    ``export_video`` and ``ExportResult`` depend on the optional ``skia``
    package (via the rendering pool) and are imported lazily on first access.
    The Lottie/SVG/HTML exporters are pure-Python and always available.
"""

from __future__ import annotations

from typing import Any

from archmotion.exporter.ffmpeg import (
    EncoderConfig,
    FFmpegPipe,
    detect_encoder,
    get_ffmpeg_path,
)
from archmotion.exporter.html_player import build_html_player, export_html_player, export_svg
from archmotion.exporter.lottie import build_lottie_json, export_lottie

__all__ = [
    "EncoderConfig",
    "ExportResult",
    "FFmpegPipe",
    "build_html_player",
    "build_lottie_json",
    "detect_encoder",
    "export_html_player",
    "export_lottie",
    "export_svg",
    "export_video",
    "get_ffmpeg_path",
]

# Symbols that depend on the optional `skia` package (via the render pool),
# resolved lazily on first attribute access so the vector exporters stay
# importable without skia (e.g. in Pyodide).
_LAZY_POOL_SYMBOLS: set[str] = {"ExportResult", "export_video"}


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """Lazily import skia-dependent pool symbols on first access.

    Raises:
        AttributeError: If ``name`` is not a known exporter symbol.
    """
    if name in _LAZY_POOL_SYMBOLS:
        from archmotion.exporter.pool import ExportResult, export_video

        globals()["ExportResult"] = ExportResult
        globals()["export_video"] = export_video
        return export_video if name == "export_video" else ExportResult
    msg = f"module 'archmotion.exporter' has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    """Support ``dir()`` and IDE autocompletion of lazy symbols."""
    return sorted(set(__all__) | set(globals()))
