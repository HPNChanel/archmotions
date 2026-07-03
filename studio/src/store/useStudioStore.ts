// Central app state (Zustand). YAML is the single source of truth; the compile
// result (layout + lottie) is derived from it via Pyodide. Canvas edits patch
// the YAML, which triggers a recompile.

import { create } from "zustand";
import type { CompileResult, SavedScene } from "../types";
import { compileScene, initPyodide, type InitProgress } from "../lib/pyodide";
import {
  loadScenes,
  upsertScene,
  deleteScene as deleteStored,
  newId,
} from "../lib/storage";

export type { SavedScene } from "../types";

export type EngineStatus = "idle" | "loading" | "ready" | "error";

interface StudioState {
  yaml: string;
  result: CompileResult | null;
  compiling: boolean;
  status: EngineStatus;
  initFraction: number;
  initMessage: string;
  errorMsg: string | null;
  themeId: string;
  selectedNodeId: string | null;
  previewTab: "canvas" | "preview";
  savedScenes: SavedScene[];
  exportProgress: { active: boolean; stage: string; fraction: number } | null;

  // actions
  setYaml: (yaml: string) => void;
  patchYaml: (nextYaml: string) => void;
  initEngine: () => Promise<void>;
  compile: () => Promise<void>;
  setTheme: (themeId: string) => void;
  setSelectedNode: (id: string | null) => void;
  setPreviewTab: (tab: "canvas" | "preview") => void;
  saveCurrent: (name: string) => SavedScene;
  loadScene: (scene: SavedScene) => void;
  removeScene: (id: string) => void;
  setExportProgress: (p: { active: boolean; stage: string; fraction: number } | null) => void;
}

let compileTimer: ReturnType<typeof setTimeout> | null = null;

export const useStudioStore = create<StudioState>((set, get) => ({
  yaml: "",
  result: null,
  compiling: false,
  status: "idle",
  initFraction: 0,
  initMessage: "",
  errorMsg: null,
  themeId: "dark_terminal",
  selectedNodeId: null,
  previewTab: "canvas",
  savedScenes: loadScenes(),
  exportProgress: null,

  setYaml: (yaml) => {
    set({ yaml });
    scheduleCompile(get);
  },

  // Internal: replace YAML without re-scheduling (used after a canvas patch
  // already produced a final value that should be compiled once).
  patchYaml: (nextYaml) => {
    set({ yaml: nextYaml });
    scheduleCompile(get);
  },

  initEngine: async () => {
    if (get().status === "loading" || get().status === "ready") return;
    set({ status: "loading", errorMsg: null });
    const onProgress: InitProgress = (fraction, message) =>
      set({ initFraction: fraction, initMessage: message });
    try {
      await initPyodide(onProgress);
      set({ status: "ready" });
      await get().compile();
    } catch (err) {
      set({
        status: "error",
        errorMsg: err instanceof Error ? err.message : String(err),
      });
    }
  },

  compile: async () => {
    if (get().status !== "ready") return;
    const yaml = get().yaml;
    if (!yaml.trim()) {
      set({ result: null });
      return;
    }
    set({ compiling: true });
    try {
      const result = await compileScene(yaml);
      set({ result, errorMsg: result.ok ? null : result.error });
    } catch (err) {
      set({
        errorMsg: err instanceof Error ? err.message : String(err),
      });
    } finally {
      set({ compiling: false });
    }
  },

  setTheme: (themeId) => set({ themeId }),

  setSelectedNode: (id) => set({ selectedNodeId: id }),

  setPreviewTab: (tab) => set({ previewTab: tab }),

  saveCurrent: (name) => {
    const scene: SavedScene = {
      id: newId(),
      name,
      yaml: get().yaml,
      updatedAt: Date.now(),
    };
    const scenes = upsertScene(scene);
    set({ savedScenes: scenes });
    return scene;
  },

  loadScene: (scene) => {
    set({ yaml: scene.yaml, selectedNodeId: null });
    scheduleCompile(get);
  },

  removeScene: (id) => {
    const scenes = deleteStored(id);
    set({ savedScenes: scenes });
  },

  setExportProgress: (p) => set({ exportProgress: p }),
}));

function scheduleCompile(get: () => StudioState) {
  if (compileTimer) clearTimeout(compileTimer);
  compileTimer = setTimeout(() => {
    void get().compile();
  }, 250);
}
