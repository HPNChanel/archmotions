# Phase 6 — Animation Catalog & Domain Completion

> Predecessor: `.kilo/plans/1783740568483-phase5-v2-release-readiness.md` (Phase 5 — done)
> Status: Implementation-ready · Completes the v2.0 multi-domain feature surface.

## Goal

Build every animation and domain class the v2.0 plan specified but that were
never implemented. After this phase, the animation catalog matches the full
Manim-competitive surface (`Write`, `Uncreate`, `DrawBorderThenFill`,
`ReplacementTransform`, chart animations, growth/indicator recipes) and every
domain (geometry, charts, text, code, math) has its planned class set complete.

## Context (verified against source)

- The **animation compilation model** is uniform: each `Animation` subclass
  implements `targets()`, `begin()`, `compile(start_time) -> list[PropertyAction |
  MorphAction]`, `finish()`. The `_scalar(...)` helper builds single
  `PropertyAction`s; `MorphAction` handles point-array morphing; `_color_tween`
  emits FILL_R/G/B tweens. All in `animation/base.py` + `recipes.py`.
- **The property model** (`core/property.py` + `render/path_render.py`) already
  supports every property the new animations need: `CREATE_PROGRESS` (path-trim
  via `PathMeasure.getSegment`), `SCALE` (centered transform), `OPACITY`,
  `FILL_OPACITY`, `FILL_R/G/B`, `POSITION_X/Y`, `GLOW_INTENSITY`, `ROTATION`,
  `STROKE_*`. **No renderer or property-model changes are needed.**
- `CREATE_PROGRESS` trims the entire skia path (all contours) — so for multi-
  glyph `Text` / `CodeBlock` / `MathText`, path-trim reveals glyphs in reading
  order. This powers `Write`, `DrawLine`, `SweepPie` with zero renderer changes.
- **SCALE is uniform** (centered at the graphic's bbox center, `path_render.py:104-107`).
  There is no per-axis SCALE — so `GrowBar` uses a `MorphAction` (collapse-to-
  bottom points → full-height points) instead of a Y-only scale.
- **Missing classes (confirmed):** `Write` (the single most-referenced gap —
  code/math/text docstrings assume it exists), `Uncreate`,
  `DrawBorderThenFill`, `ReplacementTransform`, `Flash`, `Indicate`,
  `FadeToColor`, `GrowFromCenter`, `GrowFromEdge`, `GrowBar`, `DrawLine`,
  `SweepPie`, `Typewriter` (animations); `ScatterPlot`, `Paragraph`,
  `ArcBetweenPoints`, `Brace`, `Bezier`, `NumberPlane` (domain classes).

## Locked decisions

1. **`Write` = path-trim** (user-confirmed). Uses `CREATE_PROGRESS` 0→1 on the
   text's whole path — glyphs reveal continuously in reading order. Same
   mechanism as `Create`, distinct class for semantic clarity + text-tuned
   default easing. `Typewriter` = same mechanism with a stepped rate function
   (approximates per-glyph; true per-glyph splitting is a future enhancement).
2. **No renderer/property-model changes.** Every animation is expressible with
   the existing `PropertyAction`/`MorphAction` compilation model.
3. **`GrowBar` = `MorphAction`** (zero-height → full-height bar), not a Y-only
   scale (which the uniform SCALE property can't express).
4. **Add to existing files** (`base.py`, `recipes.py`, `shapes.py`,
   `coordinate_systems.py`, `charts.py`, `text.py`). No full modular-file
   reorganization (the plan's 7-file split is out of scope — current 2-file
   layout works).
5. **Export all new classes** from their domain `__init__.py` + the animation
   `__init__.py`. Add `Write`, `Transform`, `AnimationGroup`, `Create` to the
   top-level `archmotion` package (they're the headline v2 features currently
   requiring deep import paths).
6. **`ReplacementTransform`** = `Transform` whose `finish()` commits the
   **original** target points (not the aligned/resampled ones). The morph itself
   uses aligned points for smoothness; only the committed end-state is exact.

## Ordered task list

### 1. Creation animations (`animation/base.py`)
- **`Write(target, run_time=1.0, rate_func="smooth")`** — `CREATE_PROGRESS`
  0→1, `finish()` sets opacity 1.0. Subclass-of-`Create`-pattern; distinct class
  for text/code/math semantic. Update `codeblock.py:6` + `mathtext` docstrings
  to reference it.
- **`Uncreate(target, run_time=1.0, rate_func="smooth")`** — reverse: emits
  `CREATE_PROGRESS` 1→0; `begin()` no-op; `finish()` sets opacity 0.0.
- **`DrawBorderThenFill(target, run_time=1.0, rate_func="smooth")`** — two-phase
  compile: `CREATE_PROGRESS` 0→1 over `[t, t+rt/2]`, then `FILL_OPACITY` 0→1
  over `[t+rt/2, t+rt]`. `begin()` captures the target's original
  `fill_opacity` and sets it to 0; `finish()` restores it.
- **`Typewriter(target, run_time=1.0)`** — `CREATE_PROGRESS` 0→1 with a
  stepped/"linear" rate that approximates discrete glyph reveal.

### 2. Transform variant (`animation/base.py`)
- **`ReplacementTransform(source, target, run_time=1.0, rate_func="smooth")`** —
  like `Transform` (aligned morph in `compile`), but `finish()` sets
  `source.points = target.points` (the **original** target points, not
  `aligned_tgt`) + `source.style = target.style`.

### 3. Growth animations (`animation/base.py`)
- **`GrowFromCenter(target, run_time=1.0, rate_func="smooth")`** — `begin()`
  sets opacity 0. `compile()` emits `SCALE` 0→1 + `OPACITY` 0→1 over the full
  interval. `finish()` sets opacity 1.0.
- **`GrowFromEdge(target, edge="bottom", run_time=1.0, rate_func="smooth")`** —
  same as GrowFromCenter plus a `POSITION_X`/`POSITION_Y` tween that keeps the
  specified edge stationary as the centered scale goes 0→1. Compute the edge
  offset from `target.bounding_box()` in `begin()`; emit position tweens in
  `compile()`.
- **`GrowBar(bar, run_time=1.0, rate_func="smooth")`** — `begin()` captures the
  bar's full-height points, builds a zero-height variant (collapse all Y to the
  bottom Y), stores both. `compile()` emits a `MorphAction(zero → full)`.
  `finish()` commits the full points. Accepts a `Rectangle`/`BarChart` bar.

### 4. Chart animations (`animation/recipes.py`)
- **`DrawLine(line, run_time=1.0, rate_func="smooth")`** — `CREATE_PROGRESS`
  0→1 on a `LineChart` or `Line`/`Polyline` target (progressive stroke draw).
- **`SweepPie(pie, run_time=1.0, rate_func="smooth")`** — `CREATE_PROGRESS`
  0→1 on a `PieChart` target (slices reveal in path order).

### 5. Indicator / effect animations (`animation/recipes.py`)
- **`Flash(target, run_time=0.5, rate_func="ease_out")`** — brief emphasis:
  `SCALE` 1→1.5→1 (peak at midpoint) via two `PropertyAction`s, plus a
  `GLOW_INTENSITY` 0→1→0 spike. `begin()`/`finish()` no state mutation.
- **`Indicate(target, run_time=0.5, rate_func="ease_out")`** — scale up slightly
  (`SCALE` 1→1.1→1) + fill color flash to a highlight color and back.
- **`FadeToColor(target, color, run_time=0.8, rate_func="smooth")`** —
  convenience wrapper: reads the target's current `style.fill_color` as
  `from_color`, emits FILL_R/G/B tween to `color`. `finish()` commits
  `target.set_fill(color)`.

### 6. Geometry shapes (`domains/geometry/shapes.py`)
- **`ArcBetweenPoints(start, end, *, angle=90.0, ...)`** — quadratic/cubic
  bezier arc from `start` to `end` with `angle` degrees of curvature. Compute
  the control point from the perpendicular bisector + sagitta.
- **`Bezier(control_points, ...)`** — cubic bezier from an explicit list of
  `(x, y)` control points (chain of cubic segments). Distinct from `Polyline`
  (which uses only anchor points).
- **`Brace(target, *, direction="left", ...)`** — curly-brace outline pointing
  at `target`. Generate the brace as two mirrored quadratic-cubic humps scaled
  to the target's extent.

### 7. Coordinate system (`domains/geometry/coordinate_systems.py`)
- **`NumberPlane(x_range=(-10,10), y_range=(-6,6), ...)`** — a `VGroup` of two
  `NumberLine`s (x-axis horizontal, y-axis vertical) plus evenly-spaced grid
  lines. Reuse `NumberLine` for axes + tick labels.

### 8. Charts (`domains/charts/charts.py`)
- **`ScatterPlot(points, *, x_range, y_range, ...)`** — a `VGroup` containing
  an `Axes` (or reuse `NumberLine` pair) + a `Dot` at each mapped `(x, y)` data
  point. Accepts `list[tuple[float, float]]`.

### 9. Text (`domains/text/text.py`)
- **`Paragraph(lines, *, line_spacing=1.2, family, size, ...)`** — a `VGroup`
  of `Text` objects, one per line (accepts a multi-line string or `list[str]`).
  Vertically stack each line by its bbox height × `line_spacing`.

### 10. Exports + public API
- `animation/__init__.py`: add `Write, Uncreate, DrawBorderThenFill,
  ReplacementTransform, GrowFromCenter, GrowFromEdge, GrowBar, DrawLine,
  SweepPie, Flash, Indicate, FadeToColor, Typewriter` to imports + `__all__`.
- Domain `__init__.py`s: add `ArcBetweenPoints, Brace, Bezier, NumberPlane`
  (geometry), `ScatterPlot` (charts), `Paragraph` (text).
- `archmotion/__init__.py`: add `Write, Transform, AnimationGroup, Create` to
  the top-level exports (headline v2 features currently buried in deep paths).

### 11. Tests (`tests/unit/animation/` + `tests/unit/domains/`)
- **Animation tests** (`test_catalog.py`): for each new animation, assert
  `compile()` emits the expected `PropertyAction`/`MorphAction` (correct prop,
  start/end values, timing); assert `begin()`/`finish()` set the right state.
  Smoke-render (SVG export) a scene using each new animation.
- **Domain tests** (`test_geometry.py` extend, `test_charts.py` extend,
  `test_text_code.py` extend): assert `generate_points()` produces non-empty
  point arrays; assert shapes have correct point counts / bbox extents;
  Paragraph produces N children; ScatterPlot maps data points correctly.
- `mypy --strict` + `ruff check` clean on all new/changed modules.

### 12. Examples + docs
- Update `examples/09_fusion_math_over_arch.py` + `10_fusion_code_walkthrough.py`
  to use `Write` (currently use `Create` as a workaround).
- Add `examples/11_chart_animations.py` showing `GrowBar` + `DrawLine` +
  `SweepPie` on live chart data.
- Update `docs/api.md` autodoc targets for the new classes.
- Update `docs/architecture.md` animation table.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| `GrowBar` MorphAction with mismatched point counts | Zero-height variant built by collapsing the SAME points' Y (preserves count); alignment is implicit (same count). |
| `GrowFromEdge` position offset math wrong | Compute offset from `bounding_box()` in `begin()`; unit-test that the edge stays fixed at t=0 and t=1. |
| `Write` on `CodeBlock` (VGroup of Text spans) | `CREATE_PROGRESS` applies per-target-ID; `CodeBlock` is a VGroup — `Write` must target the group or each span. Document: pass the `CodeBlock` (group handles it) or iterate spans in an `AnimationGroup`. |
| `Brace` shape geometry imprecise | Use the standard 4-hump cubic approximation; test bbox extent matches target. |
| Typewriter not truly per-glyph | Documented as approximate (path-trim with stepped easing); true per-glyph is explicitly future work. |

## Validation plan

- `pytest tests/` 100% green (existing + new catalog/domain tests).
- `mypy --strict src/archmotion && ruff check` clean on new modules.
- Each new animation smoke-renders to SVG without error.
- `examples/11_chart_animations.py` renders SVG + Lottie.
- `from archmotion import Write, Transform, AnimationGroup, Create` succeeds
  (top-level export check).

## Out of scope (future)

- True per-glyph `Write`/`Typewriter` via renderer-level per-contour progress.
- Modular animation file reorganization (creation.py / fading.py / ...).
- Correctness fixes (YAMLParseError hierarchy, export errors, README staleness)
  — separate "polish" phase.
- `NumberPlane` interactive features (zoom, pan) — static grid only here.
