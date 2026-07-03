import { useStudioStore } from "../../store/useStudioStore";
import { TEMPLATES } from "../../templates";

export default function TemplateGallery() {
  const setYaml = useStudioStore((s) => s.setYaml);
  const setSelectedNode = useStudioStore((s) => s.setSelectedNode);

  const load = (yaml: string) => {
    setYaml(yaml);
    setSelectedNode(null);
  };

  return (
    <div className="section">
      <div className="panel-header" style={{ padding: 0, border: "none", marginBottom: 10 }}>
        Templates
      </div>
      <div className="template-list" style={{ padding: 0 }}>
        {TEMPLATES.map((t) => (
          <button key={t.id} className="template-item" onClick={() => load(t.yaml)}>
            <div className="t-name">{t.name}</div>
            <div className="t-desc">{t.description}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
