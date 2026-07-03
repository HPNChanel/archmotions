import { useState } from "react";
import { useStudioStore } from "../../store/useStudioStore";
import { renderHtml } from "../../lib/pyodide";
import { encodeLottieToMp4 } from "../../lib/ffmpeg";
import { totalLottieFrames } from "../../lib/lottie";
import { downloadBytes, downloadJson, downloadText } from "../../lib/download";

const stamp = () => new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");

export default function ExportPanel() {
  const result = useStudioStore((s) => s.result);
  const yaml = useStudioStore((s) => s.yaml);
  const setExportProgress = useStudioStore((s) => s.setExportProgress);
  const exportProgress = useStudioStore((s) => s.exportProgress);
  const [err, setErr] = useState<string | null>(null);

  const ok = result?.ok === true;
  const lottie = ok ? result.lottie : null;
  const svg = ok ? result.svg : null;
  const fps = ok ? result.fps : 60;
  const hasAnim = !!lottie;

  const guard = (fn: () => void | Promise<void>) => async () => {
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const doLottie = guard(() => {
    if (lottie) downloadJson(lottie, `archmotion-${stamp()}.json`);
  });

  const doSvg = guard(() => {
    if (svg) downloadText(svg, `archmotion-${stamp()}.svg`, "image/svg+xml");
  });

  const doHtml = guard(async () => {
    const html = await renderHtml(yaml);
    downloadText(html, `archmotion-${stamp()}.html`, "text/html");
  });

  const doMp4 = guard(async () => {
    if (!lottie) return;
    const total = totalLottieFrames(lottie);
    setExportProgress({ active: true, stage: "Starting…", fraction: 0 });
    const bytes = await encodeLottieToMp4(lottie, total, {
      fps,
      onProgress: (stage, fraction) => setExportProgress({ active: true, stage, fraction }),
    });
    setExportProgress(null);
    downloadBytes(bytes, `archmotion-${stamp()}.mp4`, "video/mp4");
  });

  const busy = !!exportProgress?.active;

  return (
    <div className="section">
      <div className="panel-header" style={{ padding: 0, border: "none", marginBottom: 10 }}>
        Export
      </div>

      {!hasAnim && (
        <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 8 }}>
          Add a <code>choreography</code> step to enable Lottie / SVG / MP4
          export (layout-only scenes export HTML).
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <button className="btn" onClick={doLottie} disabled={!hasAnim || busy}>
          Lottie JSON
        </button>
        <button className="btn" onClick={doSvg} disabled={!hasAnim || busy}>
          Animated SVG
        </button>
        <button className="btn" onClick={doHtml} disabled={busy || !yaml.trim()}>
          HTML Player
        </button>
        <button className="btn primary" onClick={doMp4} disabled={!hasAnim || busy}>
          MP4 Video
        </button>
      </div>

      {busy && exportProgress && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 12, marginBottom: 4 }}>{exportProgress.stage}</div>
          <div className="bar" style={{ width: "100%", height: 6, background: "var(--panel-2)" }}>
            <div style={{ width: `${Math.round(exportProgress.fraction * 100)}%`, height: "100%", background: "var(--accent)" }} />
          </div>
        </div>
      )}

      {err && (
        <div style={{ marginTop: 10, fontSize: 12, color: "var(--danger)" }}>{err}</div>
      )}
    </div>
  );
}
