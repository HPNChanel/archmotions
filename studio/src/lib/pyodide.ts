// Pyodide bridge — runs the real archmotion Python package in the browser (WASM).
//
// Lazy-initialized singleton. Loads Pyodide core + pydantic/pyyaml + the
// archmotion wheel (a pure-Python wheel served as a static asset). Exposes a
// single `compileScene(yaml)` entry point that returns resolved layout +
// Lottie/SVG in JSON form.

import { loadPyodide, type PyodideInterface } from "pyodide";
import type { CompileResult } from "../types";

const PYODIDE_VERSION = "0.26.4";
const PYODIDE_INDEX = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

// The wheel is built from the repo root (python -m build --wheel) and copied to
// studio/public/wheels so it ships as a static asset (no external CDN dep).
const WHEEL_URL = "./wheels/archmotion-1.0.0-py3-none-any.whl";

let pyodidePromise: Promise<PyodideInterface> | null = null;

export type InitProgress = (fraction: number, message: string) => void;

/** Lazily load + configure the Pyodide runtime (singleton). */
export function initPyodide(onProgress?: InitProgress): Promise<PyodideInterface> {
  if (pyodidePromise) return pyodidePromise;

  pyodidePromise = (async () => {
    onProgress?.(0.1, "Loading Pyodide runtime…");
    const py = await loadPyodide({ indexURL: PYODIDE_INDEX });

    onProgress?.(0.45, "Loading Python packages (pydantic, pyyaml)…");
    await py.loadPackage(["micropip", "pydantic", "pyyaml"]);

    onProgress?.(0.75, "Installing the ArchMotion engine…");
    const micropip = py.pyimport("micropip");
    // pydantic + pyyaml are already loaded above, so we can skip dependency
    // resolution (which would otherwise try to fetch the heavy skia/Pillow deps
    // that archmotion only needs for server-side MP4 rendering).
    await micropip.install(WHEEL_URL);

    onProgress?.(0.95, "Defining the compiler bridge…");
    py.runPython(BRIDGE_PY);

    onProgress?.(1.0, "Ready");
    return py;
  })().catch((err) => {
    // Allow a retry on failure.
    pyodidePromise = null;
    throw err;
  });

  return pyodidePromise;
}

// Python bridge: parses YAML, resolves layout, and returns a JSON string with
// layout + (optionally) lottie/svg. Animations are optional — layout works even
// with an empty/invalid choreography so the canvas stays live while editing.
const BRIDGE_PY = `
import json
from archmotion.api.scene import Scene
from archmotion.ai import parse_yaml_string, YAMLParseError
from archmotion.errors import ArchMotionError

def _compile(yaml_src):
    try:
        scene = parse_yaml_string(yaml_src)
    except YAMLParseError as e:
        return {"ok": False, "error": str(e), "type": "YAMLParseError"}
    except ArchMotionError as e:
        return {"ok": False, "error": str(e), "type": type(e).__name__}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "type": type(e).__name__}

    out = {"ok": True, "layout": scene.to_layout_dict(), "fps": scene.fps, "duration": scene.total_duration}
    try:
        out["lottie"] = scene.to_lottie()
        out["svg"] = scene.to_svg()
    except ArchMotionError:
        # No animations recorded yet — preview disabled, layout still live.
        out["lottie"] = None
        out["svg"] = None
    return out

def _render_json(yaml_src):
    return json.dumps(_compile(yaml_src))
`;

/**
 * Compile a YAML scene through the real archmotion engine in Pyodide.
 *
 * Returns resolved layout (always, even without animations) plus Lottie/SVG
 * (only when animations are present). Never throws — failures are reported as
 * a `CompileFailure` so the UI can show inline errors.
 */
export async function compileScene(yaml: string): Promise<CompileResult> {
  const py = await initPyodide();
  py.globals.set("__am_yaml_src", yaml);
  // _render_json returns a JSON string we can parse directly (avoids the
  // Pyodide Map-vs-Object conversion quirks for nested dicts).
  const jsonStr = py.runPython("_render_json(__am_yaml_src)") as string;
  return JSON.parse(jsonStr) as CompileResult;
}

/** Build the self-contained HTML player string via Pyodide (for HTML export). */
export async function renderHtml(yaml: string, title = "ArchMotion Animation"): Promise<string> {
  const py = await initPyodide();
  py.globals.set("__am_yaml_src", yaml);
  py.globals.set("__am_title", title);
  py.runPython(
    "from archmotion.ai import parse_yaml_string\n" +
      "def _to_html(s, t):\n" +
      "    try:\n" +
      "        return parse_yaml_string(s).to_html(title=t)\n" +
      "    except Exception as e:\n" +
      "        return None\n",
  );
  const html = py.runPython("_to_html(__am_yaml_src, __am_title)");
  if (html === null || html === undefined) {
    throw new Error("Failed to render HTML — check the scene YAML.");
  }
  return html as string;
}
