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
"""

from archmotion.exporter.ffmpeg import (
    EncoderConfig,
    FFmpegPipe,
    detect_encoder,
    get_ffmpeg_path,
)
from archmotion.exporter.html_player import export_html_player, export_svg
from archmotion.exporter.lottie import build_lottie_json, export_lottie
from archmotion.exporter.pool import ExportResult, export_video

__all__ = [
    "EncoderConfig",
    "ExportResult",
    "FFmpegPipe",
    "build_lottie_json",
    "detect_encoder",
    "export_html_player",
    "export_lottie",
    "export_svg",
    "export_video",
    "get_ffmpeg_path",
]
