# Architecture Deep-Dive

ArchMotion v2.0 is a **multi-domain animation engine**: every vector graphic shares
a **point-array Bézier geometry**, so any two shapes can `Transform` into each other.
Architecture animation remains a first-class domain (DAG layout, A\*-routed
connections, data-flow packets) fused with general-purpose graphics.

> **v2.0 support boundary:** MP4 and PNG are production-MVP outputs. Lottie,
> SVG, HTML, Studio, shared-memory tuning, and hardware encoding are
> experimental. ArchMotion is not API-compatible with Manim; see
> [MVP status](https://github.com/archmotion/archmotion/blob/main/MVP_STATUS.md).

---

## Pipeline Overview

```mermaid
graph LR
    subgraph "Topology"
        A["Scene + Graphics (VMobjects)"]
    end
    subgraph "Layout"
        B["Resolved positions + routes"]
    end
    subgraph "Timeline"
        C["CompiledTimeline\n(PropertyAction + MorphAction)"]
    end
    subgraph "Render / Export"
        D["FrameSpec × N"]
        E["MP4 / PNG\n+ experimental vector exports"]
    end

    A -->|"resolve_architecture()"| B
    B -->|"compile_timeline()"| C
    C -->|"render_pool()" / build_*()"| D
    D -->|"Pool.imap() + FFmpegPipe"| E
```

---

## Module Layout (v2.0)

```
src/archmotion/
  core/                 Foundation
    graphic.py          Graphic base (id, z_index, transform, style, opacity, parent)
    vmobject.py         VMobject — point-array Bézier base (generate_points, interpolate)
    camera.py           Camera — scene-units ↔ pixels viewport
    scene.py            Scene — virtual clock, play/wait, layout, render/export
    transform.py        Affine 3×3 transform
    style.py            Style dataclass (fill/stroke colors + opacities)
    color.py            Shared strict CSS color normalization
    updaters.py         ValueTracker + frame-local always_redraw support
    pathops.py          Bézier utilities (length, point-at-t, resample, align)
    property.py         Property enum + PropertyAction/MorphAction + CompiledTimeline
  animation/
    base.py             Animation base/groups, .animate, creation, writing, transforms
    recipes.py          Transfer, Pulse, Highlight, ColorShift, ScaleUp/Down
  render/
    path_render.py      Generic VMobject → Skia painter (one renderer for ALL shapes)
    frame.py            FrameSpec + render_frame (single-frame) + render_scene (single-process)
    pool.py             Single/parallel frame orchestration → MP4
    shm.py              Optional SharedMemory ring buffer
    ffmpeg.py           CPU H.264 baseline + opt-in probed NVENC + stdin pipe
    canvas.py           Skia canvas wrapper
    theme.py            ThemeConfig + THEMES (4 themes)
    tex.py              LaTeX → dvisvgm → VMobject points (math domain)
    text_glyphs.py      Glyph-path extraction from text
  domains/
    architecture/       Node/Database/Cloud/Queue/Cache/User + Connection + Packet + layout
    geometry/           Circle, Rectangle, Square, Line, Arrow, Polygon, Arc, Dot, Axes, ...
    charts/             BarChart, LineChart, PieChart, ScatterPlot
    text/               Text, Paragraph, MarkupText
    math/               MathText, Tex (LaTeX)
    code/               CodeBlock (Pygments syntax highlight)
  exporter/
    lottie_v2.py        VMobjects → Lottie JSON shape layers
    svg_v2.py           VMobjects → animated SVG (CSS @keyframes)
    html_v2.py          Self-contained lottie-web HTML player
  ai/                   YAML schema (Pydantic) + builder → Scene
  loader.py             Isolated Python Scene module loading
  dx/, errors.py, constants.py, __main__.py
```

---

## Topology & Layout

The user composes a scene graph of VMobjects. Architecture primitives support
**relative positioning** (resolved in an explicit layout pass):

```python
db.right_of(gateway, distance=4)  # 4 grid units right
cache.below(gateway, distance=3)  # 3 grid units below
```

The **Layout Resolver** (`domains/architecture/layout.py`) converts relative
positioning into absolute pixel coordinates:

1. Build a DAG from position dependencies.
2. Topological sort (Kahn's algorithm) to determine evaluation order.
3. Convert grid units → pixel offsets (1 unit = `GRID_UNIT` = 80px).
4. Assign a `BoundingBox` to each node via text-size estimation.
5. Center the diagram on the canvas.
6. Route connections using **A\* obstacle-aware Manhattan routing** with optional
   waypoints + rounded corners.

**Output:** `node_boxes` (pixel-perfect bounding boxes) + `connection_routes`
(routed polylines), applied to the graphics via `move_to()`.

Layout is **opt-in** — call `scene._prepare()` (done automatically by
`render`/`export`) or `resolve_architecture(scene, ...)`.

---

## Timeline Compilation

Animations compile into a pure-data `CompiledTimeline` (`core/property.py`):

- **PropertyAction** — a scalar tween (`OPACITY`, `SCALE`, `POSITION_X/Y`,
  `FILL_R/G/B`, `GLOW_INTENSITY`, `PATH_PROGRESS`, `CREATE_PROGRESS`, …) with
  `O(1)` `value_at(t)` interpolation and easing.
- **MorphAction** — a whole-point-array morph (cross-domain `Transform`): the
  renderer sets the graphic's Bézier points to `lerp(source, target, eased(t))`.

| Animation | Resolves to |
|---|---|
| `FadeIn(node)` / `FadeOut(node)` | `OPACITY: 0 → 1` / `1 → 0` |
| `Create(node)` / `Write(text)` / `Uncreate` | `CREATE_PROGRESS: 0 → 1` / `1 → 0` (path-trim) |
| `DrawBorderThenFill(node)` | `CREATE_PROGRESS` + `FILL_OPACITY` (stroke then fill) |
| `Transform(a, b)` / `ReplacementTransform` | `MorphAction` (point-array interpolation) |
| `Transfer(conn)` | `PATH_PROGRESS: 0 → 1` (packet slides along route) |
| `Pulse(node)` | `GLOW_INTENSITY: 0 → peak → 0` |
| `Highlight(node)` | `GLOW_INTENSITY: 0 → intensity` (persistent) |
| `ColorShift(node)` / `FadeToColor(node)` | `FILL_R/G/B: from → to` |
| `ScaleUp` / `ScaleDown` | `SCALE: 1 → factor` / `factor → 1` |
| `GrowFromCenter` / `GrowFromEdge` | `SCALE: 0 → 1` + `OPACITY: 0 → 1` (+ position) |
| `GrowBar(bar)` | `MorphAction` (zero-height → full) |
| `DrawLine(line)` / `SweepPie(pie)` | `CREATE_PROGRESS: 0 → 1` (progressive draw) |
| `Flash` / `Indicate` | `SCALE` + `GLOW`/`FILL` spike (up then back) |
| `Typewriter(text)` | `CREATE_PROGRESS: 0 → 1` (linear, approximate per-glyph) |

`CompiledTimeline.snapshot_at_frame(frame)` resolves the full per-target state —
scalars + active morphs — in one pass.

---

## Render & Export

### MP4 and PNG production path

1. **Construct once** — run the Scene lifecycle, resolve layout, compile the
   timeline, and collect paintable VMobjects.
2. **Evaluate frames** — apply timeline snapshots, hierarchy transforms, theme
   inheritance, and frame-local updaters.
3. **Paint canonical RGBA** — Skia uses an explicitly RGBA raster surface on
   every OS; platform-native `N32` is intentionally avoided because it is BGRA
   on Windows.
4. **Encode** — raw RGBA streams directly to FFmpeg `libx264`/`yuv420p` with no
   intermediate image sequence. PNG stills pass the same bytes to Pillow.

Windows defaults to one process to make normal scripts safe under spawn.
Updater-driven scenes also force one process. Other scenes/platforms may use a
worker pool; the SharedMemory ring and hardware encoders are opt-in experimental
optimizations rather than release requirements.

```python
scene.render("out.mp4")                    # reliable platform default
scene.render("out.mp4", workers=1)         # deterministic explicit baseline
scene.render("out.mp4", show_progress=True)
scene.save_frame("out.png")                # final scene frame
```

### Generic path renderer

A **single** renderer (`render/path_render.py`) paints every VMobject: it builds a
Skia `Path` from the Bézier control points, applies the graphic's transform +
camera matrix, and fills/strokes per `style`. This replaces per-type painters and
is what makes cross-domain `Transform` possible.

### Experimental vector exports (Skia-free)

`exporter/{lottie_v2,svg_v2,html_v2}.py` consume the point-array graphics +
compiled actions directly — no Skia/FFmpeg needed, so they run in the browser
(ArchMotion Studio / Pyodide). They are structurally tested but do not yet carry
the MP4 visual-parity guarantee.

---

## Multi-Domain Fusion

The v2.0 differentiator: any domain coexists in one scene, and any two VMobjects
share point-array geometry so they can `Transform`:

```python
from archmotion.domains.geometry import Circle
from archmotion.domains.charts import PieChart
from archmotion.animation import Transform

# Morph a database node into a circle, then into a pie chart:
scene.play(Transform(db, Circle(radius=55).move_to(520, 270)))
scene.play(Transform(db, PieChart([3, 7, 5, 9], radius=60, center=(760, 340))))
```

Point-count and contour alignment handles mismatched topologies via resampling.

---

## Theme System

Four themes, each a frozen `ThemeConfig` (`render/theme.py`):

| Theme | Style | Best For |
|---|---|---|
| `dark_terminal` | Dark background, muted colors *(default)* | Technical presentations |
| `neon_cyber` | Deep black + neon glows (cyan, magenta) | Eye-catching demos |
| `blueprint` | Blue background, white wireframe | Engineering documentation |
| `light_paper` | White background, dark borders | Reports, slides, print |

```python
scene = Scene(theme="neon_cyber")
```

---

## YAML AI Interface

The `archmotion.ai` package lets LLMs generate YAML that compiles into animated
videos:

```
User → "Draw an OAuth2 flow"
  → LLM reads prompt_template.md
  → LLM generates YAML
  → parse_yaml_string(yaml) → Scene
  → scene.render() → video.mp4
```

Security: `yaml.safe_load()` only, size limit, Pydantic validation, no `eval()`.
