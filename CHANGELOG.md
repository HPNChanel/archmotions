# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — v2.0 beta

### Added

- Python `Scene` file loading with optional class selection, sibling imports,
  lifecycle hooks, CLI quality presets, render overrides, and PNG still output.
- Hierarchical scene graph transforms, topology-aware morphing, `Succession`,
  `LaggedStart`, `ValueTracker`, and `always_redraw`.
- General 2D geometry, axes/function plots, chart, text, math, and code domains
  alongside the architecture domain.
- Native LaTeX SVG `<defs>/<use>` expansion and a public `MathTex` alias.
- Strict shared CSS color normalization and strict YAML unknown-field handling.
- Cross-platform CI, coverage enforcement, artifact checks, clean wheel install,
  and real MP4/PNG release smoke scenes.

### Changed

- Declared the project Beta and narrowed the production contract to H.264 MP4
  and PNG. Lottie, SVG, HTML, hardware encoding, and Studio are explicitly
  experimental.
- Made `libx264` the deterministic default. Hardware encoding is opt-in and
  NVENC must pass a real one-frame probe before selection.
- Made the Windows automatic worker count one and forced updater-driven scenes
  to single-process rendering for deterministic execution.
- Updated theme/style inheritance, architecture labels/payload rendering,
  signed chart data, coordinate mappings, exporter contour schemas, and the
  public top-level API.

### Fixed

- Prevented recursive Windows multiprocessing in scripts and benchmarks.
- Fixed shared-memory slot reuse races, FPS override handling, animation-group
  retiming, multi-contour path creation, hierarchy ownership, and transform
  interpolation.
- Fixed native Skia BGRA output being mislabelled as RGBA on Windows; render
  surfaces now use a canonical RGBA byte order for Pillow and FFmpeg.
- Fixed Studio's Pyodide wheel installation (`deps=False`), preview sizing,
  missing favicon, dependency audit findings, and reproducible wheel build path.

## [1.0.0] - 2026-06-13

### Added

**Core Pipeline**
- Node + Database primitives with Fluent positioning API (`.right_of()`, `.below()`)
- Manhattan connection routing with L/I-shape and manual waypoints override
- 7 easing functions (Linear, EaseIn, EaseOut, EaseInOut, EaseInCubic, EaseOutCubic, EaseOutBounce)
- Scene orchestrator with Virtual Clock + concurrent animation support
- 12-type exception hierarchy with clear error messages
- Layout Resolver: Kahn topological sort + centering algorithm
- Timeline Compiler: 4 decomposers (FadeIn, FadeOut, Transfer, Pulse)
- Skia Renderer: canvas + 4 painters (node, connection, packet, text)
- Multiprocessing Exporter: FFmpegPipe + Pool with zero-disk I/O

**Extended Primitives**
- Cloud, Queue, Cache, User — 4 additional node types with custom renderers

**Enhanced Animations**
- Highlight, ColorShift, ScaleUp, ScaleDown — 4 animation types with decomposers

**YAML AI Interface**
- Pydantic v2 schema validation for LLM-generated YAML scenes
- `load_yaml()` / `parse_yaml_string()` public API
- Security: safe_load, size limits, input sanitization

**Developer Experience**
- Rich progress bar with auto-detection
- Structured error messages with field paths
- Logging integration

**Documentation**
- MkDocs Material documentation site (4 pages)
- 6 runnable example scripts

**Visual Polish**
- 4 themes: dark_terminal, neon_cyber, blueprint, light_paper
- Rounded corner routing (`conn_corner_radius` 12px default)
- Theme selection via Python API and YAML

**Advanced Routing**
- A* obstacle-aware pathfinding (visibility graph approach)
- Automatic collision avoidance around intermediate nodes
- 16px inflation margin for aesthetic clearance

**Performance**
- SharedMemory ring buffer for zero-copy IPC between render workers
- 99.99% reduction in IPC serialization overhead
- Fixed 32MB memory budget for ring buffer (vs unbounded pickle)

**Web Export**
- Lottie JSON exporter (bodymovin format v5.7.4)
- Animated SVG with CSS @keyframes
- Interactive HTML player with lottie-web + controls (play/pause, scrub, speed, loop)

**CLI**
- `archmotion render <yaml> -o output.mp4` — multi-format CLI
- Auto-detect format from file extension (.mp4, .json, .svg, .html)
- `archmotion version` / `archmotion themes` subcommands

**Public API**
- `Scene.export()` — unified method for Lottie/SVG/HTML export
- All 6 primitives, 8 animations, YAML functions exposed at top level
- PEP 561 `py.typed` marker for type checking support

### Technical Details
- Python 3.10+ required
- Dependencies: skia-python, imageio-ffmpeg, Pillow, pydantic, rich
- Test suite: 460+ tests, 100% pass rate
- Build: hatchling backend, src layout, PEP 621 metadata
