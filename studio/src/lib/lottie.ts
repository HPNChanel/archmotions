// lottie-web helpers shared by the preview panel and the MP4 encoder.

import lottie, { type AnimationItem } from "lottie-web";
import type { LottieAnimation } from "../types";

/** Load a Lottie animation into a container with sensible defaults. */
export function loadLottie(
  container: HTMLElement,
  data: LottieAnimation,
  opts: { loop?: boolean; autoplay?: boolean } = {},
): AnimationItem {
  return lottie.loadAnimation({
    container,
    renderer: "svg",
    loop: opts.loop ?? true,
    autoplay: opts.autoplay ?? true,
    animationData: data,
  });
}

/**
 * Render a Lottie animation frame-by-frame to PNG blobs (used for MP4 export).
 *
 * Uses lottie-web's canvas renderer on an offscreen element. Yields each frame
 * as a PNG Blob in order. The caller is responsible for disposing the canvas.
 */
export async function* renderLottieFrames(
  data: LottieAnimation,
  totalFrames: number,
  onProgress?: (frame: number, total: number) => void,
): AsyncGenerator<{ index: number; png: Blob }> {
  const width = (data.w as number) || 1920;
  const height = (data.h as number) || 1080;

  // Offscreen host element for lottie-web's canvas renderer.
  const host = document.createElement("div");
  host.style.width = `${width}px`;
  host.style.height = `${height}px`;
  host.style.position = "fixed";
  host.style.left = "-99999px";
  document.body.appendChild(host);

  let anim: AnimationItem | undefined;
  try {
    anim = lottie.loadAnimation({
      container: host,
      renderer: "canvas",
      loop: false,
      autoplay: false,
      animationData: data,
    });

    // Give the renderer a tick to initialize the canvas.
    await new Promise((r) => setTimeout(r, 30));

    const canvas = host.querySelector("canvas");
    if (!canvas) throw new Error("lottie-web did not create a canvas for rendering");
    canvas.width = width;
    canvas.height = height;

    for (let i = 0; i < totalFrames; i++) {
      anim.goToAndStop(i, true);
      onProgress?.(i + 1, totalFrames);
      const png = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/png");
      });
      yield { index: i, png };
    }
  } finally {
    anim?.destroy();
    document.body.removeChild(host);
  }
}

export function totalLottieFrames(data: LottieAnimation): number {
  const op = data.op as number | undefined;
  const ip = data.ip as number | undefined;
  if (typeof op === "number" && typeof ip === "number") return Math.max(1, Math.round(op - ip));
  return Math.round(((data.op as number) ?? 0));
}
