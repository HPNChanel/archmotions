"""FFmpeg subprocess management -- encoder detection and pipe setup.

CONTAINMENT: This module is the ONLY place that imports subprocess.

Architectural Note:
    FFmpeg receives raw RGBA frames via stdin pipe (Zero-Disk I/O).
    Encoder selection: NVENC (GPU) preferred, libx264 (CPU) fallback.
    The subprocess is long-running -- frames are streamed incrementally.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from archmotion.constants import FFMPEG_PIPE_TIMEOUT
from archmotion.errors import FFmpegCrashError, FFmpegNotFoundError


# ──────────────────────────────────────────────
# FFmpeg Binary Resolution
# ──────────────────────────────────────────────


def get_ffmpeg_path() -> str:
    """Resolve the FFmpeg binary path.

    Resolution priority:
    1. FFMPEG_BINARY environment variable
    2. System PATH (shutil.which)
    3. Bundled binary via imageio-ffmpeg

    Returns:
        Absolute path to the FFmpeg executable.

    Raises:
        FFmpegNotFoundError: If FFmpeg cannot be found anywhere.
    """
    # Priority 1: Environment variable
    env_path = os.environ.get("FFMPEG_BINARY")
    if env_path and os.path.isfile(env_path):
        return env_path

    # Priority 2: System PATH
    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path

    # Priority 3: Bundled via imageio-ffmpeg
    try:
        import imageio_ffmpeg  # type: ignore[import-untyped]

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        pass

    raise FFmpegNotFoundError()


# ──────────────────────────────────────────────
# Encoder Detection
# ──────────────────────────────────────────────

EncoderName = Literal["h264_nvenc", "libx264"]


@dataclass(frozen=True)
class EncoderConfig:
    """Configuration for the selected video encoder.

    Attributes:
        name: Encoder name ('h264_nvenc' or 'libx264').
        label: Human-readable label.
        options: Additional FFmpeg command-line options for this encoder.
    """

    name: EncoderName
    label: str
    options: tuple[str, ...]


NVENC_CONFIG = EncoderConfig(
    name="h264_nvenc",
    label="GPU (h264_nvenc)",
    options=("-preset", "p6", "-b:v", "5M"),
)

LIBX264_CONFIG = EncoderConfig(
    name="libx264",
    label="CPU (libx264)",
    options=("-preset", "medium", "-crf", "18"),
)


def detect_encoder(ffmpeg_path: str) -> EncoderConfig:
    """Detect the best available H.264 encoder.

    Attempts NVENC (GPU) first, falls back to libx264 (CPU).

    Args:
        ffmpeg_path: Path to the FFmpeg binary.

    Returns:
        EncoderConfig for the selected encoder.
    """
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if "h264_nvenc" in result.stdout:
            return NVENC_CONFIG
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return LIBX264_CONFIG


# ──────────────────────────────────────────────
# FFmpeg Pipe Process
# ──────────────────────────────────────────────


class FFmpegPipe:
    """Managed FFmpeg subprocess for streaming RGBA frames to video.

    Wraps Popen lifecycle: open -> write frames -> close -> wait.

    Usage:
        pipe = FFmpegPipe.open(...)
        try:
            for frame_bytes in frames:
                pipe.write_frame(frame_bytes)
        finally:
            pipe.close()  # Waits for FFmpeg to finish
    """

    __slots__ = ("_process", "_output_path", "_encoder_config", "_closed")

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        output_path: Path,
        encoder_config: EncoderConfig,
    ) -> None:
        self._process = process
        self._output_path = output_path
        self._encoder_config = encoder_config
        self._closed = False

    @classmethod
    def open(
        cls,
        output_path: Path,
        width: int,
        height: int,
        fps: int,
        ffmpeg_path: str | None = None,
        encoder: EncoderConfig | None = None,
    ) -> FFmpegPipe:
        """Start an FFmpeg subprocess with stdin pipe for raw RGBA input.

        Args:
            output_path: Path for the output MP4 file.
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frame rate.
            ffmpeg_path: FFmpeg binary path (auto-detected if None).
            encoder: Encoder config (auto-detected if None).

        Returns:
            FFmpegPipe ready for write_frame() calls.

        Raises:
            FFmpegNotFoundError: If FFmpeg binary cannot be found.
        """
        if ffmpeg_path is None:
            ffmpeg_path = get_ffmpeg_path()
        if encoder is None:
            encoder = detect_encoder(ffmpeg_path)

        cmd = [
            ffmpeg_path,
            "-y",                           # Overwrite output
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "rgba",
            "-r", str(fps),
            "-i", "-",                      # Read from stdin pipe
            "-c:v", encoder.name,
            *encoder.options,
            "-pix_fmt", "yuv420p",          # H.264 compatibility
            str(output_path),
        ]

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return cls(process, output_path, encoder)

    @property
    def encoder(self) -> EncoderConfig:
        """The active encoder configuration."""
        return self._encoder_config

    @property
    def output_path(self) -> Path:
        """Output video file path."""
        return self._output_path

    def write_frame(self, raw_rgba_bytes: bytes) -> None:
        """Write a single frame's raw RGBA bytes to FFmpeg stdin.

        Args:
            raw_rgba_bytes: Raw pixel data (width * height * 4 bytes).

        Raises:
            FFmpegCrashError: If FFmpeg stdin pipe is broken.
        """
        if self._closed:
            msg = "Cannot write to a closed FFmpegPipe."
            raise RuntimeError(msg)

        try:
            self._process.stdin.write(raw_rgba_bytes)  # type: ignore[union-attr]
        except (BrokenPipeError, OSError) as exc:
            stderr = self._read_stderr()
            raise FFmpegCrashError(
                returncode=self._process.returncode or -1,
                stderr_output=stderr,
            ) from exc

    def close(self) -> None:
        """Close stdin pipe and wait for FFmpeg to finish encoding.

        Raises:
            FFmpegCrashError: If FFmpeg exits with a non-zero return code.
        """
        if self._closed:
            return

        self._closed = True

        try:
            if self._process.stdin and not self._process.stdin.closed:
                self._process.stdin.close()

            self._process.wait(timeout=FFMPEG_PIPE_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            raise FFmpegCrashError(
                returncode=-1,
                stderr_output="FFmpeg timed out and was killed.",
            )

        if self._process.returncode != 0:
            stderr = self._read_stderr()
            raise FFmpegCrashError(
                returncode=self._process.returncode,
                stderr_output=stderr,
            )

    def kill(self) -> None:
        """Forcefully terminate FFmpeg (for error cleanup)."""
        self._closed = True
        try:
            self._process.kill()
        except OSError:
            pass
        finally:
            self._process.wait()

    def _read_stderr(self) -> str:
        """Read FFmpeg stderr for error diagnostics."""
        try:
            if self._process.stderr:
                return self._process.stderr.read().decode(errors="replace")
        except (OSError, ValueError):
            pass
        return "(stderr unavailable)"
