import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: "./",
  // COOP/COEP headers are set at the hosting layer (firebase.json) so the
  // multi-threaded ffmpeg.wasm core (SharedArrayBuffer) is available. Vite dev
  // server also needs them — handled by `vite-plugin-cross-origin-isolation`
  // would be ideal, but we configure headers via a small middleware here so
  // `npm run dev` also gets cross-origin isolation for local MP4 testing.
  server: {
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
  },
  preview: {
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
  },
  build: {
    target: "es2022",
    sourcemap: true,
    // ffmpeg.wasm + pyodide make the bundle large; raise the warning limit.
    chunkSizeWarningLimit: 4000,
  },
});
