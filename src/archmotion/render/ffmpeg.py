"""FFmpeg subprocess management — encoder detection and pipe setup.

CONTAINMENT: This module is the ONLY place in the render stack that imports
``subprocess``. FFmpeg receives raw RGBA frames via stdin pipe (zero-disk I/O).
The production baseline is libx264 (CPU). Hardware encoding is opt-in and NVENC
must pass a real encode probe before selection. The subprocess is long-running;
frames are streamed incrementally.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING, Literal

from archmotion.constants import FFMPEG_PIPE_TIMEOUT
from archmotion.errors import FFmpegCrashError, FFmpegNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

# ──────────────────────────────────────────────
# FFmpeg Binary Resolution
# ──────────────────────────────────────────────


def get_ffmpeg_path() -> str:
    """Resolve the FFmpeg binary path.

    Resolution priority:
        1. ``FFMPEG_BINARY`` environment variable
        2. System PATH (``shutil.which``)
        3. Bundled binary via ``imageio-ffmpeg``

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
        import imageio_ffmpeg

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
        name: Encoder name (``h264_nvenc`` or ``libx264``).
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
    options=("-preset", "veryfast", "-crf", "20"),
)


def cpu_encoder(crf: int = 20) -> EncoderConfig:
    """Return the deterministic CPU baseline encoder configuration."""
    return EncoderConfig(
        name="libx264",
        label="CPU (libx264)",
        options=("-preset", "veryfast", "-crf", str(crf)),
    )


# Module-level cache so the encoder probe runs at most once per process.
_encoder_cache: EncoderConfig | None = None


def detect_encoder(
    ffmpeg_path: str | None = None,
    *,
    force: bool = False,
    crf: int = 20,
) -> EncoderConfig:
    """Detect the best available H.264 encoder.

    Attempts NVENC (GPU) first, falls back to libx264 (CPU). Result is cached
    per process unless ``force`` is set.

    Args:
        ffmpeg_path: FFmpeg binary path (auto-detected if None).
        force: Re-run the probe even if a cached result exists.
        crf: Constant-rate factor for the libx264 fallback.

    Returns:
        :class:`EncoderConfig` for the selected encoder.
    """
    global _encoder_cache
    if _encoder_cache is not None and not force:
        return _encoder_cache

    resolved = ffmpeg_path if ffmpeg_path is not None else None
    try:
        if resolved is None:
            resolved = get_ffmpeg_path()
        result = subprocess.run(
            [resolved, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if "h264_nvenc" in result.stdout and _probe_nvenc(resolved):
            _encoder_cache = NVENC_CONFIG
            return NVENC_CONFIG
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, FFmpegNotFoundError):
        pass

    libx = cpu_encoder(crf)
    _encoder_cache = libx
    return libx


def _probe_nvenc(ffmpeg_path: str) -> bool:
    """Attempt a one-frame hardware encode, not merely an encoder listing."""
    try:
        result = subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=16x16:d=0.04",
                "-frames:v",
                "1",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def clear_encoder_cache() -> None:
    """Clear the cached encoder selection (mainly for tests)."""
    global _encoder_cache
    _encoder_cache = None


# ──────────────────────────────────────────────
# FFmpeg Pipe Process
# ──────────────────────────────────────────────


class FFmpegPipe:
    """Managed FFmpeg subprocess for streaming RGBA frames to video.

    Wraps the ``Popen`` lifecycle: open -> write frames -> close -> wait.

    Usage::

        pipe = FFmpegPipe.open(Path("out.mp4"), 1920, 1080, 30)
        try:
            for frame_bytes in frames:
                pipe.write_frame(frame_bytes)
        finally:
            pipe.close()  # Waits for FFmpeg to finish
    """

    __slots__ = ("_closed", "_encoder_config", "_output_path", "_process", "_stderr_file")

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        output_path: Path,
        encoder_config: EncoderConfig,
        stderr_file: IO[bytes],
    ) -> None:
        """Store the subprocess, output path, encoder, and stderr temp file."""
        self._process = process
        self._output_path = output_path
        self._encoder_config = encoder_config
        self._closed = False
        self._stderr_file = stderr_file

    @classmethod
    def open(
        cls,
        output_path: Path,
        width: int,
        height: int,
        fps: int,
        ffmpeg_path: str | None = None,
        encoder: EncoderConfig | None = None,
        crf: int = 20,
    ) -> FFmpegPipe:
        """Start an FFmpeg subprocess with stdin pipe for raw RGBA input.

        Args:
            output_path: Path for the output MP4 file.
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frame rate.
            ffmpeg_path: FFmpeg binary path (auto-detected if None).
            encoder: Encoder config (auto-detected if None).
            crf: Constant-rate factor (used for the libx264 default encoder).

        Returns:
            :class:`FFmpegPipe` ready for :meth:`write_frame` calls.

        Raises:
            FFmpegNotFoundError: If FFmpeg binary cannot be found.
        """
        if ffmpeg_path is None:
            ffmpeg_path = get_ffmpeg_path()
        if encoder is None:
            # Reliability is the default contract. Hardware encoding is opt-in
            # until a caller has chosen the platform-specific trade-off.
            if os.environ.get("ARCHMOTION_HARDWARE_ENCODER", "").lower() in {
                "1",
                "true",
                "auto",
                "nvenc",
            }:
                encoder = detect_encoder(ffmpeg_path, crf=crf)
            else:
                encoder = cpu_encoder(crf)

        cmd = [
            ffmpeg_path,
            "-y",  # Overwrite output
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            f"{width}x{height}",
            "-pix_fmt",
            "rgba",
            "-r",
            str(fps),
            "-i",
            "-",  # Read from stdin pipe
            "-c:v",
            encoder.name,
            *encoder.options,
            "-pix_fmt",
            "yuv420p",  # H.264 compatibility
            str(output_path),
        ]

        # Redirect stderr to a temp file instead of a pipe. FFmpeg builds can be
        # very verbose; a PIPE'd stderr fills its OS buffer (4KB on Windows) and
        # deadlocks FFmpeg when frames arrive slowly from the worker pool. A file
        # never blocks. stdout is discarded (never needed).
        stderr_file = tempfile.TemporaryFile()  # noqa: SIM115
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )

        return cls(process, output_path, encoder, stderr_file)

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
            RuntimeError: If called after :meth:`close`.
        """
        if self._closed:
            msg = "Cannot write to a closed FFmpegPipe."
            raise RuntimeError(msg)

        stdin = self._process.stdin
        if stdin is None:
            msg = "FFmpeg stdin pipe is unavailable."
            raise RuntimeError(msg)

        try:
            stdin.write(raw_rgba_bytes)
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
            ) from None

        if self._process.returncode != 0:
            stderr = self._read_stderr()
            raise FFmpegCrashError(
                returncode=self._process.returncode,
                stderr_output=stderr,
            )
        self._cleanup_stderr()

    def kill(self) -> None:
        """Forcefully terminate FFmpeg (for error cleanup)."""
        self._closed = True
        try:
            self._process.kill()
        except OSError:
            pass
        finally:
            self._process.wait()
        self._cleanup_stderr()

    def _read_stderr(self) -> str:
        """Read FFmpeg stderr for error diagnostics."""
        try:
            self._stderr_file.seek(0)
            content = self._stderr_file.read()
            if isinstance(content, bytes):
                return content.decode(errors="replace")
            return str(content)
        except (OSError, ValueError):
            return "(stderr unavailable)"

    def _cleanup_stderr(self) -> None:
        """Close and delete the stderr temp file (safe to call multiple times)."""
        with contextlib.suppress(Exception):
            self._stderr_file.close()
