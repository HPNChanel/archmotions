// In-browser MP4 encoding via @ffmpeg/ffmpeg (ffmpeg.wasm).
//
// Multi-threaded core is used when the page is cross-origin isolated
// (Cross-Origin-Opener-Policy + Cross-Origin-Embedder-Policy headers, set in
// firebase.json / vite.config). Otherwise we fall back to the single-threaded
// core so the feature still works (just slower) — e.g. on GitHub Pages or when
// isolation is unavailable.

import { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile, toBlobURL } from "@ffmpeg/util";
import type { LottieAnimation } from "../types";
import { renderLottieFrames } from "./lottie";

const CORE_VERSION = "0.12.10";
const MT_BASE = `https://unpkg.com/@ffmpeg/core-mt@${CORE_VERSION}/dist/umd`;
const ST_BASE = `https://unpkg.com/@ffmpeg/core@${CORE_VERSION}/dist/umd`;

let ffmpegInstance: FFmpeg | null = null;
let loadPromise: Promise<FFmpeg> | null = null;

/** Whether SharedArrayBuffer (MT core) is available in this context. */
export function isCrossOriginIsolated(): boolean {
  return typeof window !== "undefined" && (window as Window).crossOriginIsolated === true;
}

async function loadFFmpeg(onLog?: (msg: string) => void): Promise<FFmpeg> {
  if (ffmpegInstance) return ffmpegInstance;
  if (loadPromise) return loadPromise;

  loadPromise = (async () => {
    const ff = new FFmpeg();
    if (onLog) ff.on("log", ({ message }) => onLog(message));

    const mt = isCrossOriginIsolated();
    const base = mt ? MT_BASE : ST_BASE;
    // toBlobURL fetches cross-origin resources and re-serves them as same-origin
    // blob URLs, satisfying COEP `require-corp` (the CDNs send ACAO:*).
    const coreURL = await toBlobURL(`${base}/ffmpeg-core.js`, "text/javascript");
    const wasmURL = await toBlobURL(`${base}/ffmpeg-core.wasm`, "application/wasm");
    await ff.load(
      mt
        ? { coreURL, wasmURL }
        : { coreURL, wasmURL },
    );
    ffmpegInstance = ff;
    return ff;
  })().catch((err) => {
    loadPromise = null;
    throw err;
  });

  return loadPromise;
}

export interface EncodeOptions {
  fps: number;
  onProgress?: (stage: string, fraction: number) => void;
  onLog?: (msg: string) => void;
  signal?: AbortSignal;
}

/**
 * Encode a Lottie animation to an MP4 (H.264) entirely in the browser.
 *
 * Renders each frame via lottie-web's canvas renderer, writes PNGs to the
 * ffmpeg.wasm MEMFS, then encodes with libx264. Returns the MP4 bytes.
 */
export async function encodeLottieToMp4(
  lottie: LottieAnimation,
  totalFrames: number,
  opts: EncodeOptions,
): Promise<Uint8Array> {
  const { fps, onProgress, onLog, signal } = opts;

  onProgress?.("Loading ffmpeg.wasm…", 0);
  const ff = await loadFFmpeg(onLog);

  // Clean any frames / output from a previous encode (MEMFS persists on the
  // singleton instance). Best-effort: stop at the first missing frame.
  for (let i = 0; i <= totalFrames + 1; i++) {
    const name = frameName(i);
    try {
      await ff.deleteFile(name);
    } catch {
      break;
    }
  }
  try {
    await ff.deleteFile("out.mp4");
  } catch {
    // No prior output — fine.
  }

  // Phase 1: render + write frames.
  const frameGen = renderLottieFrames(lottie, totalFrames, (f, total) => {
    onProgress?.(`Rendering frame ${f}/${total}`, f / (total * 2));
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  });

  for await (const { index, png } of frameGen) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    await ff.writeFile(frameName(index), await fetchFile(png));
  }

  // Phase 2: encode.
  onProgress?.("Encoding MP4 (libx264)…", 0.6);
  const inputArgs = ["-y", "-framerate", String(fps), "-i", "f_%05d.png"];
  const encodeArgs = [
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-preset",
    "veryfast",
    "-crf",
    "23",
    "out.mp4",
  ];

  ff.on("progress", ({ progress }) => {
    onProgress?.("Encoding MP4 (libx264)…", 0.6 + Math.min(0.39, progress * 0.39));
  });

  await ff.exec([...inputArgs, ...encodeArgs]);

  const data = await ff.readFile("out.mp4");
  onProgress?.("Done", 1);
  return data as Uint8Array;
}

function frameName(index: number): string {
  return `f_${String(index).padStart(5, "0")}.png`;
}
