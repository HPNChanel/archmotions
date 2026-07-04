# ArchMotion v2.0 — Multi-Domain Fusion Engine

> Plan ID: 1783092584541 · Status: Implementation-ready · Predecessor: v1.0.0 (Python lib + Studio)

## Goal

Evolve ArchMotion from an **architecture-only** animation tool into a **Manim-scale
general-purpose graphics/animation library** whose differentiator is **multi-domain
fusion**: composing and *morphing* architecture/data-flow, geometry, charts, math, and
code in one scene. The core differentiator vs Manim is that **system-architecture
animation is a first-class domain** (DAG layout, A*-routed connections, data-flow
packets) fused with general-purpose graphics, and every vector graphic shares a
**point-array Bezier geometry** so any two shapes can `Transform` into each other.

## Context & Key Findings (verified against source)

- **Phase 3 is already a generic property-tween engine.** `ScheduledAction(target_id,
  prop, start/end_time, start/end_value, easing)` with O(1) `value_at(t)`
  (`timeline/actions.py:46`) and `CompiledTimeline.snapshot_at(frame)`
  (`timeline/compiler.py:102`) is domain-agnostic — identical to Manim's interpolation
  model. This is reused, not rewritten.
- **`AnimatableProperty` already defines** `OPACITY, POSITION_X/Y, SCALE, COLOR_R/G/B,
  GLOW_INTENSITY, PATH_PROGRESS` (`_types.py:75`). Architecture-specificity is
  concentrated in: primitives (`api/primitives.py` — pure topology dataclasses, no
  geometry/transform state), the hardcoded animation dispatch
  (`timeline/compiler.py:192` `_decompose`), `render_frame`'s hardcoded layers +
  `_PAINTER_DISPATCH` (`renderer/frame.py:130`), and per-type painter functions
  (`renderer/painters.py`).
- **Primitives carry no geometry.** `Node` is a `BoundingBox`-fed label; shape is
  painted per-type. To enable morphing, every shape must instead *generate an ordered
  Bezier point array*.
- **Export path is pure-Python** (no `skia`/`Pillow`/`ffmpeg`) — this is what lets the
  Studio run it in Pyodide. v2.0 LaTeX adds a **native dep** (`latex`+`dvisvgm`) that is
  **not** Pyodide-compatible (see Consequences).
- skia `Path` supports cubic Beziers natively → a single generic path renderer can paint
  any point-array graphic. skia can also extract glyph **paths from text** (no extra font
  dependency needed for plain/markdown text).

## Locked Decisions

1. **v2.0 breaking redesign.** New Manim-style API is first-class; v1.0 classes migrate
   or are removed. No compat shim (user-confirmed).
2. **Point-array Bezier geometry (Manim `VMobject` model).** Every vector graphic exposes
   an ordered cubic-Bezier control-point array; **one generic path renderer** paints all;
   cross-domain `Transform` via point interpolation.
3. **2D only on skia.** 3D/GPU renderer deferred (separate later phase).
4. **Full LaTeX** math via `latex` + `dvisvgm`, parsed into point-array Graphics (fully
   morphable). Code = syntax-highlighted blocks.
5. **Multi-domain:** architecture (migrated) + geometry + charts + text/math + code.
6. **numpy** becomes a core dependency for point arrays (available in Pyodide; MP4 path
   unaffected).
7. **Animation API:** recipe animations (`Create`, `FadeIn/Out`, `Write`, `Transform`,
   `Transfer`, `GrowBar`, `Pulse`, `Highlight`) **+** `.animate` property builder
   (`g.animate.shift(x,y).scale(s).rotate(d).set_fill(c)`) **+** `AnimationGroup`
   (sequential/parallel/lagged). All compile down to the generalized `ScheduledAction`
   timeline.

## Target Module Layout (new)

```
src/archmotion/
  core/                 # NEW foundation (replaces api/scene.py role)
    graphic.py          # Graphic base: id, z_index, transform, style, opacity, parent
    vmobject.py         # VMobject: point-array Bezier base (generate_points, interpolate, to_skia_path)
    camera.py           # Camera: scene-units <-> pixels frame, position, zoom
    scene.py            # generalized Scene: clock, add/remove, play/wait, AnimationGroup scheduling
    transform.py        # affine transform (translate/scale/rotate/shear) -> matrix
    style.py            # Style dataclass (fill/stroke colors, opacities, stroke width)
    pathops.py          # Bezier path builders (cubic, line, arc, close, resample, point-align)
  animation/            # renamed from motions/
    base.py             # Animation base + AnimationGroup + .animate builder + rate funcs
    creation.py         # Create, Uncreate, DrawBorderThenFill, ShowPassingFlash
    fading.py           # FadeIn, FadeOut
    transform.py        # Transform, ReplacementTransform, Morph (point interp)
    writing.py          # Write (per-glyph progressive)
    indicator.py        # Pulse, Highlight, Flash, Indicate
    color.py            # FadeToColor, ColorShift
    growing.py          # GrowFromCenter/Edge, GrowBar, DrawLine
  render/               # renamed/generalized from renderer/
    path_render.py      # generic VMobject -> skia painter (fills+strokes+transform+camera)
    frame.py            # generalized render_frame: iterate Graphics in z_order
    canvas.py           # skia canvas wrapper (kept)
    theme.py            # ThemeConfig (kept/extended with chart/text/code styles)
    tex.py              # latex + dvisvgm -> SVG parse -> VMobject points
  timeline/             # kept, generalized
    actions.py          # ScheduledAction (prop generalized to enum + optional index)
    property.py         # NEW: property addressing + per-Graphic resolution
    compiler.py         # generalized compile (Animation -> ScheduledActions)
    easing.py           # kept (add more curves)
  domains/
    geometry/           # Circle, Rectangle, Square, Line, Arrow, Polygon, Arc, Curve, Dot, Brace, Axes, NumberLine, ParametricFunction
    math/               # MathText, Tex (LaTeX)
    charts/             # BarChart, LineChart, PieChart, ScatterPlot
    text/               # Text, Paragraph, MarkupText (markdown via glyph paths)
    code/               # CodeBlock (Pygments syntax highlight -> styled Text spans)
    architecture/       # MIGRATED from api/ + layout/
      primitives.py     # Node/Database/Cloud/Queue/Cache/User as point-generating VMobjects
      connections.py    # Connection as routed-path VMobject + arrowhead + Packet VMobject
      layout/           # resolver.py, astar.py, router.py, bbox.py (moved, unchanged logic)
  exporter/             # kept, generalized to read VMobjects (lottie/svg/html)
    lottie.py, svg.py, html_player.py, ffmpeg.py, pool.py, shm.py
  ai/                   # generalized YAML schema + builder (new domain kinds)
  dx/, _types.py, constants.py, errors.py, __main__.py   # updated
```

---

## Phase 0 — Core Foundation (`core/` + `animation/` + `render/` + `timeline/`)

This phase delivers an engine that can render **arbitrary vector graphics** and animate
them, with **no new domains yet**. Everything downstream depends on it.

### 0.1 Point-array geometry base
- `core/vmobject.py`: `VMobject` with `points: np.ndarray` (flat cubic-Bezier quadruples,
  `[p0, c1, c2, p3]` per segment), `generate_points()` (abstract), path builders
  (`start_new_path`, `add_cubic_bezier`, `add_line_to`, `add_quadratic`, `add_arc`,
  `close_path`), `interpolate(other, alpha)` (point-count-matched morph), `align_points(other)`
  (resample to match counts for Transform), `bounding_box()`, `to_skia_path()`.
- `core/graphic.py`: `Graphic` base — `id`, `z_index`, `transform`, `style`, `opacity`,
  `parent`/`children` (scene-graph), `add()`/`remove()`, `shift/scale/rotate/move_to`
  fluent transforms.
- `core/transform.py`: affine matrix; `to_matrix()`, composition, apply-to-points.
- `core/style.py`: `Style(fill_color, fill_opacity, stroke_color, stroke_width,
  stroke_opacity)` frozen dataclass.
- `core/pathops.py`: Bezier utilities (length, point-at-t, resample, subdivision, offset).

### 0.2 Camera
- `core/camera.py`: `Camera(frame_width, frame_height, center, zoom)` mapping scene units
  (origin at center, y-up option) to pixels; `to_pixels(point)`, `frame_matrix()`.

### 0.3 Generic path renderer
- `render/path_render.py`: `paint_vmobject(canvas, vmobject, camera, snapshot)` — builds
  `skia.Path` from points (`cubicTo`), applies `transform` + `camera` matrix, fills +
  strokes per `style` with overall `opacity`. Handles `GLOW_INTENSITY` glow as a blurred
  stroke pass. Replaces ALL per-type painters for vector graphics.
- `render/frame.py`: generalized `render_frame(spec)` — iterate `scene.graphics` sorted by
  `z_index`, paint each via `paint_vmobject` given the frame's property snapshot.
  `FrameSpec` becomes `scene_graphics` (picklable point arrays + styles) + compiled actions.
- Keep `render/canvas.py` (skia wrapper). Extend `render/theme.py` with chart/text/code styles.

### 0.4 Generalized property model
- `timeline/property.py`: `AnimatableProperty` extended with `ROTATION, STROKE_WIDTH,
  STROKE_R/G/B, FILL_R/G/B` and **indexed point access** (`POINT_X(index)`, `POINT_Y(index)`)
  for movement + morph. A `PropertyKey` (enum + optional index) addresses any value.
- `timeline/actions.py`: `ScheduledAction.prop` → `PropertyKey`; `value_at` unchanged (O(1)).
- `timeline/compiler.py`: `snapshot_at` → `target_id -> {PropertyKey: float}`; resolver
  applies snapshot to each Graphic's transform/style/points before paint.

### 0.5 Animation model
- `animation/base.py`: `Animation` (`begin`, `interpolate(alpha)`, `cleanup`,
  `target/run_time/rate_func`); `AnimationGroup(*anims, lag_ratio, run_time)`; `.animate`
  builder returning a deferred property-tween animation.
- `animation/creation.py`: `Create` (progressive stroke draw via path trimming/dash
  animation over the point array), `Uncreate`, `DrawBorderThenFill`.
- `animation/fading.py`: `FadeIn`/`FadeOut` (opacity 0<->1).
- `animation/transform.py`: `Transform(a, b)` — `align_points`, then `interpolate` point
  arrays + colors; `ReplacementTransform`.
- `animation/writing.py`: `Write` — progressive per-glyph reveal (for text/code).
- `animation/indicator.py`, `color.py`, `growing.py`: migrate `Pulse`/`Highlight`/
  `ColorShift`/`Scale` semantics; add `GrowFromCenter`, `GrowBar`, `DrawLine`.
- **All compile to `ScheduledAction`s** via per-animation `to_actions(start_time)`.

### 0.6 Generalized Scene
- `core/scene.py`: virtual clock; `add(*graphics)`, `remove(*graphics)`; `play(*anims,
  run_time, lag_ratio)`, `wait(t)`, `wait_until`; collects graphics + compiles timeline.
- Replaces v1 `api/scene.py`'s `_play_calls` model but keeps the 4-phase pipeline
  (topology/layout/timeline/render) generalized.

### 0.7 Generalized exporters
- `exporter/lottie.py`: point-array → Lottie shape layers (bezier `ks` paths); keyframes
  from `ScheduledAction`s (position/scale/opacity/color/trim).
- `exporter/svg.py`: paths + CSS `@keyframes` from properties.
- `exporter/html_player.py`: shell unchanged (lottie-web).
- `exporter/ffmpeg.py`/`pool.py`/`shm.py`: unchanged; fed by generalized `render_frame`.
- `Scene.render()`/`export()` rebuild on the generalized frame pipeline.

### 0.8 Phase-0 validation
- New `tests/unit/core/` for VMobject point gen/interp/align, Camera mapping, generic
  path renderer (golden-frame smoke), property resolution, AnimationGroup timing.
- `mypy --strict` + `ruff` clean for new modules.

---

## Phase 1 — Geometry Domain (`domains/geometry/`)

### 1.1 Shapes
- `Circle`, `Rectangle`, `Square`, `RoundedRectangle`, `Line`, `DashedLine`, `DoubleArrow`,
  `Arrow`, `Polygon`, `RegularPolygon`, `Arc`, `ArcBetweenPoints`, `Dot`, `Brace`,
  `CurvesAsLine`, `Bezier`, `Annulus`, `Ellipse`. Each overrides `generate_points()` to
  emit cubic-Bezier control points (so all are `Transform`-morphable).

### 1.2 Coordinate systems
- `Axes`, `NumberLine`, `NumberPlane`, `ParametricFunction`, `FunctionGraph`. Map
  data-space to scene-space; produce tick/label VMobjects.

### 1.3 Phase-1 validation
- `tests/unit/domains/geometry/`: point-array correctness per shape, Transform
  (circle↔square) point alignment, axes scaling.

---

## Phase 2 — Architecture Domain Migration (`domains/architecture/`)

### 2.1 Primitives → VMobjects
- `Node/Database/Cloud/Queue/Cache/User` become VMobjects whose `generate_points()`
  produce their Bezier outlines (box/cylinder caps/cloud humps/parallelogram/diamond/
  person icon). The existing `renderer/painters.py` shapes become **point-generation
  recipes**, not painters.
- Labels become child `Text` VMobjects (Phase 4) positioned by the parent's bbox.

### 2.2 Connections
- `Connection` becomes a VMobject whose points = the A*-routed polyline (as Bezier
  segments, with optional rounded-corner subdivision). Arrowhead = child VMobject.
- `Packet` becomes a VMobject animated along the connection path (`PATH_PROGRESS`).
- `Transfer` animation migrates to `animation/` (drives packet `PATH_PROGRESS`).

### 2.3 Layout (moved, logic unchanged)
- Move `layout/{resolver,astar,router,bbox}.py` → `domains/architecture/layout/`.
- Resolver outputs feed Graphic positions (relative/absolute positioning preserved).

### 2.4 Recipe-animation + YAML/AI migration
- Migrate `FadeIn/Transfer/Pulse/Highlight/ColorShift/Scale` to the new `Animation` base.
- Generalize `ai/schema.py` + `ai/builder.py`: `NodeSpec` etc. now produce architecture
  VMobjects; add discriminated `domain` field for future cross-domain YAML.

### 2.5 Phase-2 validation
- `tests/unit/domains/architecture/`: layout parity with v1, primitives render via generic
  renderer, Transfer packet path, YAML→scene→export end-to-end.

---

## Phase 3 — Charts Domain (`domains/charts/`)

### 3.1 Charts
- `BarChart`, `LineChart`, `PieChart`, `ScatterPlot` — compositions of geometry VMobjects
  (bars = rectangles, line = polyline, slices = arcs); data → point arrays.
- Axes reuse `domains/geometry/Axes`.

### 3.2 Chart animations
- `GrowBar` (scale-from-zero), `DrawLine` (progressive trim), `SweepPie` (arc sweep).

### 3.3 Phase-3 validation
- `tests/unit/domains/charts/`: data→points correctness, GrowBar/DrawLine timing.

---

## Phase 4 — Text, Math & Code Domain (`domains/text/`, `domains/math/`, `domains/code/`)

### 4.1 Text
- `Text`, `Paragraph`, `MarkupText` (markdown). Glyph outlines via skia path-from-text
  (no extra dep) → VMobject points (so text is morphable).

### 4.2 Math (LaTeX)
- `render/tex.py`: `tex_to_vmobject(latex)` — shell `latex` → `dvisvgm` → SVG → parse path
  `d` commands → VMobject point arrays. Grouped per glyph for `Write`.
- `MathText`/`Tex`/`MathTex`. `Write` animation (per-glyph progressive).

### 4.3 Code
- `CodeBlock`: Pygments-tokenized source → colored `Text` spans (line-by-line VMobjects).
- `Write`/`Typewriter` animations; line-highlight indicator.

### 4.4 Phase-4 validation
- `tests/unit/domains/{text,math,code}/`: glyph-path extraction, LaTeX compile (skip if
  `latex` absent — mark `@pytest.mark.skipif`), syntax-span mapping.

---

## Phase 5 — Integration, Migration, Docs, Studio

### 5.1 Test migration (460 → v2.0)
- Map v1 tests to new module paths; rewrite assertions against the new API. Keep all
  behavioral coverage (layout, timeline, exporters, YAML). Target ≥ v1 coverage.

### 5.2 Fusion examples
- New `examples/`: (a) architecture + live metrics `BarChart` beside it; (b) `Transform`
  a `Node` into a `Circle` then into a `PieChart`; (c) `MathText` equation derivation over
  an architecture diagram; (d) `CodeBlock` walkthrough with data-flow `Transfer`.

### 5.3 CLI + docs
- Update `__main__.py`/CLI for new Scene API. MkDocs: new API reference, domain guides,
  "fusion" tutorial. Bump version to `2.0.0`.

### 5.4 Studio adaptation
- Rebuild `archmotion` wheel (now needs `numpy` in Pyodide — available). Studio supports
  **non-LaTeX** domains in-browser; LaTeX scenes render CLI/MP4 only (graceful message in
  browser). Update `compileScene` bridge + canvas node renderers to consume generic layout.

---

## Consequences / Caveats

- **LaTeX is a native dep.** `latex` + `dvisvgm` must be installed for MP4 math scenes.
  This **breaks the Pyodide/Studio browser path for the math domain** (math renders
  CLI/MP4 only). Plain/markdown text + code remain Pyodide-compatible.
- **v2.0 is breaking.** v1.0 consumers must migrate. No compat shim.
- **numpy** becomes a core dependency (Pyodide-compatible; MP4 path unaffected).
- **Point-count matching** for cross-domain `Transform` requires resampling/alignment
  (`align_points`) — lossy for very different topologies but standard (Manim does this).

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Generic path renderer slower than specialized painters | Profile vs v1 per-type painters; cache `to_skia_path` when points unchanged; vectorize with numpy. |
| 460-test migration volume + regressions | Migrate phase-by-phase (architecture in Phase 2); keep behavioral parity assertions; golden-frame diffing. |
| LaTeX native dep + Pyodide breakage | `tex.py` guarded by availability check; `@skipif` tests; Studio graceful fallback message. |
| Cross-domain Transform fidelity | `align_points` resampling; document supported morph pairs; `ReplacementTransform` fallback. |
| Point-array memory for large scenes | Use float32 numpy arrays; lazy point generation; instancing for repeated shapes. |
| Scope creep toward 3D | 3D explicitly deferred; camera designed to extend to 3D later without rework. |

## Validation Plan

- **Per phase:** unit tests in `tests/unit/<area>/`; `mypy --strict src/archmotion`; `ruff check`.
- **Engine parity:** architecture scenes render identically to v1 (golden frames / Lottie
  diff) after Phase 2.
- **Fusion smoke:** each Phase-5 example renders MP4 + Lottie + SVG + HTML; cross-domain
  `Transform` produces a valid morph (no point-count crash).
- **Export parity:** Lottie/SVG/HTML from generalized exporters are valid/playable.
- **Studio:** non-LaTeX scenes compile in-browser via Pyodide (after wheel rebuild).

## Out of Scope (v2.0)

- 3D scenes / GPU (OpenGL/moderngl) renderer — deferred to a later phase.
- Firebase Auth / Firestore cloud save, real-time collaboration (Studio Phase 2).
- Plugin system and premium icon packs (ROADMAP "Future").
- Server-side MP4 rendering.
- Audio/narration timeline (future compositing enhancement).
