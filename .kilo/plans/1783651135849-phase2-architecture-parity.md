# Phase 2 — Architecture Domain Parity (v2.0)

> Predecessor plan: `.kilo/plans/1783092584541-archmotion-v2-multi-domain-engine.md` (Phase 2 of the v2.0 plan).
> Status: Implementation-ready · Follow-on: v1→v2 cutover (CLI/AI/`__init__`/tests/Studio) is a separate phase.

## Goal

Finish the **half-done architecture-domain migration** so the v2 engine reaches **parity with v1** for architecture scenes. This unblocks (but does NOT perform) the foundational v1→v2 cutover.

Concretely, after this phase a v2 scene built with `archmotion.domains.architecture` must reproduce v1 behavior: relative positioning (`.right_of()/.below()/.at()`), DAG layout resolution + canvas centering, **A\* obstacle-aware Manhattan routing** with waypoints + rounded corners, the `Packet`/`Transfer` data-flow animation, and correct MP4/Lottie/SVG output — with **no imports from v1 packages** (`api/`, `renderer/`, `motions/`).

## Context & verified findings

- v2 multi-domain engine Phases 0–1, 3–4 are **done** (`core/`, `domains/{geometry,charts,text,math,code}`, `animation/`, `render/`, `lottie_v2`/`svg_v2`).
- v2 architecture (`domains/architecture/`) is **~40% done**: 6 primitives + `Connection` exist as VMobjects, and `Transfer/Pulse/Highlight/ColorShift/Scale` exist (`animation/recipes.py`), but:
  - **No positioning API** — `Node(label, *, center=...)` only; zero `.right_of()/.at()` in `core/` (`domains/architecture/primitives.py:32`).
  - **No layout pass** — no `domains/architecture/layout/`; `layout/resolver.py` operates on v1 `Node.position`; v2 primitives have no `position`.
  - **Trivial routing** — `domains/architecture/connections.py` is a hardcoded 71-line L-shape; v1 has A\* + Manhattan + waypoints + rounded corners (`layout/router.py`, `layout/astar.py`).
  - **No `Packet`** — `Transfer` (`animation/recipes.py:41`) takes a `packet` arg the caller must supply; no packet shape exists.
  - **v2 depends on v1** — `render/frame.py:45` imports `renderer.canvas`; `core/scene.py` + `render/frame._background` reference `renderer.theme`.
- **Good news (low-risk port):** the v1 router is already pure-`BoundingBox`+`waypoints` (`layout/router.py:25`); the resolver reads only `.id/.label/.position/.source.id/.target.id/.waypoints` (`layout/resolver.py`). So the port is **interface decoupling, not a logic rewrite**.
- `examples/v2_fusion_demo.py` confirms current usage: nodes placed by `center=`, plain `Connection(a,b)`.

## Locked decisions

1. **Positioning = mirror v1's constraint model.** v2 primitives gain a `position: RelativePosition | AbsolutePosition | None` field + fluent `.right_of()/.left_of()/.above()/.below()/.at()` (single-set guard + distance validation, same signatures as `api/primitives.py:124`). A global layout pass resolves pixel centers and applies them via the existing `Graphic.move_to()` (sets `transform`). Rejected alternative (positioning-as-immediate-transform): can't do topological ordering/canvas centering, so it is not parity.
2. **Single shared layout engine, generic via Protocols.** Define `LayoutNode`/`LayoutConnection` Protocols; move `resolver/router/astar` to `domains/architecture/layout/` typed against them (logic unchanged). v1's `layout/resolver.py` becomes a thin re-export so the 460 v1 tests stay green. Avoids duplication/drift, doesn't break v1.
3. **Move shared geometry types to neutral homes** so v2 has zero v1 imports: `BoundingBox`+`estimate_text_bbox` → `core/bbox.py`; `RelativePosition`+`AbsolutePosition` → `domains/architecture/positions.py`. Old locations re-export for v1 back-compat.
4. **De-couple render** by relocating `renderer/canvas.py` → `render/canvas.py` and `renderer/theme.py` → `render/theme.py` (ThemeConfig + THEMES + `get_theme`). v1 `renderer/` re-exports until the cutover phase.
5. **Architecture layout is an explicit, opt-in step** (e.g. `resolve_architecture(scene, ...)`) — do **not** pollute the generic `core.Scene` with v1-specific `add_node/concurrent/theme-by-name`. Scene-authoring-API reconciliation belongs to the cutover phase (out of scope here).

## Ordered task list

### 1. Relocate shared types (keep v1 green via re-exports)
- `layout/bbox.py` → `core/bbox.py` (`BoundingBox`, `estimate_text_bbox`); update `core/graphic.py:20`, `core/vmobject.py:33`, v2 primitives; `layout/bbox.py` becomes `from archmotion.core.bbox import *` re-export.
- `RelativePosition`/`AbsolutePosition` → `domains/architecture/positions.py`; `api/primitives.py:30` re-exports them.
- Run full suite → must stay green.

### 2. Generic layout engine under `domains/architecture/layout/`
- Add `LayoutNode` Protocol (`id: str`, `label: str`, `position`) and `LayoutConnection` Protocol (`id`, `source`/`target` exposing `.id`, `waypoints: list[Point] | None`).
- Move `resolver.py` + `router.py` + `astar.py` here, retyped to Protocols (numeric logic byte-for-byte unchanged). Keep `ResolvedLayout` output (`node_boxes`, `connection_routes`).
- `layout/resolver.py` (v1) → thin re-export of the generic resolver.

### 3. v2 primitives: positioning API
- Add `position` field + `.right_of()/.left_of()/.above()/.below()/.at(anchor=None, x=, y=)` to the architecture primitive base (all 6 inherit). Mirror `api/primitives.py` validation (`MIN/MAX_DISTANCE`, `TopologyError` on double-position).
- Keep size estimation consistent: resolver reads size from label via `estimate_text_bbox` (as v1 does) — verify primitive `width/height` match, or have resolver consult the primitive's own bbox.

### 4. v2 Connection: real routing + corners + arrowhead
- Add `waypoints: list[Point] | None` and `corner_radius` to `Connection`.
- Replace the trivial L-route `generate_points` with a `regenerate_points(route, corner_radius)` that rebuilds the Bezier point array from a resolved polyline (rounded-corner subdivision via `add_arc`/cubic, + arrowhead wings). Source route = `ResolvedLayout.connection_routes[conn.id]`.

### 5. Packet + Transfer wiring
- Add `Packet` VMobject (`domains/architecture/`, small rounded-rect/circle).
- Verify/fix the PATH_PROGRESS→position path in `render/path_render.resolve_effective` so the packet is placed via `connection.point_at_progress(progress)`; `Transfer` auto-creates a `Packet` when none supplied and binds it to the connection's route.

### 6. Architecture layout entry point
- `resolve_architecture(scene, canvas_width, canvas_height)`: gather architecture nodes/connections from the scene, run the resolver, apply `node.move_to(cx, cy)`, regenerate each connection's points from its route, register packets.
- Call site: explicit `scene.layout()`/`resolve_architecture(...)` before `render`/`to_lottie`/`to_svg` (mirrors v1 Phase 2). Builder/cutover can call it automatically later.

### 7. Kill v2→v1 render coupling
- `renderer/canvas.py` → `render/canvas.py`; `renderer/theme.py` → `render/theme.py`; update `render/frame.py`, `core/scene.py`. v1 `renderer/*` re-exports.
- Grep-guard: `rg "from archmotion\.(api|renderer|motions)\b" src/archmotion/{core,domains,animation,render}` must return **zero** hits after this phase.

### 8. Parity tests (`tests/unit/domains/architecture/`)
- **Coordinate parity (exact):** same topology → v2 `resolve_architecture` node_boxes == v1 `resolve_layout` node_boxes. Cover relative chains, absolute, mixed, multi-root, orphan/cycle/overflow errors, A\* obstacle routing, waypoints.
- **Routing parity:** v2 connection polylines match v1 routes (after corner subdivision tolerance).
- **Golden frames:** render a representative scene (FadeIn + Transfer + Pulse) via v2 to PNG/MP4; pixel-diff vs v1 render within tolerance.
- **Transfer/Packet:** assert packet x/y traverse the routed polyline at 0/0.5/1.0 progress.
- `mypy --strict` + `ruff check` clean on changed v2 modules.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Relocating `BoundingBox`/positions breaks v1 imports | Old paths are pure re-exports; full v1 suite must stay green (gate each task). |
| Resolver genericization changes numeric output | Coordinate-parity tests assert byte-exact boxes vs v1 before/after. |
| Packet PATH_PROGRESS not wired in path_render | Task 5 verifies `resolve_effective`; add unit test before golden frames. |
| Polluting generic `core.Scene` | Layout is an explicit opt-in step; Scene stays domain-agnostic. |
| Corner subdivision changes connection point count (affects Transform) | Document; `align_with` already handles count-matching for morphs. |

## Validation plan

- `pytest tests/` 100% green (v1 untouched via re-exports).
- New `tests/unit/domains/architecture/` parity suite passes.
- `rg "from archmotion\.(api|renderer|motions)\b" src/archmotion/{core,domains,animation,render}` → 0 hits.
- `mypy --strict src/archmotion && ruff check` clean.
- `examples/v2_fusion_demo.py` + a new relative-positioned architecture example render MP4 + Lottie + SVG.

## Out of scope (follow-on cutover phase)

- Removing v1 `api/`/`renderer/`/`motions/`/`layout/` stacks.
- Re-pointing `__init__.py`, CLI (`__main__.py`), `ai/builder.py` to v2.
- v2 `core.Scene` authoring API reconciliation (`add_node`/`concurrent`/theme-by-name/`export`/`resolve`).
- Studio Pyodide bridge rebuild; docs/CHANGELOG update.

## Open questions

None blocking — scope (Phase 2 parity only) and positioning model (mirror v1) are confirmed.
