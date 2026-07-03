import { useEffect } from "react";
import "@xyflow/react/dist/style.css";
import { useStudioStore } from "./store/useStudioStore";
import { DEFAULT_TEMPLATE } from "./templates";
import YamlEditor from "./features/yaml/YamlEditor";
import SceneCanvas from "./features/editor/SceneCanvas";
import LottiePreview from "./features/preview/LottiePreview";
import ThemePicker from "./features/panels/ThemePicker";
import TemplateGallery from "./features/panels/TemplateGallery";
import Inspector from "./features/panels/Inspector";
import ExportPanel from "./features/panels/ExportPanel";
import SavedScenes from "./features/panels/SavedScenes";

export default function App() {
  const yaml = useStudioStore((s) => s.yaml);
  const status = useStudioStore((s) => s.status);
  const initFraction = useStudioStore((s) => s.initFraction);
  const initMessage = useStudioStore((s) => s.initMessage);
  const errorMsg = useStudioStore((s) => s.errorMsg);
  const result = useStudioStore((s) => s.result);
  const themeId = useStudioStore((s) => s.themeId);
  const setYaml = useStudioStore((s) => s.setYaml);
  const setTheme = useStudioStore((s) => s.setTheme);
  const previewTab = useStudioStore((s) => s.previewTab);
  const setPreviewTab = useStudioStore((s) => s.setPreviewTab);
  const initEngine = useStudioStore((s) => s.initEngine);

  // Seed the default template + launch the engine on first mount.
  useEffect(() => {
    if (!yaml) setYaml(DEFAULT_TEMPLATE.yaml);
    // Derive initial theme from the template.
    setTheme(DEFAULT_TEMPLATE.yaml.match(/^theme:\s*(\S+)/m)?.[1] ?? "dark_terminal");
    void initEngine();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loading = status === "loading";
  const lottie = result?.ok ? result.lottie : null;

  return (
    <div className="app">
      <div className="topbar">
        <span className="brand">🎬 ArchMotion Studio</span>
        <span
          className={"status-pill " + (status === "ready" ? "ready" : status === "error" ? "error" : "")}
        >
          {status === "ready" ? "● Engine ready" : status === "loading" ? "Loading…" : status === "error" ? "Engine error" : "Idle"}
        </span>
        <span className="spacer" />
        <a
          href="https://github.com/archmotion/archmotion"
          target="_blank"
          rel="noreferrer"
          style={{ fontSize: 12, color: "var(--text-dim)" }}
        >
          Docs ↗
        </a>
      </div>

      <div className="workspace">
        {/* Left: YAML editor */}
        <div className="panel">
          <div className="panel-header">Scene YAML</div>
          <div className="panel-body">
            <YamlEditor />
          </div>
        </div>

        {/* Center: Canvas / Preview tabs */}
        <div className="center">
          <div className="tabs">
            <button
              className={"tab" + (previewTab === "canvas" ? " active" : "")}
              onClick={() => setPreviewTab("canvas")}
            >
              Canvas
            </button>
            <button
              className={"tab" + (previewTab === "preview" ? " active" : "")}
              onClick={() => setPreviewTab("preview")}
            >
              Preview {lottie ? "" : "(no anim)"}
            </button>
          </div>
          <div style={{ position: "relative", minHeight: 0, flex: 1 }}>
            {previewTab === "canvas" ? <SceneCanvas /> : (
              <LottiePreview data={lottie} bg={themeBg(themeId)} />
            )}

            {errorMsg && (
              <div className="error-banner">{errorMsg}</div>
            )}

            {loading && (
              <div className="loading-overlay">
                <div style={{ fontWeight: 600 }}>Starting the ArchMotion engine…</div>
                <div className="bar">
                  <div style={{ width: `${Math.round(initFraction * 100)}%` }} />
                </div>
                <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{initMessage}</div>
                <div style={{ fontSize: 11, color: "var(--text-dim)", maxWidth: 420, textAlign: "center" }}>
                  The real Python engine (~15&nbsp;MB) is loading once via Pyodide and will be
                  cached by your browser.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: panels */}
        <div className="panel right">
          <div className="panel-body">
            <ThemePicker />
            <Inspector />
            <ExportPanel />
            <TemplateGallery />
            <SavedScenes />
          </div>
        </div>
      </div>
    </div>
  );
}

function themeBg(themeId: string): string {
  // Minimal inline lookup to avoid a circular import in styles.
  const map: Record<string, string> = {
    dark_terminal: "#12121c",
    neon_cyber: "#08050f",
    blueprint: "#0d244d",
    light_paper: "#fafaf5",
  };
  return map[themeId] ?? "#12121c";
}
