"""ArchMotion CLI — render Python/YAML scenes to MP4, PNG, or experimental vectors.

Architectural Note:
    Uses ``argparse`` (stdlib only, zero extra dependencies) with subcommands:
        - ``render``  — Load Python/YAML, auto-detect output format, export
        - ``still``   — Save one scene frame as PNG
        - ``version`` — Print version string
        - ``themes``  — List available themes

    Format is auto-detected from output file extension:
        .mp4  → Skia raster + FFmpeg MP4 video
        .json → Lottie bodymovin JSON
        .svg  → Animated SVG with CSS @keyframes
        .html → Interactive HTML player with lottie-web

    Override with ``--format`` flag when extension is ambiguous.

Usage::

    archmotion render scene.yaml -o output.mp4
    archmotion render scene.py MyScene -qm -o output.mp4
    archmotion still scene.py MyScene -qm -o output.png
    archmotion render scene.yaml -o output.json --minify
    archmotion render scene.yaml -o output.html --theme neon_cyber
    archmotion version
    archmotion themes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from archmotion import __version__

if TYPE_CHECKING:
    from archmotion.core.scene import Scene

# ──────────────────────────────────────────────
# Format Detection
# ──────────────────────────────────────────────

_FORMAT_MAP: dict[str, str] = {
    ".mp4": "mp4",
    ".json": "lottie",
    ".svg": "svg",
    ".html": "html",
    ".htm": "html",
}
"""Map file extensions to export format identifiers."""

SUPPORTED_FORMATS: tuple[str, ...] = ("mp4", "lottie", "svg", "html")
"""All supported export format identifiers."""

QUALITY_PRESETS: dict[str, tuple[tuple[int, int], int]] = {
    "low": ((854, 480), 15),
    "medium": ((1280, 720), 30),
    "high": ((1920, 1080), 60),
}
"""CLI quality presets as ``(resolution, fps)``."""


def detect_format(output_path: str, format_override: str | None = None) -> str:
    """Detect export format from file extension or explicit override.

    Args:
        output_path: Output file path.
        format_override: Explicit format name (overrides extension detection).

    Returns:
        Format identifier string ('mp4', 'lottie', 'svg', 'html').

    Raises:
        ValueError: If format cannot be determined.
    """
    if format_override is not None:
        fmt = format_override.lower()
        if fmt not in SUPPORTED_FORMATS:
            msg = f"Unknown format '{fmt}'. Supported: {', '.join(SUPPORTED_FORMATS)}"
            raise ValueError(msg)
        return fmt

    ext = Path(output_path).suffix.lower()
    detected = _FORMAT_MAP.get(ext)
    if detected is None:
        msg = (
            f"Cannot detect format from extension '{ext}'. "
            f"Use --format to specify. Supported extensions: "
            f"{', '.join(_FORMAT_MAP.keys())}"
        )
        raise ValueError(msg)
    return detected


# ──────────────────────────────────────────────
# Subcommand: render
# ──────────────────────────────────────────────


def _cmd_render(args: argparse.Namespace) -> int:
    """Execute the ``render`` subcommand.

    Loads a YAML scene file, builds a v2 :class:`Scene`, and exports to the
    requested format. The v2 Scene handles layout resolution (Phase 2) and
    timeline compilation internally.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    from archmotion.ai import YAMLParseError
    from archmotion.render.theme import THEMES, get_theme

    input_path = str(args.input)
    output_path = str(args.output) if args.output else _default_output(input_path, args.format)

    if args.workers is not None and args.workers < 1:
        print("Error: workers must be at least 1", file=sys.stderr)
        return 1
    if not 0 <= args.crf <= 51:
        print("Error: CRF must be between 0 and 51", file=sys.stderr)
        return 1

    # Detect format
    try:
        fmt = detect_format(output_path, args.format)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Validate theme
    theme_name = args.theme or "dark_terminal"
    if theme_name not in THEMES:
        print(
            f"Error: Unknown theme '{theme_name}'. Available: {', '.join(THEMES.keys())}",
            file=sys.stderr,
        )
        return 1

    # Load YAML or a Python Scene subclass.
    try:
        scene = _load_input_scene(args)
    except (FileNotFoundError, ImportError, TypeError, ValueError, YAMLParseError) as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    # Apply --theme override
    if args.theme and scene.theme.name != theme_name:
        scene.theme = get_theme(theme_name)

    out = Path(output_path)

    try:
        if fmt == "mp4":
            result_path = scene.render(
                output_file=str(out),
                show_progress=True,
                workers=args.workers,
                crf=args.crf,
            )
        elif fmt == "lottie":
            print(
                "Warning: Lottie/SVG/HTML exporters are experimental and not part of "
                "the production MVP contract.",
                file=sys.stderr,
            )
            result_path = scene.export(str(out), minify=getattr(args, "minify", False))
        elif fmt == "svg":
            print("Warning: SVG export is experimental.", file=sys.stderr)
            result_path = scene.export(str(out))
        else:  # html
            print("Warning: HTML export is experimental.", file=sys.stderr)
            result_path = scene.export(str(out), title=out.stem)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    label = {"mp4": "MP4", "lottie": "Lottie JSON", "svg": "SVG", "html": "HTML Player"}[fmt]
    print(f"Exported {label}: {result_path}")
    return 0


def _cmd_still(args: argparse.Namespace) -> int:
    """Render one frame from YAML or a Python Scene to PNG."""
    try:
        scene = _load_input_scene(args)
        result = scene.save_frame(args.output, time=args.time)
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Exported PNG: {result}")
    return 0


def _load_input_scene(args: argparse.Namespace) -> Scene:
    """Load a YAML scene or instantiate a Python Scene subclass."""
    from archmotion.ai import load_yaml
    from archmotion.core.camera import Camera
    from archmotion.loader import load_python_scene

    resolution, fps = _render_overrides(args)
    source = Path(args.input)
    if source.suffix.lower() == ".py":
        return load_python_scene(
            source,
            getattr(args, "scene", None),
            resolution=resolution,
            fps=fps,
        )

    scene = load_yaml(source)
    if resolution is not None:
        scene.resolution = resolution
        scene.camera = Camera(*resolution)
    if fps is not None:
        scene.fps = fps
    return scene


def _render_overrides(
    args: argparse.Namespace,
) -> tuple[tuple[int, int] | None, int | None]:
    """Resolve explicit resolution/fps over an optional quality preset."""
    quality = getattr(args, "quality", None)
    resolution: tuple[int, int] | None = None
    fps: int | None = None
    if quality:
        resolution, fps = QUALITY_PRESETS[quality]
    raw_resolution = getattr(args, "resolution", None)
    if raw_resolution:
        try:
            width, height = raw_resolution.lower().split("x", 1)
            resolution = (int(width), int(height))
        except (ValueError, AttributeError) as exc:
            raise ValueError("resolution must use WIDTHxHEIGHT, e.g. 1280x720") from exc
        if resolution[0] <= 0 or resolution[1] <= 0:
            raise ValueError("resolution dimensions must be positive")
    explicit_fps = getattr(args, "fps", None)
    if explicit_fps is not None:
        if explicit_fps <= 0:
            raise ValueError("fps must be positive")
        fps = explicit_fps
    return resolution, fps


def _default_output(input_path: str, format_override: str | None) -> str:
    """Generate default output path from input path and format.

    Args:
        input_path: Input YAML file path.
        format_override: Explicit format name.

    Returns:
        Default output file path.
    """
    stem = Path(input_path).stem
    ext_map = {
        "mp4": ".mp4",
        "lottie": ".json",
        "svg": ".svg",
        "html": ".html",
    }
    if format_override and format_override in ext_map:
        return f"{stem}{ext_map[format_override]}"
    return f"{stem}.mp4"


# ──────────────────────────────────────────────
# Subcommand: version
# ──────────────────────────────────────────────


def _cmd_version(_args: argparse.Namespace) -> int:
    """Print version information."""
    print(f"archmotion {__version__}")
    return 0


# ──────────────────────────────────────────────
# Subcommand: themes
# ──────────────────────────────────────────────


def _cmd_themes(_args: argparse.Namespace) -> int:
    """List available themes."""
    from archmotion.render.theme import THEMES

    print("Available themes:")
    for name in THEMES:
        marker = " (default)" if name == "dark_terminal" else ""
        print(f"  - {name}{marker}")
    return 0


# ──────────────────────────────────────────────
# Argument Parser
# ──────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser with subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="archmotion",
        description="ArchMotion — Python/YAML 2D animation engine",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # render
    render_parser = subparsers.add_parser(
        "render",
        help="Render a Python/YAML scene to MP4 or an experimental vector format",
    )
    render_parser.add_argument(
        "input",
        help="Path to a YAML scene or Python scene file",
    )
    render_parser.add_argument(
        "scene",
        nargs="?",
        help="Scene subclass name for Python files (optional when unique)",
    )
    render_parser.add_argument(
        "-o",
        "--output",
        help="Output file path (format auto-detected from extension)",
    )
    render_parser.add_argument(
        "--format",
        choices=SUPPORTED_FORMATS,
        help="Override output format (mp4, lottie, svg, html)",
    )
    render_parser.add_argument(
        "--theme",
        help="Color theme (dark_terminal, neon_cyber, blueprint, light_paper)",
    )
    render_parser.add_argument(
        "--minify",
        action="store_true",
        help="Minify JSON output (Lottie only)",
    )
    quality = render_parser.add_mutually_exclusive_group()
    quality.add_argument("-ql", dest="quality", action="store_const", const="low")
    quality.add_argument("-qm", dest="quality", action="store_const", const="medium")
    quality.add_argument("-qh", dest="quality", action="store_const", const="high")
    render_parser.add_argument("--resolution", help="Override resolution as WIDTHxHEIGHT")
    render_parser.add_argument("--fps", type=int, help="Override frame rate")
    render_parser.add_argument("--workers", type=int, help="Render worker count")
    render_parser.add_argument("--crf", type=int, default=20, help="H.264 CRF quality (0-51)")

    # still
    still_parser = subparsers.add_parser(
        "still",
        help="Render one PNG frame from a YAML or Python scene",
    )
    still_parser.add_argument("input", help="Path to a YAML scene or Python scene file")
    still_parser.add_argument("scene", nargs="?", help="Python Scene subclass name")
    still_parser.add_argument("-o", "--output", required=True, help="Output PNG path")
    still_parser.add_argument("--time", type=float, help="Timestamp in seconds (default: end)")
    still_quality = still_parser.add_mutually_exclusive_group()
    still_quality.add_argument("-ql", dest="quality", action="store_const", const="low")
    still_quality.add_argument("-qm", dest="quality", action="store_const", const="medium")
    still_quality.add_argument("-qh", dest="quality", action="store_const", const="high")
    still_parser.add_argument("--resolution", help="Override resolution as WIDTHxHEIGHT")
    still_parser.add_argument("--fps", type=int, help="Override frame rate")

    # version
    subparsers.add_parser("version", help="Print version information")

    # themes
    subparsers.add_parser("themes", help="List available themes")

    return parser


# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────


def main() -> None:
    """CLI entry point for ArchMotion."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    dispatch: dict[str, object] = {
        "render": _cmd_render,
        "still": _cmd_still,
        "version": _cmd_version,
        "themes": _cmd_themes,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    exit_code = handler(args)  # type: ignore[operator]
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
