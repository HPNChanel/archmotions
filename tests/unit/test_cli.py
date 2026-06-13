"""Unit tests for PLAN-016 — CLI Multi-Format Interface.

Tests cover:
    - Argument parser construction
    - Format detection from file extensions
    - Format override with --format flag
    - Default output path generation
    - Version subcommand
    - Themes subcommand
    - Error handling for invalid formats/themes
"""

import argparse

import pytest

from archmotion.__main__ import (
    SUPPORTED_FORMATS,
    build_parser,
    detect_format,
    _default_output,
    _cmd_version,
    _cmd_themes,
)


# ──────────────────────────────────────────────
# Format Detection
# ──────────────────────────────────────────────


class TestDetectFormat:
    def test_mp4_extension(self):
        assert detect_format("output.mp4") == "mp4"

    def test_json_extension(self):
        assert detect_format("output.json") == "lottie"

    def test_svg_extension(self):
        assert detect_format("output.svg") == "svg"

    def test_html_extension(self):
        assert detect_format("output.html") == "html"

    def test_htm_extension(self):
        assert detect_format("output.htm") == "html"

    def test_case_insensitive(self):
        assert detect_format("output.MP4") == "mp4"

    def test_override_takes_precedence(self):
        # Even if extension is .mp4, override to lottie
        assert detect_format("output.mp4", "lottie") == "lottie"

    def test_unknown_extension_raises(self):
        with pytest.raises(ValueError, match="Cannot detect format"):
            detect_format("output.avi")

    def test_unknown_override_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            detect_format("output.mp4", "webm")


# ──────────────────────────────────────────────
# Default Output Path
# ──────────────────────────────────────────────


class TestDefaultOutput:
    def test_default_mp4(self):
        assert _default_output("scene.yaml", None) == "scene.mp4"

    def test_format_override_lottie(self):
        assert _default_output("scene.yaml", "lottie") == "scene.json"

    def test_format_override_svg(self):
        assert _default_output("scene.yaml", "svg") == "scene.svg"

    def test_format_override_html(self):
        assert _default_output("scene.yaml", "html") == "scene.html"


# ──────────────────────────────────────────────
# Parser Construction
# ──────────────────────────────────────────────


class TestBuildParser:
    def test_parser_created(self):
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_render_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["render", "test.yaml"])
        assert args.command == "render"
        assert args.input == "test.yaml"

    def test_render_with_output(self):
        parser = build_parser()
        args = parser.parse_args(["render", "test.yaml", "-o", "out.json"])
        assert args.output == "out.json"

    def test_render_with_format(self):
        parser = build_parser()
        args = parser.parse_args(["render", "test.yaml", "--format", "lottie"])
        assert args.format == "lottie"

    def test_render_with_theme(self):
        parser = build_parser()
        args = parser.parse_args(["render", "test.yaml", "--theme", "neon_cyber"])
        assert args.theme == "neon_cyber"

    def test_render_with_minify(self):
        parser = build_parser()
        args = parser.parse_args(["render", "test.yaml", "--minify"])
        assert args.minify is True

    def test_version_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["version"])
        assert args.command == "version"

    def test_themes_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["themes"])
        assert args.command == "themes"


# ──────────────────────────────────────────────
# Subcommand Handlers
# ──────────────────────────────────────────────


class TestSubcommands:
    def test_version_returns_zero(self, capsys):
        args = argparse.Namespace(command="version")
        code = _cmd_version(args)
        assert code == 0
        captured = capsys.readouterr()
        assert "archmotion" in captured.out

    def test_themes_returns_zero(self, capsys):
        args = argparse.Namespace(command="themes")
        code = _cmd_themes(args)
        assert code == 0
        captured = capsys.readouterr()
        assert "dark_terminal" in captured.out
        assert "neon_cyber" in captured.out


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────


class TestConstants:
    def test_supported_formats(self):
        assert "mp4" in SUPPORTED_FORMATS
        assert "lottie" in SUPPORTED_FORMATS
        assert "svg" in SUPPORTED_FORMATS
        assert "html" in SUPPORTED_FORMATS
