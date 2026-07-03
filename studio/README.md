# ArchMotion Studio

A zero-cost, fully client-side web editor for composing system-architecture
animations and exporting **MP4 / Lottie / SVG / HTML** — no server compute.

The real `archmotion` Python package runs in the browser via **Pyodide**
(Python-on-WebAssembly). MP4 is encoded in-browser via **ffmpeg.wasm**
(multi-threaded when the page is cross-origin isolated). Scenes are saved in
`localStorage`. Hosted free on **Firebase Hosting**.

> The Python engine changes that power the Studio (absolute positioning +
> in-memory export) live in the repo root `src/archmotion/`.

## Architecture

```
YAML editor ─┐
             ├─► Pyodide (real archmotion) ─► resolved layout + Lottie/SVG
Canvas  ─────┘            │                          │
   (drag → patch YAML)    │                          ▼
                         layout ─► React Flow canvas   Lottie preview
                                                            │
                                          MP4 ◄── ffmpeg.wasm ◄── lottie-web frames
```

- **YAML is the single source of truth.** Canvas edits surgically patch the YAML,
  which triggers a debounced recompile. On a parse error the canvas keeps the
  last valid state and shows the error banner.
- **Node sizes come from the engine** (`Scene.to_layout_dict()`), so the canvas
  always matches the exported video/Lottie exactly.
- **Absolute positioning** is additive & backward-compatible: a node may be
  positioned either relatively (`anchor/direction/distance`) or absolutely
  (`x/y` pixels). When any node is absolute, auto-centering is skipped.

## Local development

### 1. Build the Python wheel (Pyodide payload)

The Studio loads `archmotion` as a pure-Python wheel served as a static asset.
Build it once from the **repo root**:

```bash
python -m pip install build hatchling
python -m build --wheel --no-isolation --outdir studio/public/wheels
```

This produces `studio/public/wheels/archmotion-<ver>-py3-none-any.whl`. The wheel
is gitignored (it's a build artifact) and rebuilt by CI on deploy.

> Only the export path (YAML → layout → timeline → Lottie/SVG/HTML) is used in
> the browser — it's pure Python and needs no `skia`/`Pillow`/`ffmpeg`. Pyodide
> loads `pydantic` + `pyyaml` only.

### 2. Install & run the frontend

```bash
cd studio
npm install
npm run dev
```

The Vite dev server sets `COOP`/`COEP` headers locally so multi-threaded
ffmpeg.wasm (SharedArrayBuffer) works for MP4 testing.

Open the printed URL. The first load fetches the Pyodide runtime (~15 MB,
cached afterwards) and the archmotion wheel.

## Deploy

`firebase.json` configures Firebase Hosting with `Cross-Origin-Opener-Policy:
same-origin` + `Cross-Origin-Embedder-Policy: require-corp` on all routes,
which enables the multi-threaded ffmpeg.wasm core.

The `.github/workflows/studio-deploy.yml` workflow builds the wheel + frontend
and deploys on push to `main`. Set these to enable deploy:

- `FIREBASE_SERVICE_ACCOUNT` (secret) — service account JSON (Firebase console →
  Project settings → Service accounts → Generate new private key)
- `FIREBASE_PROJECT_ID` (repo variable) — your Firebase project id

Manual deploy:

```bash
cd studio
npm run build
npx firebase deploy --only hosting
```

## Notes & trade-offs

- **First-load cost:** Pyodide is ~15 MB on first visit, then browser-cached. A
  loading screen reports progress.
- **ffmpeg.wasm isolation:** the Studio auto-selects the multi-threaded core
  when `self.crossOriginIsolated` is true (Firebase Hosting) and falls back to
  the single-threaded core otherwise (slower MP4, but still works).
- **COEP + CDN resources:** Pyodide is loaded from the jsDelivr CDN and ffmpeg
  core via `toBlobURL` (same-origin blob), both compatible with
  `require-corp`. If you self-host Pyodide instead, mirror the whole `full/`
  directory and set `PYODIDE_INDEX` in `src/lib/pyodide.ts`.
