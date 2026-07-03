// Surgical YAML edits from canvas actions. Uses the `yaml` package's document
// model so edits preserve the user's formatting/comments as much as possible.
// The YAML text remains the single source of truth (parsed → compiled).

import { parseDocument, type Document, type YAMLMap, type YAMLSeq } from "yaml";
import type { PrimitiveType } from "../types";

function nodesSeq(doc: Document): YAMLSeq {
  let nodes = doc.get("nodes") as YAMLSeq | undefined;
  if (!nodes) {
    nodes = doc.createNode([]) as unknown as YAMLSeq;
    doc.set("nodes", nodes);
  }
  return nodes;
}

function findNodeMap(doc: Document, nodeId: string): YAMLMap | undefined {
  const nodes = doc.get("nodes") as YAMLSeq | undefined;
  if (!nodes) return undefined;
  for (const item of nodes.items) {
    const map = item as YAMLMap;
    if (map.get("id") === nodeId) return map;
  }
  return undefined;
}

/** Set/update a node's absolute pixel position (top-left). */
export function setNodePosition(yaml: string, nodeId: string, x: number, y: number): string {
  const doc = parseDocument(yaml);
  const node = findNodeMap(doc, nodeId);
  if (!node) return yaml;
  node.set("position", doc.createNode({ x: round(x), y: round(y) }));
  return doc.toString({ lineWidth: 0 });
}

/** Add a new node (absolute position, type, label). Returns updated YAML. */
export function addNode(
  yaml: string,
  node: { id: string; label: string; type: PrimitiveType; x: number; y: number },
): string {
  const doc = parseDocument(yaml);
  const seq = nodesSeq(doc);
  const entry = doc.createNode({
    id: node.id,
    label: node.label,
    type: node.type,
    position: { x: round(node.x), y: round(node.y) },
  });
  seq.add(entry);
  return doc.toString({ lineWidth: 0 });
}

/** Remove a node and any connections referencing it. */
export function removeNode(yaml: string, nodeId: string): string {
  const doc = parseDocument(yaml);
  const nodes = doc.get("nodes") as YAMLSeq | undefined;
  if (nodes) {
    nodes.items = nodes.items.filter((item) => (item as YAMLMap).get("id") !== nodeId);
  }
  const conns = doc.get("connections") as YAMLSeq | undefined;
  if (conns) {
    conns.items = conns.items.filter(
      (item) => {
        const m = item as YAMLMap;
        return m.get("source") !== nodeId && m.get("target") !== nodeId;
      },
    );
  }
  return doc.toString({ lineWidth: 0 });
}

/** Update a node's label or type. */
export function updateNode(
  yaml: string,
  nodeId: string,
  patch: { label?: string; type?: PrimitiveType },
): string {
  const doc = parseDocument(yaml);
  const node = findNodeMap(doc, nodeId);
  if (!node) return yaml;
  if (patch.label !== undefined) node.set("label", patch.label);
  if (patch.type !== undefined) node.set("type", patch.type);
  return doc.toString({ lineWidth: 0 });
}

/** Add a connection between two node ids. */
export function addConnection(yaml: string, conn: { id: string; source: string; target: string }): string {
  const doc = parseDocument(yaml);
  let conns = doc.get("connections") as YAMLSeq | undefined;
  if (!conns) {
    conns = doc.createNode([]) as unknown as YAMLSeq;
    doc.set("connections", conns);
  }
  conns.add(doc.createNode({ id: conn.id, source: conn.source, target: conn.target }));
  return doc.toString({ lineWidth: 0 });
}

/** Remove a connection by id. */
export function removeConnection(yaml: string, connId: string): string {
  const doc = parseDocument(yaml);
  const conns = doc.get("connections") as YAMLSeq | undefined;
  if (conns) {
    conns.items = conns.items.filter((item) => (item as YAMLMap).get("id") !== connId);
  }
  return doc.toString({ lineWidth: 0 });
}

/** Set the scene theme. */
export function setTheme(yaml: string, themeId: string): string {
  const doc = parseDocument(yaml);
  doc.set("theme", themeId);
  return doc.toString({ lineWidth: 0 });
}

function round(n: number): number {
  return Math.round(n * 10) / 10;
}
