"""Phase 4b -- Export Pipeline (FFmpeg + Multiprocessing Pool).

Public API:
    export_video()   -- Main entry point: render all frames + encode to MP4
    ExportResult     -- Output metadata
    FFmpegPipe       -- Managed FFmpeg subprocess
    get_ffmpeg_path  -- FFmpeg binary resolution
    detect_encoder   -- NVENC/libx264 auto-detection
"""

from archmotion.exporter.ffmpeg import (
    EncoderConfig,
    FFmpegPipe,
    detect_encoder,
    get_ffmpeg_path,
)
from archmotion.exporter.pool import ExportResult, export_video

__all__ = [
    "EncoderConfig",
    "ExportResult",
    "FFmpegPipe",
    "detect_encoder",
    "export_video",
    "get_ffmpeg_path",
]
