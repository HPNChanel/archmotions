import { memo } from "react";
import { Handle, Position, type EdgeProps, type NodeProps } from "@xyflow/react";
import { getTheme } from "../../lib/themes";
import type { LayoutConnection, PrimitiveType } from "../../types";

export interface PrimNodeData {
  label: string;
  primitiveType: PrimitiveType;
  themeId: string;
  w: number;
  h: number;
  [key: string]: unknown;
}

/** Corner radius per primitive type, mirroring the engine's shape selection. */
function shapeRadius(t: PrimitiveType): number {
  switch (t) {
    case "database":
      return 4;
    case "cloud":
      return 20;
    case "user":
      return 50;
    case "cache":
      return 4;
    case "queue":
      return 4;
    default:
      return 8;
  }
}

/** A themed node box sized to the engine-resolved bounding box. */
export const PrimitiveNode = memo(function PrimitiveNode({
  data,
  selected,
}: NodeProps) {
  const d = data as PrimNodeData;
  const theme = getTheme(d.themeId);
  return (
    <div
      className={"prim-node" + (selected ? " selected" : "")}
      style={{
        width: d.w,
        height: d.h,
        background: theme.nodeFill,
        borderColor: theme.nodeBorder,
        color: theme.text,
        borderRadius: shapeRadius(d.primitiveType),
      }}
      title={d.primitiveType}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <span>{d.label}</span>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
});

/** Draws the engine-computed (A-star / Manhattan) route polyline as the edge path. */
export function RoutedEdge(props: EdgeProps) {
  const data = props.data as { route?: [number, number][]; stroke?: string } | undefined;
  const route = data?.route ?? [];
  if (route.length < 2) return null;
  const path = route
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`)
    .join(" ");
  return (
    <>
      <path d={path} stroke="transparent" strokeWidth={14} fill="none" />
      <path
        d={path}
        stroke={data?.stroke ?? "#888"}
        strokeWidth={2}
        fill="none"
        markerEnd="url(#am-arrow)"
      />
    </>
  );
}

export type { LayoutConnection };
