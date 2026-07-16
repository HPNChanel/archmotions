# ArchMotion Roadmap

This roadmap starts from the v2.0 beta truth boundary. ArchMotion targets a
useful 2D production workflow first; it does not treat version numbers or feature
names as evidence of Manim parity.

## Current: v2.0 2D production MVP

Done:

- Python `Scene.construct()` authoring and strict YAML authoring.
- Hierarchical vector scene graph, transforms, timelines, animation groups,
  morphing, `ValueTracker`, and `always_redraw`.
- Architecture, geometry, charts, text, math, and code domains.
- Reliable CPU H.264 MP4 and PNG still output, including Windows execution.
- CLI presets/overrides, Python scene discovery, build/install gates, real render
  smoke tests, and cross-platform CI.

Experimental in v2.0:

- Lottie, animated SVG, and HTML output.
- Browser Studio and browser-side MP4 conversion.
- Multiprocess/shared-memory tuning and hardware encoders.

The exact matrix is maintained in [MVP_STATUS.md](MVP_STATUS.md).

## v2.1: release hardening

- Add golden-image regression fixtures for colors, transforms, contours, text,
  charts, and architecture packets on Windows/Linux/macOS.
- Test every documented example as a clean-installed wheel, not an editable
  checkout.
- Add cancellation, structured render diagnostics, bounded resource policies,
  and clearer FFmpeg/LaTeX installation failures.
- Make experimental exporters pass a shared visual parity corpus or keep their
  warnings and experimental labels.
- Improve responsive Studio preview layout and automate browser runtime smoke.

Exit condition: MP4/PNG regressions fail closed in CI and release artifacts are
reproducibly installed and rendered on all supported operating systems.

## v2.2: broader 2D authoring

- Camera framing, pan/zoom, and scene sections.
- Richer text/glyph selection, TeX templates, matrices, equations, braces, and
  equation-to-equation transforms.
- More layout primitives, labels, coordinate systems, graph discontinuities,
  tables, images, and reusable composition helpers.
- Audio tracks, narration timing, video compositing, transparent sequences, and
  image-sequence export.
- A documented extension API for custom graphics, animations, and exporters.

Exit condition: a representative set of 2D educational Manim videos can be
re-authored in ArchMotion without modifying engine internals.

## v3.x: parity lane, not MVP scope

- Optional Manim-style compatibility helpers where semantics can be preserved.
- Stable plugin and asset ecosystem.
- GPU renderer and 3D camera/objects only after the 2D renderer and extension
  contracts are stable.

ArchMotion will not claim drop-in Manim compatibility until existing scenes can
be executed against a versioned compatibility test suite.
