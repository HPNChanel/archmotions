"""ArchMotion CLI — render YAML scenes to MP4, Lottie, SVG, or HTML.

Architectural Note:
    Uses ``argparse`` (stdlib only, zero extra dependencies) with subcommands:
        - ``render``  — Load YAML, auto-detect output format, export
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
    archmotion render scene.yaml -o output.json --minify
    archmotion render scene.yaml -o output.html --theme neon_cyber
    archmotion version
    archmotion themes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from archmotion import __version__


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
            msg = (
                f"Unknown format '{fmt}'. "
                f"Supported: {', '.join(SUPPORTED_FORMATS)}"
            )
            raise ValueError(msg)
        return fmt

    ext = Path(output_path).suffix.lower()
    fmt = _FORMAT_MAP.get(ext)
    if fmt is None:
        msg = (
            f"Cannot detect format from extension '{ext}'. "
            f"Use --format to specify. Supported extensions: "
            f"{', '.join(_FORMAT_MAP.keys())}"
        )
        raise ValueError(msg)
    return fmt


# ──────────────────────────────────────────────
# Subcommand: render
# ──────────────────────────────────────────────


def _cmd_render(args: argparse.Namespace) -> int:
    """Execute the ``render`` subcommand.

    Loads a YAML scene file, resolves the layout, compiles the timeline,
    and exports to the specified format.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    from archmotion.ai import load_yaml, YAMLParseError
    from archmotion.exporter.lottie import export_lottie
    from archmotion.exporter.html_player import export_html_player, export_svg
    from archmotion.layout.resolver import resolve_layout
    from archmotion.renderer.theme import get_theme, THEMES
    from archmotion.timeline.compiler import compile_timeline

    input_path = args.input
    output_path = args.output or _default_output(input_path, args.format)

    # Detect format
    try:
        fmt = detect_format(output_path, args.format)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    # Validate theme
    theme_name = args.theme or "dark_terminal"
    if theme_name not in THEMES:
        print(  # noqa: T201
            f"Error: Unknown theme '{theme_name}'. "
            f"Available: {', '.join(THEMES.keys())}",
            file=sys.stderr,
        )
        return 1

    # Load YAML
    try:
        scene = load_yaml(input_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        return 1
    except YAMLParseError as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    # Route to appropriate export format
    out = Path(output_path)

    if fmt == "mp4":
        # Use Scene.render() for MP4 (full pipeline with progress bar)
        if theme_name != scene._theme:
            scene._theme = theme_name
        result_path = scene.render(output_file=str(out), show_progress=True)
        print(f"✓ Exported MP4: {result_path}")  # noqa: T201
    else:
        # For non-MP4 formats, we need to manually run phases 1-3
        all_nodes, all_connections = scene._collect_topology()
        layout = resolve_layout(
            nodes=all_nodes,
            connections=all_connections,
            canvas_width=scene._canvas_width,
            canvas_height=scene._canvas_height,
        )
        timeline = compile_timeline(
            play_calls=scene._play_calls,
            total_duration=scene._current_time,
            fps=scene._fps,
        )

        theme = get_theme(theme_name)
        node_labels = {n.id: n.label for n in all_nodes}
        node_types = {n.id: n.primitive_type for n in all_nodes}
        conn_labels = {c.id: c.label for c in all_connections}

        if fmt == "lottie":
            export_lottie(
                timeline=timeline, layout=layout, theme=theme,
                node_labels=node_labels, node_types=node_types,
                connection_labels=conn_labels, output_path=out,
                minify=getattr(args, "minify", False),
            )
            print(f"✓ Exported Lottie JSON: {out}")  # noqa: T201
        elif fmt == "svg":
            export_svg(
                timeline=timeline, layout=layout, theme=theme,
                node_labels=node_labels, node_types=node_types,
                connection_labels=conn_labels, output_path=out,
            )
            print(f"✓ Exported SVG: {out}")  # noqa: T201
        elif fmt == "html":
            export_html_player(
                timeline=timeline, layout=layout, theme=theme,
                node_labels=node_labels, node_types=node_types,
                connection_labels=conn_labels, output_path=out,
            )
            print(f"✓ Exported HTML Player: {out}")  # noqa: T201

    return 0


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
    print(f"archmotion {__version__}")  # noqa: T201
    return 0


# ──────────────────────────────────────────────
# Subcommand: themes
# ──────────────────────────────────────────────


def _cmd_themes(_args: argparse.Namespace) -> int:
    """List available themes."""
    from archmotion.renderer.theme import THEMES

    print("Available themes:")  # noqa: T201
    for name, config in THEMES.items():
        marker = " (default)" if name == "dark_terminal" else ""
        print(f"  • {name}{marker}")  # noqa: T201
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
        description="ArchMotion — Code-to-Video Framework for System Architecture Animations",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # render
    render_parser = subparsers.add_parser(
        "render",
        help="Render a YAML scene to video, Lottie, SVG, or HTML",
    )
    render_parser.add_argument(
        "input",
        help="Path to the YAML scene file",
    )
    render_parser.add_argument(
        "-o", "--output",
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
