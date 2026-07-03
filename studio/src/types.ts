// Shared types for ArchMotion Studio.

/** Primitive types rendered by the canvas (mirrors archmotion PrimitiveType). */
export type PrimitiveType =
  | "node"
  | "database"
  | "cloud"
  | "queue"
  | "cache"
  | "user";

/** Resolved layout + metadata for one node (from archmotion Scene.to_layout_dict). */
export interface LayoutNode {
  label: string;
  type: PrimitiveType;
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Resolved routed polyline for one connection. */
export interface LayoutConnection {
  source: string;
  target: string;
  label: string | null;
  route: [number, number][];
}

/** Output of archmotion Scene.to_layout_dict(). */
export interface LayoutData {
  canvas: [number, number];
  nodes: Record<string, LayoutNode>;
  connections: Record<string, LayoutConnection>;
}

/** Result of compiling a YAML scene through Pyodide. */
export interface CompileSuccess {
  ok: true;
  layout: LayoutData;
  lottie: LottieAnimation | null;
  svg: string | null;
  fps: number;
  duration: number;
}

export interface CompileFailure {
  ok: false;
  error: string;
  type: string;
}

export type CompileResult = CompileSuccess | CompileFailure;

/** Minimal Lottie shape — we treat it as opaque JSON handed to lottie-web. */
export type LottieAnimation = Record<string, unknown>;

/** A persisted scene in localStorage. */
export interface SavedScene {
  id: string;
  name: string;
  yaml: string;
  updatedAt: number;
}

/** Theme descriptor (mirrors archmotion ThemeConfig for the UI). */
export interface ThemeOption {
  id: string;
  label: string;
  /** CSS background for the preview swatch + canvas. */
  bg: string;
  /** CSS accent (border) color. */
  accent: string;
  /** CSS text color. */
  text: string;
}

export type ExportFormat = "mp4" | "lottie" | "svg" | "html";
