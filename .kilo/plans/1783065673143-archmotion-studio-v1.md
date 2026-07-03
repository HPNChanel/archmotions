# ArchMotion Studio v1 — Client-Side, Zero-Cost Web App

> Plan ID: 1783065673143 · Owner: ArchMotion · Status: Implementation-ready

## Goal

A zero-cost, browser-based "Studio" where users visually compose system-architecture
animations and export **MP4 / Lottie / SVG / HTML** — with **no server compute**. The
real `archmotion` Python package runs in the browser via **Pyodide**; MP4 is encoded in
the browser via **multi-threaded ffmpeg.wasm**. Hosted on **Firebase Hosting** (free tier)
with cross-origin-isolation headers. Zero ongoing cost; fully open-source.

## Context & Key Findings (verified against source)

- The **export path** (`YAML → Scene → resolve_layout → compile_timeline → Lottie/SVG/HTML`)
  is **pure Python**. The native deps (`skia`, `Pillow`, `imageio-ffmpeg`) are used **only**
  on the MP4 path (`renderer/canvas.py`, `renderer/painters.py`, `exporter/ffmpeg.py`).
  Therefore the package runs in **Pyodide unchanged** — only `pydantic` + `pyyaml` are
  needed, both shipped by Pyodide.
- **Coordinate space is top-left origin, y-down** (`BoundingBox.x/y` at `layout/bbox.py`).
  Identical to SVG/Canvas/React Flow → freeform drag maps 1:1.
- **Node size is engine-estimated from label text** (`estimate_text_bbox`,
  `constants.GRID_UNIT=80`, monospace approximation). The canvas therefore **reads the
  resolver's `node_boxes`** and renders nodes at those exact boxes; dragging only sets the
  top-left `(x,y)`, then re-resolves. Sizes stay consistent with the engine.
- v1 is **backend-free** (`localStorage`). Firebase Hosting is used **only** for static
  hosting + COOP/COEP headers (enables multi-threaded ffmpeg.wasm). No Auth/Firestore.

## Locked Decisions

1. **Direction:** client-side web app, zero server compute, open-source.
2. **MP4:** in-browser via multi-threaded `ffmpeg.wasm`.
3. **Engine:** Pyodide runs the real `archmotion` wheel (no TS port, no logic duplication).
4. **Stack:** React + TypeScript + Vite + React Flow (`@xyflow/react`) + CodeMirror 6.
5. **v1 scope:** YAML editor + visual drag-drop canvas + live Lottie preview + theme picker
   + template gallery + export (Lottie/SVG/HTML/MP4) + `localStorage` save/load. No Auth/Firestore.
6. **Position model:** freeform absolute positions → **add absolute-position support to the
   Python engine** (additive, backward-compatible). Relative model stays the default.
7. **Hosting:** Firebase Hosting (free tier) + COOP/COEP headers → MT ffmpeg.wasm.

---

## Workstream A — Python Engine (additive, backward-compatible)

All changes must keep the existing 460+ tests green and `mypy --strict` / `ruff` clean.

### A1. Absolute positioning — primitives
File: `src/archmotion/api/primitives.py`
- Add `AbsolutePosition` dataclass: `{ x: float, y: float }` (top-left, pixels).
- Change `Node.position` type to `RelativePosition | AbsolutePosition | None`.
- Add `Node.at(x: float, y: float) -> Self` fluent method that sets an `AbsolutePosition`.
  - Reuse the existing "position set once" guard in `_set_position` (raise `TopologyError`
    if already positioned). Extract a shared `_mark_positioned(...)` if needed.
  - Validate `x >= 0`, `y >= 0` (upper bound validated against canvas in the builder).

### A2. Absolute positioning — layout resolver
File: `src/archmotion/layout/resolver.py`
- `_topological_sort`: treat `AbsolutePosition` nodes as **roots** (`in_degree=0`, no anchor
  dependency). They must not trigger `OrphanNodeError`.
- `_assign_coordinates`: if `isinstance(node.position, AbsolutePosition)` →
  `center_x = pos.x + bbox_width/2`, `center_y = pos.y + bbox_height/2`. Else existing logic.
- `_center_on_canvas`: if **any** node is absolute → **skip centering** (manual layout mode).
  (Detection: scan `layout_nodes` once for an `AbsolutePosition`.)
- `_check_overflow`: keep as-is (UI clamps dragging so it normally won't trigger). Document
  that freeform drags off-canvas will raise `OverflowCanvasError` — the Studio clamps in UI.

### A3. Schema + builder (YAML AI Interface)
Files: `src/archmotion/ai/schema.py`, `src/archmotion/ai/builder.py`
- `schema.py`: turn `PositionSpec` into a **discriminated union**:
  - `RelativePositionSpec { anchor, direction, distance }` (existing).
  - `AbsolutePositionSpec { x: float (ge=0), y: float (ge=0) }`.
  - `NodeSpec.position: RelativePositionSpec | AbsolutePositionSpec | None`.
- `validate_references`: only run the anchor checks for `RelativePositionSpec` instances.
- `builder.py` Phase 2: branch on kind — relative → existing method call;
  absolute → `node.at(spec.x, spec.y)`.
- Validate absolute coords against the scene resolution bounds
  (`RESOLUTION_MAP[spec.resolution]`) in `SceneSpec` model validator; clear error message.

### A4. In-memory export helpers (Pyodide-friendly)
File: `src/archmotion/api/scene.py`
- Add `Scene.to_lottie(*, minify=False) -> dict`, `Scene.to_svg() -> str`,
  `Scene.to_html(title=...) -> str`. These run Phases 1–3 and call the existing
  `build_lottie_json` / `build_animated_svg` / HTML template **in-memory** (no `Path`/disk).
- Also expose resolved layout for the canvas: add `Scene.resolve() -> ResolvedLayout`
  (Phases 1–3 only) so the Studio can read `node_boxes` + `connection_routes`.
- Keep file-based `Scene.render()` / `Scene.export()` unchanged.

### A5. Tests
- `tests/unit/layout/`: absolute-only layout; mixed absolute+relative; centering disabled
  when an absolute node exists; overflow still enforced.
- `tests/unit/api/`: `Node.at()` sets absolute; double-position raises; `Scene.to_*`/`resolve()`.
- `tests/unit/ai/`: YAML `position: {x, y}` parses/builds; invalid coords rejected; mixed.
- Run `pytest tests/`, `mypy --strict src/archmotion`, `ruff check` — all must pass.

### A6. Wheel for Pyodide
- `python -m build --wheel` produces a pure-Python wheel (deps `pydantic`, `pyyaml` only —
  both available in Pyodide; no `skia`/`Pillow` needed for the export path).
- CI drops the built wheel into `studio/public/wheels/archmotion-<ver>-py3-none-any.whl`
  so Pyodide loads it as a static asset (no external CDN dependency).

---

## Workstream B — Web App (`studio/`, new monorepo dir)

### B1. Repo structure & tooling
- New top-level `studio/` (monorepo). Root `pyproject.toml` untouched.
- `studio/package.json` deps: `react`, `react-dom`, `@xyflow/react`, `@uiw/react-codemirror`
  (+ `@codemirror/lang-yaml`), `pyodide`, `@ffmpeg/ffmpeg` + `@ffmpeg/core-mt`, `zustand`,
  `lottie-web`; dev: `vite`, `typescript`, `eslint`, `@types/*`.
- `studio/` owns its own `tsconfig.json` + eslint config.

### B2. Pyodide integration (`src/lib/pyodide.ts`)
- **Lazy** init (not on page load) behind a "Launch Studio" gate; singleton; show progress.
- Steps: load Pyodide core → `loadPackage(["pydantic","pyyaml"])` →
  `micropip.install("/wheels/archmotion-<ver>-py3-none-any.whl")`.
- Typed API: `compileScene(yaml): Promise<{ lottie, svg, html, layout, timeline } | { error }>`.
  Calls Python `parse_yaml_string` → `Scene.resolve()` + `Scene.to_lottie/to_svg/to_html`.
- Surface `YAMLParseError` field paths to the editor for inline markers.

### B3. State (Zustand)
- Store: `yamlText`, `parsed` (SceneSpec|null), `error`, `theme`, `layout` (boxes/routes),
  `selectedNodeId`, `scenes` (localStorage list), `exportFormat`.
- **YAML is the single source of truth.** Debounced re-parse on YAML change → updates layout
  + canvas. Canvas drag → surgically patch that node's `position: {x,y}` in the YAML text →
  re-parse → re-resolve. On parse failure: keep last valid layout + show error banner.

### B4. Visual editor — React Flow (`src/features/editor/`)
- Custom node components for the 6 primitives (Node/Database/Cloud/Queue/Cache/User),
  themed renderers keyed off `primitive_type`.
- Nodes positioned/sized from the engine's resolved `node_boxes` (`x,y,width,height`).
- On drag stop → write new top-left `(x,y)` into YAML `position: {x, y}` → re-resolve.
  Drag is **clamped to canvas bounds** (resolution-aware) so overflow never triggers.
- Edges from connections; use **custom React Flow edges** that draw the engine's
  `connection_routes` polylines (A*-routed) and disable React Flow's own routing.
- Add-node palette (type + label), connect via handles, select→edit label/type in side panel,
  delete node/edge.

### B5. YAML editor — CodeMirror 6 (`src/features/yaml/`)
- YAML language + lint via Pyodide parse result (inline error markers with field paths).
- Edit YAML → updates canvas; parse errors do **not** blank the canvas.

### B6. Live preview — Lottie (`src/features/preview/`)
- `lottie-web` renders `to_lottie()` output with play/pause/scrub/speed/loop controls
  (mirror the existing HTML player control patterns). Debounced re-render on change.

### B7. Theme picker + template gallery
- Theme picker (4 themes) → writes `scene.theme` in YAML.
- Template gallery: ship YAML versions of the 6 examples at
  `studio/src/templates/*.yaml`; click loads into editor.

### B8. Export pipeline (`src/features/export/`)
- **Lottie/SVG/HTML:** direct download of `to_lottie()`/`to_svg()`/`to_html()`.
- **MP4:** in a **Web Worker** — lottie-web renders frame-by-frame to an offscreen canvas
  (`goToAndStop(frame)` + canvas renderer), capture each frame, feed to `@ffmpeg/ffmpeg`
  (MT core): write numbered frames to MEMFS, run
  `-framerate <fps> -i frame_%d.png -c:v libx264 -pix_fmt yuv420p out.mp4`, read + download.
  Progress bar; non-blocking.

### B9. Persistence (localStorage)
- Versioned key; save/load named scenes `{ id, name, yamlText, updatedAt }`. List/duplicate/delete.

### B10. Hosting + deploy
- `studio/firebase.json`: hosting `public = studio/dist`; SPA rewrite to `index.html`;
  **headers**: `Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy: require-corp`
  on all routes (enables SharedArrayBuffer for MT ffmpeg.wasm).
- `.github/workflows/`: on push to `main` → build Python wheel → `npm run build` in `studio/`
  → `firebase deploy` (secrets). Runtime guard: if `self.crossOriginIsolated === false`,
  fall back to the single-threaded ffmpeg core.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Pyodide ~15MB first-load | Lazy-load behind gate; service-worker cache; progress UI. Acceptable for v1. |
| ffmpeg.wasm MT needs cross-origin isolation | Firebase Hosting COOP/COEP headers; runtime `crossOriginIsolated` guard + ST fallback. |
| Node size mismatch (canvas vs engine) | Canvas always reads engine `node_boxes`; drag only sets top-left; re-resolve keeps sizes consistent. |
| Bidirectional YAML↔canvas sync | YAML is single source of truth; canvas edits patch one node's position then re-parse; keep last-valid on error. |
| `OverflowCanvasError` on freeform drag | UI clamps drag within canvas bounds; engine overflow check remains a safety net. |
| Backward compatibility | Absolute positioning is purely additive; existing tests stay green; relative is the default. |

## Validation Plan

- **Python:** `pytest tests/` 100% pass; new tests for absolute/mixed; `mypy --strict`; `ruff`.
- **Studio:** `npm run build` + `tsc --noEmit` + eslint clean. Manual smoke per template: drag a
  node, edit YAML, preview plays, export all 4 formats; exported MP4 is a valid playable file.
- **Hosting:** deployed site reports `self.crossOriginIsolated === true`; MT ffmpeg.wasm loads.

## Out of Scope (v1)

- Firebase Auth / Firestore cloud save & sharing (Phase 2).
- Collaborative / multi-user editing.
- Premium icon packs; plugin system.
- Server-side MP4 rendering.
- Visual editor features beyond drag/connect/edit/delete (e.g. grouping, re-parenting anchors).

## Open Questions

None blocking — all major decisions resolved above.
