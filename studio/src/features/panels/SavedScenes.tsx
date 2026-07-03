import { useState } from "react";
import { useStudioStore } from "../../store/useStudioStore";

export default function SavedScenes() {
  const savedScenes = useStudioStore((s) => s.savedScenes);
  const saveCurrent = useStudioStore((s) => s.saveCurrent);
  const loadScene = useStudioStore((s) => s.loadScene);
  const removeScene = useStudioStore((s) => s.removeScene);
  const [name, setName] = useState("");

  const onSave = () => {
    const n = name.trim() || `Scene ${new Date().toLocaleString()}`;
    saveCurrent(n);
    setName("");
  };

  return (
    <div className="section">
      <div className="panel-header" style={{ padding: 0, border: "none", marginBottom: 10 }}>
        Saved Scenes
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        <input
          className="input"
          placeholder="Scene name…"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSave()}
        />
        <button className="btn" onClick={onSave}>
          Save
        </button>
      </div>
      {savedScenes.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
          No saved scenes yet. Scenes are stored locally in your browser.
        </div>
      ) : (
        savedScenes.map((s) => (
          <div className="saved-item" key={s.id}>
            <span className="name" onClick={() => loadScene(s)} title={s.yaml.slice(0, 80)}>
              {s.name}
            </span>
            <button className="btn" onClick={() => removeScene(s.id)} title="Delete">
              ✕
            </button>
          </div>
        ))
      )}
    </div>
  );
}
