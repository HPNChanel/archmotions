"""Tests for FFmpeg binary resolution + encoder detection (render/ffmpeg.py).

No real ffmpeg encoding is exercised here — subprocess calls are monkeypatched.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from archmotion.errors import FFmpegCrashError, FFmpegNotFoundError
from archmotion.render.ffmpeg import (
    NVENC_CONFIG,
    EncoderConfig,
    FFmpegPipe,
    clear_encoder_cache,
    detect_encoder,
    get_ffmpeg_path,
)


class TestGetFfmpegPath:
    def test_env_var_priority(self, monkeypatch, tmp_path):
        fake_bin = tmp_path / "ffmpeg"
        fake_bin.write_text("fake")
        monkeypatch.setenv("FFMPEG_BINARY", str(fake_bin))
        monkeypatch.setattr("archmotion.render.ffmpeg.shutil.which", lambda _: None)
        assert get_ffmpeg_path() == str(fake_bin)

    def test_system_path_second(self, monkeypatch):
        monkeypatch.delenv("FFMPEG_BINARY", raising=False)
        monkeypatch.setattr("archmotion.render.ffmpeg.shutil.which", lambda _: "/usr/bin/ffmpeg")
        assert get_ffmpeg_path() == "/usr/bin/ffmpeg"

    def test_not_found_when_all_sources_fail(self, monkeypatch):
        monkeypatch.delenv("FFMPEG_BINARY", raising=False)
        monkeypatch.setattr("archmotion.render.ffmpeg.shutil.which", lambda _: None)

        def no_imageio():
            raise ImportError

        monkeypatch.setitem(__import__("sys").modules, "imageio_ffmpeg", None)
        # Force the imageio import inside get_ffmpeg_path to fail.
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "imageio_ffmpeg":
                raise ImportError
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(FFmpegNotFoundError):
            get_ffmpeg_path()


class TestDetectEncoder:
    def setup_method(self):
        clear_encoder_cache()

    def test_nvenc_detected(self, monkeypatch):
        clear_encoder_cache()
        calls = 0

        def successful_probe(*args, **kwargs):
            nonlocal calls
            calls += 1
            run = MagicMock()
            run.stdout = (
                "V..... h264_nvenc ..... NVIDIA NVENC H.264 encoder"
                if calls == 1
                else ""
            )
            run.returncode = 0
            return run

        monkeypatch.setattr(subprocess, "run", successful_probe)
        config = detect_encoder("/fake/ffmpeg")
        assert config == NVENC_CONFIG
        assert config.name == "h264_nvenc"

    def test_nvenc_listing_without_working_hardware_falls_back(self, monkeypatch):
        clear_encoder_cache()
        calls = 0

        def failed_probe(*args, **kwargs):
            nonlocal calls
            calls += 1
            run = MagicMock()
            run.stdout = "V..... h264_nvenc" if calls == 1 else ""
            run.returncode = 1
            return run

        monkeypatch.setattr(subprocess, "run", failed_probe)
        assert detect_encoder("/fake/ffmpeg").name == "libx264"

    def test_libx264_fallback(self, monkeypatch):
        clear_encoder_cache()
        run = MagicMock()
        run.stdout = "V..... libx264 ..... x264 encoder"  # no nvenc
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: run)
        config = detect_encoder("/fake/ffmpeg", crf=18)
        assert config.name == "libx264"
        assert "-crf" in config.options
        assert "18" in config.options

    def test_probe_failure_falls_back(self, monkeypatch):
        clear_encoder_cache()

        def boom(*a, **kw):
            raise FileNotFoundError

        monkeypatch.setattr(subprocess, "run", boom)
        config = detect_encoder("/fake/ffmpeg")
        assert config.name == "libx264"

    def test_result_is_cached(self, monkeypatch):
        clear_encoder_cache()
        call_count = 0

        def counting_run(*a, **kw):
            nonlocal call_count
            call_count += 1
            run = MagicMock()
            run.stdout = "libx264"
            return run

        monkeypatch.setattr(subprocess, "run", counting_run)
        detect_encoder("/fake/ffmpeg")
        detect_encoder("/fake/ffmpeg")
        assert call_count == 1  # second call used cache


class TestFFmpegPipeErrorHandling:
    def test_crash_raises_ffmpeg_crash_error(self, monkeypatch):
        """A non-zero FFmpeg exit raises FFmpegCrashError on close."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.stdin = MagicMock()
        proc.returncode = 1
        proc.wait.return_value = None
        stderr_file = MagicMock()
        stderr_file.read.return_value = b"bad codec"
        encoder = EncoderConfig(
            name="libx264", label="CPU", options=("-preset", "veryfast")
        )
        pipe = FFmpegPipe(proc, Path("out.mp4"), encoder, stderr_file)
        with pytest.raises(FFmpegCrashError) as exc_info:
            pipe.close()
        assert exc_info.value.returncode == 1

    def test_write_after_close_raises(self):
        proc = MagicMock(spec=subprocess.Popen)
        proc.stdin = MagicMock()
        proc.returncode = 0
        stderr_file = MagicMock()
        encoder = EncoderConfig(name="libx264", label="CPU", options=())
        pipe = FFmpegPipe(proc, Path("out.mp4"), encoder, stderr_file)
        pipe.close()
        with pytest.raises(RuntimeError, match="closed"):
            pipe.write_frame(b"data")
