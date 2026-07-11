# Phase 5 — v2.0 Release Readiness

> Predecessor: `.kilo/plans/1783651135849-phase2-architecture-parity.md` (Phase 2 parity — done)
> Roadmap lineage: `.kilo/plans/1783092584541-archmotion-v2-multi-domain-engine.md` Phase 5.
> Status: Implementation-ready · Final phase before v2.0 ships.

## Goal

Finish the v2.0 multi-domain engine so it is **shippable**: restore the parallel
MP4 render pipeline to v1 performance parity (multiprocessing pool + SharedMemory
zero-copy ring), fix the broken Studio Pyodide bridge, refresh all documentation
to the v2.0 module layout, complete the cross-domain fusion examples, and
implement the performance benchmark. After this phase `archmotion 2.0.0` renders
architecture scenes at v1 speed, the Studio runs in-browser, and the docs match
the shipped API.

## Context (verified against source)

- **Phases 0–4 are complete** — `core/`, all five `domains/`, `animation/`,
  `render/`, `exporter/` exist; **390 tests pass**; the v1→v2 cutover deleted
  `api/`, `renderer/`, `motions/`, `timeline/` (commit `f3a5a57`).
- **MP4 regression (centerpiece).** `render/frame.py:64` `render_scene()` is a
  **single-process** sequential `for` loop piping RGBA to FFmpeg. v1 had
  `exporter/{pool.py,shm.py,ffmpeg.py}` (deleted). The picklable building block
  `render_frame(FrameSpec)` (`render/frame.py:43`) already exists and is
  designed for pool distribution — VMobject/CompiledTimeline/Camera are pure data
  (numpy arrays + frozen dataclasses), no skia handles.
- **Studio is broken.** `studio/src/lib/pyodide.ts:59` runs
  `from archmotion.api.scene import Scene` (deleted module). `WHEEL_URL` (line 16)
  points at `archmotion-1.0.0` while `pyproject.toml` is `2.0.0`. The bridge loads
  `pydantic`+`pyyaml` but **not `numpy`**, which v2 now requires for point arrays.
- **Docs are stale.** `docs/index.md:21` imports `archmotion.motions` (deleted);
  `docs/architecture.md` references `timeline/compiler.py` + `Pool.imap()`
  (deleted) and a v0.2.0 theme table; `docs/api.md:11` autodocs
  `archmotion.api.scene.Scene` (deleted). `docs/examples.md` lists v1 scripts.
- **Benchmark is a stub.** `benchmarks/bench_render.py` is a `# TODO`.
- **Fusion examples incomplete.** Only `examples/v2_fusion_demo.py` exists (covers
  architecture+charts + one morph). Phase 5.2 of the v2 plan calls for 4 canonical
  cross-domain demos.
- **Constants already present:** `WORKER_RATIO=0.75`, `MAX_WORKERS=14`,
  `FFMPEG_PIPE_TIMEOUT=30` in `constants.py:151-158`. Exceptions
  `FFmpegNotFoundError`/`FFmpegCrashError` still in `errors.py:159,172`.
- **Remaining v1 import refs (cleanup):** `tests/unit/test_dx.py:207` asserts
  logger name `"archmotion.renderer"` (cosmetic; suite still green).

## Locked decisions

1. **Full v1 performance parity for MP4.** Restore `pool.py` + `shm.py` +
   `ffmpeg.py` adapted to v2 types, placed under **`render/`** (the v2 MP4 home —
   `exporter/__init__.py` docstring already states "MP4 video rendering lives in
   `archmotion.render.frame`"). Rejected alternative (simple `Pool.imap` pickle
   output): user explicitly chose v1 parity with the zero-copy SharedMemory ring.
2. **SharedMemory ring = output zero-copy (faithful port); input context shared
   once via Pool initializer (v2 improvement).** Each worker is initialized with
   the immutable context `(graphics, timeline, camera, width, height, bg, fps)`
   pickled exactly once at pool startup; each task sends only
   `(frame_index, shm_slot_name)`. This is strictly better than v1's per-frame
   input pickling while preserving the shm *output* ring verbatim.
3. **Graceful pickle fallback on shm failure** (as v1 had) — Windows/CI where
   `shared_memory` is flaky falls back to standard `imap` returning RGBA bytes.
   The parallel-pool benefit is preserved either way; only the output copy is
   re-introduced in fallback mode.
4. **NVENC encoder detection restored.** `ffmpeg.py` probes for `h264_nvenc`;
   falls back to `libx264`. 3-tier binary resolution (env `FFMPEG_BINARY` → PATH
   `shutil.which` → `imageio_ffmpeg.get_ffmpeg_exe`).
5. **Single-process `render_scene` is kept as the `workers=1` / fallback path**,
   not deleted — it doubles as the shm-unavailable fallback and a testable unit.
6. **Studio bridge = minimal surgical fix**, not a rewrite: correct the import,
   bump the wheel, add `numpy` to the Pyodide package load. The v2 `Scene` already
   exposes `to_layout_dict`/`to_lottie`/`to_svg`/`to_html`, so the bridge logic
   stays; only the import + wheel + numpy dep change.
7. **Docs = full v2.0 refresh** of all four `docs/*.md` + `mkdocs.yml` nav. New
   architecture diagram (property/morph-action timeline, not the deleted
   `timeline/compiler.py`), new module map, multi-domain section.
8. **Four canonical fusion examples** (Phase 5.2) replace/augment
   `v2_fusion_demo.py`. LaTeX example guards on `latex` availability.

## Ordered task list

### 1. `render/shm.py` — SharedMemory ring buffer (output zero-copy)
- Port the ring buffer from v1 `exporter/shm.py`: `SharedMemoryRing` context
  manager (PID+UUID slot names, `_DEFAULT_RING_SIZE=4`, fixed pre-allocated slots
  of `width*height*4` bytes), `render_frame_to_shm(spec, slot)` (worker writes
  RGBA into the slot), `iter_shm_render_args(total_frames, ring)` (yields
  `(frame_index, slot_name)` pairs in order), `close()`/`__exit__` that unlinks
  all slots (no leaks).
- Graceful fallback: if `SharedMemory` allocation raises (`FileExistsError`,
  `PermissionError`, platform limit), `SharedMemoryRing.create()` returns a
  sentinel that signals "use pickle path".

### 2. `render/ffmpeg.py` — FFmpeg binary + encoder selection + pipe
- `get_ffmpeg_path()`: 3-tier resolution (env → PATH → imageio-ffmpeg); raise
  `FFmpegNotFoundError` if all fail.
- `detect_encoder(ffmpeg_path)`: probe `h264_nvenc` via `ffmpeg -hide_banner
  -encoders`; return `"h264_nvenc"` if present else `"libx264"`.
- `FFmpegPipe` context manager: builds the rawvideo→RGBA stdin → libx264/nvenc
  → yuv420p MP4 command, exposes `write_frame(rgba_bytes)`, `close()` with
  `FFMPEG_PIPE_TIMEOUT` grace, raises `FFmpegCrashError` on non-zero exit
  (captures stderr). Single import site for `subprocess` (containment).

### 3. `render/pool.py` — parallel pool orchestrator
- `render_pool(scene, output_path, *, fps, crf, workers=None, on_progress=None)`
  → str: the public parallel entry replacing the sequential loop.
  - Compute `workers = min(int(cpu_count * WORKER_RATIO), MAX_WORKERS)` (default).
  - **Shared context:** build the immutable `(graphics, timeline, camera, width,
    height, bg)` once. Worker `initializer=_init_worker(ctx)` stores it in a
    module global; `initargs` pickles it once per worker.
  - **Output path:** attempt `SharedMemoryRing`; on success, task =
    `(frame_index, slot_name)`, worker calls `render_frame_to_shm`; main reads
    slot bytes → `FFmpegPipe.write_frame`. On failure, task = `frame_index`,
    worker returns RGBA bytes via `imap`; main pipes them.
  - `Pool.imap` (ordered) preserves frame sequencing for FFmpeg stdin.
  - `on_progress(completed, total)` callback after each yield; `show_progress`
    maps to a simple stderr callback (no tqdm dep).
  - `workers=1` short-circuits to the existing single-process `render_scene`.

### 4. Wire `Scene.render()` → parallel pool
- `core/scene.py:273` `render()`: replace the direct `render_scene(self, out)`
  call with `render_pool(...)`, threading `show_progress`/`on_progress`/`fps`/
  `crf`. Add `workers: int | None = None` param. Keep calling
  `self._prepare()` first (layout resolution).
- `render/frame.py`: keep `render_frame` (the per-frame unit) + the single-process
  `render_scene` (now the `workers=1` path / shm-fallback). Remove the hardcoded
  `libx264` — delegate codec to `ffmpeg.py.detect_encoder`.

### 5. Fix the Studio Pyodide bridge
- `studio/src/lib/pyodide.ts:16`: `WHEEL_URL` → `archmotion-2.0.0-py3-none-any.whl`.
- `studio/src/lib/pyodide.ts:31`: add `numpy` to
  `py.loadPackage(["micropip", "pydantic", "pyyaml", "numpy"])`.
- `studio/src/lib/pyodide.ts:59` (`BRIDGE_PY`): change
  `from archmotion.api.scene import Scene` → `from archmotion.core.scene import
  Scene`. Verify `_compile`/`_render_json`/`renderHtml` calls
  (`to_layout_dict`/`to_lottie`/`to_svg`/`to_html`/`parse_yaml_string`) still
  resolve against v2 — they do (verified in `core/scene.py`).
- **Rebuild the wheel:** `python -m build --wheel` from repo root → copy
  `dist/archmotion-2.0.0-py3-none-any.whl` to `studio/public/wheels/`. Remove the
  stale `archmotion-1.0.0` wheel.
- Confirm `total_duration` attribute exists on v2 Scene (bridge reads
  `scene.total_duration`); add a compat property if absent.

### 6. Refresh documentation to v2.0
- `docs/index.md`: fix import (`archmotion.animation`, not `.motions`); update
  Quick Start to v2 API (`from archmotion import Scene, Node, ...`); version
  2.0.0; features table gains a **Multi-Domain Fusion** row (geometry/charts/
  math/code + cross-domain `Transform`); update Requirements (numpy now core).
- `docs/architecture.md`: redraw the pipeline (Topology → Layout resolution →
  Timeline **property/morph actions** (`core/property.py`) → Render/Export);
  replace `timeline/compiler.py`/`Pool.imap` refs with `core/property.py` +
  `render/pool.py`; new module map (`core/`, `domains/`, `animation/`, `render/`,
  `exporter/`); add a Multi-Domain + Bezier-point-array section; update theme
  table to `render/theme.py` names; update Z-index narrative to the generic
  `z_index` field on `Graphic`.
- `docs/api.md`: replace every `::: archmotion.api.*` autodoc target with the v2
  homes — `archmotion.core.scene.Scene`, `archmotion.domains.architecture.*`,
  `archmotion.domains.geometry.*`, `archmotion.domains.charts.*`,
  `archmotion.domains.text.*`, `archmotion.animation.*`,
  `archmotion.render.theme.ThemeConfig`.
- `docs/examples.md`: list the v2.0 numbered examples + fusion demos with the v2
  import style.
- `mkdocs.yml`: verify nav order + that autodoc targets resolve (MkDocs build).

### 7. Fusion examples (Phase 5.2)
Create/complete four canonical cross-domain demos (each exports SVG+Lottie, MP4
when skia present):
- `examples/07_fusion_arch_metrics.py` — architecture diagram + live `BarChart`
  beside it (split from `v2_fusion_demo.py`).
- `examples/08_fusion_morph.py` — `Transform` a `Node` → `Circle` → `PieChart`
  (the cross-domain morph showcase).
- `examples/09_fusion_math_over_arch.py` — `MathText`/`Tex` equation derivation
  layered over an architecture diagram (`@skipif`-style guard if `latex` absent;
  print a clear message).
- `examples/10_fusion_code_walkthrough.py` — `CodeBlock` walkthrough with a
  data-flow `Transfer` packet animating alongside.
- Update `examples/README.md` to v2.0; keep `v2_fusion_demo.py` as the combined
  "best-of" showcase.

### 8. Benchmark (`benchmarks/bench_render.py`)
- Build a representative ~10s scene (architecture: 3 nodes + 2 connections + a
  `Transfer` + `FadeIn`; resolution 1080p/30fps → ~300 frames).
- Measure: wall-clock render time (parallel pool), effective fps
  (`total_frames / elapsed`), peak RSS (via `tracemalloc` for Python heap +
  `psutil`/`resource` for process RSS where available).
- Assert/report vs budgets: **< 30s for 10s video**, **peak RAM < 512MB**,
  **effective ≥ 60fps** (print PASS/FAIL per budget; non-zero exit on fail).
- Print worker count, encoder (nvenc/libx264), and shm-vs-pickle path used.

### 9. Tests + validation
- `tests/unit/render/test_pool.py` (new): mock FFmpeg; assert worker sizing
  formula; assert `workers=1` uses single-process path; assert `on_progress`
  fired `(total)` times; assert pickle-fallback when shm sentinel returned.
- `tests/unit/render/test_shm.py` (new): ring create/read/unlink; slot ordering;
  fallback sentinel on allocation failure (monkeypatch).
- `tests/unit/render/test_ffmpeg.py` (new): `get_ffmpeg_path` 3-tier (monkeypatch
  env/which/imageio); `detect_encoder` nvenc-present/absent branches; FFmpegPipe
  raises `FFmpegCrashError` on non-zero return.
- MP4 smoke: extend `tests/unit/render/test_renderer_v2.py` to render a tiny
  scene (e.g. 2 frames) to a real MP4 via `render_pool` and assert the file
  exists + non-zero size (skip if ffmpeg absent).
- Fix `tests/unit/test_dx.py:207` logger-name assertion (`renderer` → `render`)
  if it no longer matches the v2 logger.
- `mypy --strict src/archmotion && ruff check` clean on new/changed modules.
- Grep-guard: `rg "archmotion\.(api|renderer|motions|timeline)\b" src/
  studio/src` → **0** hits after the cleanup.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| SharedMemory flaky on Windows CI | Graceful pickle fallback preserved; tests monkeypatch the sentinel; `workers=1` path always available. |
| Pickling VMobject (numpy arrays) across the pool boundary | VMobject/CompiledTimeline/Camera are pure data (verified); initializer pickles context once, not per frame. |
| NVENC probe slow/fails on some hosts | `detect_encoder` cached + wrapped in try/except → libx264 fallback; never blocks rendering. |
| Wheel rebuild pulls skia into Pyodide | micropip install with pydantic/pyyaml/numpy pre-loaded skips the heavy skia/ffmpeg deps (same v1 strategy). |
| LaTeX absent for the math example | Example guards on availability + prints message; never errors the suite. |
| Docs autodoc targets miss after rename | `mkdocs build` is a validation gate; grep-guard catches stray `api.*` refs. |

## Validation plan

- `pytest tests/` 100% green (existing 390 + new pool/shm/ffmpeg tests).
- `python benchmarks/bench_render.py` prints all budgets PASS.
- `mkdocs build --strict` succeeds with no broken autodoc targets.
- `rg "archmotion\.(api|renderer|motions|timeline)\b" src studio/src` → 0 hits.
- `mypy --strict src/archmotion && ruff check` clean.
- A real MP4 renders via the parallel pool (`archmotion render scene.yaml -o
  out.mp4`) and is non-empty.
- Studio: `npm run build` succeeds; Pyodide `compileScene(yaml)` returns `ok:true`
  with layout+lottie after wheel swap (manual or Playwright smoke).

## Out of scope (future)

- 3D / GPU (OpenGL/moderngl) renderer.
- Firebase Auth / Firestore cloud save, real-time collaboration (Studio Phase 2).
- Plugin system + premium icon packs (ROADMAP "Future").
- Server-side MP4 rendering; audio/narration timeline.
- SharedMemory *input* context (graphics/timeline in shm) — the initializer
  pattern already shares it once; true shm-input is a later micro-opt.
