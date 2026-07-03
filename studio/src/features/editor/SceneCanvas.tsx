import { useCallback, useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type OnConnect,
  type NodeTypes,
  type EdgeTypes,
} from "@xyflow/react";
import { useStudioStore } from "../../store/useStudioStore";
import { getTheme } from "../../lib/themes";
import {
  addConnection as yamlAddConnection,
  setNodePosition,
} from "../../lib/yamlOps";
import { PrimitiveNode, RoutedEdge, type PrimNodeData } from "./nodes";

const nodeTypes: NodeTypes = { primitive: PrimitiveNode };
const edgeTypes: EdgeTypes = { routed: RoutedEdge };

function buildNodes(
  layout: { nodes: Record<string, { label: string; type: PrimNodeData["primitiveType"]; x: number; y: number; w: number; h: number }> },
  themeId: string,
): Node<PrimNodeData>[] {
  return Object.entries(layout.nodes).map(([id, n]) => ({
    id,
    type: "primitive",
    position: { x: n.x, y: n.y },
    width: n.w,
    height: n.h,
    data: { label: n.label, primitiveType: n.type, themeId, w: n.w, h: n.h },
  }));
}

function buildEdges(
  layout: { connections: Record<string, { source: string; target: string; route: [number, number][] }> },
  stroke: string,
): Edge[] {
  return Object.entries(layout.connections).map(([id, c]) => ({
    id,
    source: c.source,
    target: c.target,
    type: "routed",
    data: { route: c.route, stroke },
  }));
}

export default function SceneCanvas() {
  const result = useStudioStore((s) => s.result);
  const themeId = useStudioStore((s) => s.themeId);
  const yaml = useStudioStore((s) => s.yaml);
  const patchYaml = useStudioStore((s) => s.patchYaml);
  const setSelectedNode = useStudioStore((s) => s.setSelectedNode);

  const layout = result?.ok ? result.layout : null;
  const theme = getTheme(themeId);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<PrimNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // A compact signature of the layout so we only resync when it actually changes
  // (after a recompile), not on every keystroke-driven render.
  const layoutSig = useMemo(
    () => (layout ? JSON.stringify(layout) : ""),
    [layout],
  );

  useEffect(() => {
    if (!layout) {
      setNodes([]);
      setEdges([]);
      return;
    }
    setNodes(buildNodes(layout, themeId));
    setEdges(buildEdges(layout, theme.connStroke));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutSig, themeId]);

  const onNodeDragStop = useCallback(
    (_evt: unknown, node: Node) => {
      // Clamp within canvas bounds so the engine's overflow check never trips.
      const canvas = layout?.canvas ?? [1920, 1080];
      const clampedX = Math.max(0, Math.min(node.position.x, canvas[0] - 10));
      const clampedY = Math.max(0, Math.min(node.position.y, canvas[1] - 10));
      const next = setNodePosition(yaml, node.id, clampedX, clampedY);
      patchYaml(next);
    },
    [yaml, patchYaml, layout],
  );

  const onConnect = useCallback<OnConnect>(
    (conn: Connection) => {
      if (!conn.source || !conn.target) return;
      const id = `c_${Date.now().toString(36)}`;
      patchYaml(yamlAddConnection(yaml, { id, source: conn.source, target: conn.target }));
    },
    [yaml, patchYaml],
  );

  return (
    <div className="canvas-host" style={{ background: theme.bg }}>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <defs>
          <marker
            id="am-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill={theme.connStroke} />
          </marker>
        </defs>
      </svg>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={(_e, node) => setSelectedNode(node.id)}
        onPaneClick={() => setSelectedNode(null)}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: "routed" }}
      >
        <Background gap={20} size={1} color={theme.connStroke} />
        <MiniMap pannable zoomable nodeColor={() => theme.nodeFill} maskColor="rgba(0,0,0,0.4)" />
        <Controls />
      </ReactFlow>
    </div>
  );
}

// Keep the NodeProps type referenced for downstream consumers.
export type { NodeProps };
