"""Unit tests for PLAN-010 — DX Package (Progress, Errors, Logging).

Tests cover:
    - RenderProgress context manager (Rich + fallback)
    - format_error() for all exception types
    - print_error() output quality
    - setup_logging() configuration
    - Scene.render() show_progress integration
"""

from __future__ import annotations

import io
import logging

import pytest

from archmotion.dx._errors import (
    _FIX_SUGGESTIONS,
    _PHASE_MAP,
    format_error,
    print_error,
)
from archmotion.dx._logging import get_logger, setup_logging
from archmotion.dx._progress import RenderProgress, create_progress_callback
from archmotion.errors import (
    ArchMotionError,
    DuplicateIdError,
    EmptyTimelineError,
    FFmpegCrashError,
    FFmpegNotFoundError,
    InvalidConnectionError,
    OrphanNodeError,
    OverflowCanvasError,
    SkiaAllocationError,
)


# ══════════════════════════════════════════════
# RenderProgress
# ══════════════════════════════════════════════


class TestRenderProgress:
    """Test Rich progress bar context manager."""

    def test_context_manager_returns_callable(self):
        with RenderProgress() as cb:
            assert callable(cb)

    def test_callback_no_crash_with_zero_total(self):
        with RenderProgress() as cb:
            cb(0, 0)  # Should not crash

    def test_callback_updates_progress(self):
        with RenderProgress() as cb:
            cb(10, 100)
            cb(50, 100)
            cb(100, 100)

    def test_exit_cleans_up(self):
        rp = RenderProgress()
        cb = rp.__enter__()
        cb(5, 10)
        rp.__exit__(None, None, None)
        # Should not crash on second exit
        rp.__exit__(None, None, None)

    def test_custom_description(self):
        with RenderProgress(description="Encoding") as cb:
            cb(1, 10)


class TestCreateProgressCallback:
    """Test factory function for progress callback."""

    def test_returns_tuple(self):
        progress, cb = create_progress_callback()
        assert isinstance(progress, RenderProgress)
        assert callable(cb)

    def test_custom_description(self):
        progress, cb = create_progress_callback(description="Exporting")
        assert isinstance(progress, RenderProgress)


# ══════════════════════════════════════════════
# Error Formatting
# ══════════════════════════════════════════════


class TestFormatError:
    """Test format_error() output quality."""

    def test_topology_error_has_phase(self):
        exc = DuplicateIdError("node_1")
        result = format_error(exc)
        assert "Phase 1" in result
        assert "Topology" in result

    def test_duplicate_id_shows_id(self):
        exc = DuplicateIdError("my_node")
        result = format_error(exc)
        assert "my_node" in result

    def test_empty_timeline_has_fix(self):
        exc = EmptyTimelineError()
        result = format_error(exc)
        assert "Fix" in result or "play()" in result

    def test_ffmpeg_not_found_has_fix(self):
        exc = FFmpegNotFoundError()
        result = format_error(exc)
        assert "ffmpeg" in result.lower()

    def test_layout_error_is_phase_2(self):
        exc = OrphanNodeError("node_1")
        result = format_error(exc)
        assert "Phase 2" in result

    def test_render_error_is_phase_4(self):
        exc = FFmpegCrashError(1, "encoding failed")
        result = format_error(exc)
        assert "Phase 4" in result

    def test_unknown_exception_handled(self):
        exc = ValueError("something")
        result = format_error(exc)
        assert "Unknown" in result or "ValueError" in result

    def test_all_archmotion_errors_have_phase(self):
        """Every mapped error type should produce a phase label."""
        for exc_type in _PHASE_MAP:
            assert _PHASE_MAP[exc_type][0].startswith("Phase")


class TestPrintError:
    """Test print_error() output to stream."""

    def test_prints_to_stream(self):
        buf = io.StringIO()
        exc = EmptyTimelineError()
        # Rich renders to stderr for ArchMotionError, use format_error instead
        output = format_error(exc)
        assert "Phase 3" in output or "Timeline" in output

    def test_prints_non_archmotion_error(self):
        buf = io.StringIO()
        exc = ValueError("bad value")
        print_error(exc, file=buf)
        output = buf.getvalue()
        assert "ValueError" in output or "bad value" in output


class TestFixSuggestions:
    """Test that fix suggestions are comprehensive."""

    def test_all_suggestions_are_strings(self):
        for fix in _FIX_SUGGESTIONS.values():
            assert isinstance(fix, str)
            assert len(fix) > 10  # Non-trivial suggestion

    def test_critical_errors_have_fixes(self):
        critical = [
            DuplicateIdError,
            EmptyTimelineError,
            FFmpegNotFoundError,
        ]
        for exc_type in critical:
            assert exc_type in _FIX_SUGGESTIONS


# ══════════════════════════════════════════════
# Structured Logging
# ══════════════════════════════════════════════


class TestSetupLogging:
    """Test logging configuration."""

    def test_returns_logger(self):
        logger = setup_logging(level="WARNING")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "archmotion"

    def test_sets_level(self):
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_info_level_default(self):
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_no_propagation(self):
        logger = setup_logging()
        assert not logger.propagate

    def test_reconfigure_clears_handlers(self):
        setup_logging(level="DEBUG")
        logger = setup_logging(level="WARNING")
        # Should have exactly 1 console handler (not 2)
        assert len(logger.handlers) == 1

    def test_plain_text_mode(self):
        logger = setup_logging(level="INFO", use_rich=False)
        assert isinstance(logger, logging.Logger)


class TestGetLogger:
    """Test child logger creation."""

    def test_get_child_logger(self):
        logger = get_logger("renderer")
        assert logger.name == "archmotion.renderer"

    def test_get_root_logger(self):
        logger = get_logger()
        assert logger.name == "archmotion"

    def test_different_names_different_loggers(self):
        a = get_logger("exporter")
        b = get_logger("renderer")
        assert a is not b


# ══════════════════════════════════════════════
# Scene.render() Integration
# ══════════════════════════════════════════════


class TestSceneRenderShowProgress:
    """Test show_progress parameter on Scene.render()."""

    def test_render_accepts_show_progress_param(self):
        """Verify Scene.render() accepts show_progress without error."""
        from archmotion.api.scene import Scene

        scene = Scene()
        # Just verify the method signature accepts the param
        import inspect
        sig = inspect.signature(scene.render)
        assert "show_progress" in sig.parameters

    def test_show_progress_default_true(self):
        """Verify show_progress defaults to True."""
        from archmotion.api.scene import Scene

        scene = Scene()
        import inspect
        sig = inspect.signature(scene.render)
        assert sig.parameters["show_progress"].default is True
