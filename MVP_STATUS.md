# ArchMotion v2.0 MVP Status

Status date: 2026-07-16

Verdict: **MVP-ready for a bounded 2D workflow; not a drop-in Manim
replacement.** The supported production path is Python/YAML → CPU-rendered H.264
MP4 or PNG. Everything outside that path must be treated according to the matrix
below.

## Support matrix

| Area | Status | Contract |
|---|---|---|
| Python scenes | Production MVP | Discover and instantiate a unique or named `Scene` subclass; run `setup`, `construct`, and `tear_down` once. |
| YAML scenes | Production MVP | Pydantic validation, unknown-field rejection, reference checks, versions `1.0` and `2.0`. |
| 2D scene graph | Production MVP | Parent/child ownership, affine transforms, inherited visual state, groups, z-order, and cycle prevention. |
| Timeline | Production MVP | Scalar actions, topology-aware morphs, animation groups, succession/lagging, trackers, and frame-local updaters. |
| 2D domains | Production MVP | Architecture, geometry/axes/plots, charts, text, native LaTeX outlines, and code blocks. |
| MP4 | Production MVP | Raw canonical RGBA frames → `libx264` H.264/yuv420p; CPU encoder is the reliable default. |
| PNG still | Production MVP | Any requested/end scene frame through Python or `archmotion still`. |
| CLI | Production MVP | YAML/Python input, scene selection, presets, resolution/fps/workers/CRF validation. |
| LaTeX | Conditional | Requires native `latex` and `dvisvgm`; repeated glyph `<use>` references and transforms are parsed. |
| Lottie/SVG/HTML | Experimental | Exported and tested structurally, but not guaranteed to match MP4 for every animation/style. CLI warnings are intentional. |
| Studio | Experimental | Pyodide loads the project wheel and compiles YAML; preview/export UX and browser-side MP4 are not production gates. |
| Multiprocessing/shared memory | Experimental | Windows defaults to one process; updater scenes force one process; shared memory is opt-in. |
| Hardware encoding | Experimental opt-in | Set `ARCHMOTION_HARDWARE_ENCODER=auto`; NVENC is selected only after an actual hardware encode probe. |
| Manim API compatibility | Unsupported | Existing Manim scripts require a rewrite. |
| 3D/OpenGL/audio/compositing | Unsupported | Not part of the v2.0 MVP. |

## What is complete

- A Manim-like `Scene.construct()` lifecycle plus direct scene composition.
- Public 2D shapes, coordinate systems, function plots, architecture nodes and
  routed connections, signed charts, text, LaTeX, and highlighted code.
- Creation, writing, fades, transforms, replacement transforms, grouped timing,
  architecture transfer/pulse effects, chart reveals, trackers, and redraw
  callbacks.
- Strict shared color parsing and a cross-platform RGBA byte contract. This is
  explicitly regression-tested because Skia's native Windows surface is BGRA.
- Real package/CLI boundaries: Python scene module loading, sibling imports,
  constructor overrides, clear scene-selection errors, MP4/PNG commands, and
  non-zero exits on invalid arguments.
- Release workflows for source quality, six Python/OS combinations, coverage,
  wheel/sdist checks, clean artifact installation, and real render smoke.

## Remaining gaps and risks

1. **No compatibility layer.** Familiar names do not imply Manim-compatible
   units, coordinate space, defaults, animation semantics, or import paths.
2. **No golden visual corpus yet.** Unit and integration coverage is broad, but
   cross-OS pixel tolerances and reference frames should gate future releases.
3. **Authoring depth is smaller than Manim.** Missing areas include moving
   cameras, scene sections, matrices/tables, richer equation transforms, images,
   audio, transparent sequences, and media compositing.
4. **Text/LaTeX portability depends on host fonts and native tools.** A release
   needs documented font/toolchain fixtures before exact typography can be
   promised across machines.
5. **Experimental exporter parity is incomplete.** Lottie/SVG/HTML need the same
   scene corpus as MP4 before their warnings can be removed.
6. **Studio is not the release authority.** Its narrow preview can make a
   1920×1080 scene difficult to inspect, and browser MP4 depends on wasm/CDN
   resources. The engine/CLI remains the truth root.
7. **Performance is not yet a universal SLA.** CPU rendering is deterministic,
   but scene complexity, text/LaTeX, worker count, and encoder availability can
   change throughput substantially.

## Verification gates

Latest local verification on Windows/Python 3.11:

- `463 passed, 1 skipped`; branch-aware coverage `80.88%` (required: `80%`).
- Ruff lint/format and mypy strict passed across all 68 source files.
- A clean wheel install outside the repository imported version `2.0.0` and
  rendered both an 854×480 RGBA PNG and a 33-frame H.264 MP4 through the
  installed `archmotion` executable.
- The release YAML benchmark produced a visually inspected H.264 stream at
  1920×1080, 60 fps, 90 frames, and 1.5 seconds with correct RGBA colors, labels,
  connection, packet, and payload.
- `twine check` passed for wheel and sdist. The constrained sdist is about
  178 KB/131 files and excludes `node_modules`, `.kilo`, Studio, and caches.
- `mkdocs build --strict`, Studio ESLint/Vite build, and `npm audit` passed;
  browser QA loaded the wheel, reached `Engine ready`, compiled the default
  YAML, ran Preview, and ended with zero console errors/warnings.

Run from a clean checkout:

```bash
python -m pip install -e ".[dev]"
ruff check src
ruff format --check src
mypy src/archmotion --strict --ignore-missing-imports
pytest tests/unit -q --cov=archmotion
python -m build
twine check dist/*
archmotion render examples/12_mvp_scene.py MvpScene -ql --workers 1 -o smoke.mp4
archmotion still examples/12_mvp_scene.py MvpScene -ql -o smoke.png
```

The real release workflow additionally installs the built wheel into an isolated
environment and runs `benchmarks/_e2e_smoke.py` before publishing.

## Replacement claim

ArchMotion may be described as an alternative for **new, bounded 2D technical
animation projects** that fit this matrix. It must not be described as a full or
drop-in replacement for Manim until a versioned compatibility corpus, the
missing media/camera capabilities, and visual parity gates exist.
