import { useStudioStore } from "../../store/useStudioStore";
import { setTheme as yamlSetTheme } from "../../lib/yamlOps";
import { THEMES } from "../../lib/themes";

export default function ThemePicker() {
  const themeId = useStudioStore((s) => s.themeId);
  const yaml = useStudioStore((s) => s.yaml);
  const setTheme = useStudioStore((s) => s.setTheme);
  const patchYaml = useStudioStore((s) => s.patchYaml);

  const apply = (id: string) => {
    setTheme(id);
    if (yaml) patchYaml(yamlSetTheme(yaml, id));
  };

  return (
    <div className="section">
      <div className="panel-header" style={{ padding: 0, border: "none", marginBottom: 10 }}>
        Theme
      </div>
      <div className="theme-grid">
        {THEMES.map((t) => (
          <button
            key={t.id}
            className={"theme-card" + (t.id === themeId ? " active" : "")}
            style={{ background: t.bg }}
            onClick={() => apply(t.id)}
          >
            <div
              className="swatch"
              style={{ background: t.nodeFill, border: `2px solid ${t.nodeBorder}`, color: t.text }}
            >
              {t.label}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
