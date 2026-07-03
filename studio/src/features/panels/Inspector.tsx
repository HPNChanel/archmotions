import { useStudioStore } from "../../store/useStudioStore";
import {
  addNode,
  removeNode,
  updateNode,
} from "../../lib/yamlOps";
import type { PrimitiveType } from "../../types";

const PRIM_TYPES: PrimitiveType[] = ["node", "database", "cloud", "queue", "cache", "user"];

export default function Inspector() {
  const result = useStudioStore((s) => s.result);
  const yaml = useStudioStore((s) => s.yaml);
  const selectedNodeId = useStudioStore((s) => s.selectedNodeId);
  const patchYaml = useStudioStore((s) => s.patchYaml);
  const setSelectedNode = useStudioStore((s) => s.setSelectedNode);

  const layout = result?.ok ? result.layout : null;
  const selected = selectedNodeId && layout ? layout.nodes[selectedNodeId] : null;

  const onAdd = () => {
    const id = `n_${Math.random().toString(36).slice(2, 7)}`;
    const cx = layout ? layout.canvas[0] / 2 : 900;
    const cy = layout ? layout.canvas[1] / 2 : 500;
    patchYaml(
      addNode(yaml, { id, label: "New Node", type: "node", x: cx - 60, y: cy - 20 }),
    );
    setSelectedNode(id);
  };

  const onDelete = () => {
    if (!selectedNodeId) return;
    patchYaml(removeNode(yaml, selectedNodeId));
    setSelectedNode(null);
  };

  return (
    <div className="section">
      <div className="panel-header" style={{ padding: 0, border: "none", marginBottom: 10 }}>
        Inspector
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button className="btn primary" onClick={onAdd} style={{ flex: 1 }}>
          + Add Node
        </button>
        <button className="btn" onClick={onDelete} disabled={!selectedNodeId}>
          Delete
        </button>
      </div>

      {selected ? (
        <>
          <div className="field">
            <label>Label</label>
            <input
              className="input"
              value={selected.label}
              onChange={(e) =>
                patchYaml(updateNode(yaml, selectedNodeId!, { label: e.target.value }))
              }
            />
          </div>
          <div className="field">
            <label>Type</label>
            <select
              className="input"
              value={selected.type}
              onChange={(e) =>
                patchYaml(
                  updateNode(yaml, selectedNodeId!, { type: e.target.value as PrimitiveType }),
                )
              }
            >
              {PRIM_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-dim)" }}>
            pos ({Math.round(selected.x)}, {Math.round(selected.y)}) ·{" "}
            {Math.round(selected.w)}×{Math.round(selected.h)}px
            <br />
            Drag on the canvas to move. Connect nodes by dragging from a node's
            right edge to another node.
          </div>
        </>
      ) : (
        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
          Select a node to edit its label and type, or add a new node. Tip: drag
          from a node's right edge onto another node to create a connection.
        </div>
      )}

      {layout && (
        <div style={{ marginTop: 16, fontSize: 11, color: "var(--text-dim)" }}>
          {Object.keys(layout.nodes).length} nodes ·{" "}
          {Object.keys(layout.connections).length} connections · canvas{" "}
          {layout.canvas[0]}×{layout.canvas[1]}
        </div>
      )}
    </div>
  );
}
