// localStorage persistence for saved scenes (zero-backend).

import type { SavedScene } from "../types";

const STORAGE_KEY = "archmotion.studio.scenes.v1";

export function loadScenes(): SavedScene[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedScene[];
    return Array.isArray(parsed) ? parsed.sort((a, b) => b.updatedAt - a.updatedAt) : [];
  } catch {
    return [];
  }
}

export function saveScenes(scenes: SavedScene[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(scenes));
  } catch {
    // Quota exceeded or disabled — fail silently (no backend to fall back to).
  }
}

export function upsertScene(scene: SavedScene): SavedScene[] {
  const scenes = loadScenes();
  const idx = scenes.findIndex((s) => s.id === scene.id);
  if (idx >= 0) {
    scenes[idx] = scene;
  } else {
    scenes.unshift(scene);
  }
  const sorted = scenes.sort((a, b) => b.updatedAt - a.updatedAt);
  saveScenes(sorted);
  return sorted;
}

export function deleteScene(id: string): SavedScene[] {
  const scenes = loadScenes().filter((s) => s.id !== id);
  saveScenes(scenes);
  return scenes;
}

export function newId(): string {
  return `scene_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}
