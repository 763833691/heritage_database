import type { EntityType } from "../types";
import type { GraphStyleConfig, NodeTypeStyle, VisualTheme } from "./graphTypes";

const jarvisNodeTypes: Record<EntityType | "other", NodeTypeStyle> = {
  place: {
    label: "地点",
    color: "#3b82f6",
    emissive: "#1d4ed8",
    bgClass: "bg-blue-500/20 text-blue-300 border-blue-400/30",
  },
  person: {
    label: "人物",
    color: "#22c55e",
    emissive: "#15803d",
    bgClass: "bg-emerald-500/20 text-emerald-300 border-emerald-400/30",
  },
  event: {
    label: "事件",
    color: "#f97316",
    emissive: "#c2410c",
    bgClass: "bg-orange-500/20 text-orange-300 border-orange-400/30",
  },
  concept: {
    label: "概念",
    color: "#a855f7",
    emissive: "#7e22ce",
    bgClass: "bg-violet-500/20 text-violet-300 border-violet-400/30",
  },
  file: {
    label: "文献",
    color: "#94a3b8",
    emissive: "#64748b",
    bgClass: "bg-slate-500/20 text-slate-300 border-slate-400/30",
  },
  other: {
    label: "其他",
    color: "#64748b",
    emissive: "#475569",
    bgClass: "bg-slate-500/20 text-slate-300 border-slate-400/30",
  },
};

/** J-space：加深灰阶，白底上更易辨认 */
const jspaceNodeTypes: Record<EntityType | "other", NodeTypeStyle> = {
  place: {
    label: "地点",
    color: "#374151",
    emissive: "#374151",
    bgClass: "bg-gray-100 text-gray-600 border-gray-200",
  },
  person: {
    label: "人物",
    color: "#1f2937",
    emissive: "#1f2937",
    bgClass: "bg-gray-100 text-gray-600 border-gray-200",
  },
  event: {
    label: "事件",
    color: "#44403c",
    emissive: "#44403c",
    bgClass: "bg-stone-100 text-stone-600 border-stone-200",
  },
  concept: {
    label: "概念",
    color: "#6b7280",
    emissive: "#6b7280",
    bgClass: "bg-gray-50 text-gray-500 border-gray-200",
  },
  file: {
    label: "文献",
    color: "#a3a3a3",
    emissive: "#a3a3a3",
    bgClass: "bg-gray-50 text-gray-500 border-gray-200",
  },
  other: {
    label: "其他",
    color: "#737373",
    emissive: "#737373",
    bgClass: "bg-gray-50 text-gray-500 border-gray-200",
  },
};

const themePresets: Record<VisualTheme, Omit<GraphStyleConfig, "nodeTypes">> = {
  jspace: {
    theme: "jspace",
    background: "#f8f9fb",
    gridColor: "#e5e7eb",
    edgeColor: "#e5e7eb",
    edgeHighlightColor: "#374151",
    showEdges: false,
    showEdgesOnSelect: true,
    enableBloom: false,
    showGrid: false,
    showParticles: false,
    labelMode: "interaction",
    nodeSizeScale: 0.072,
  },
  jarvis: {
    theme: "jarvis",
    background: "#050814",
    gridColor: "#1e293b",
    edgeColor: "#334155",
    edgeHighlightColor: "#60a5fa",
    showEdges: true,
    enableBloom: true,
    showGrid: true,
    showParticles: true,
    labelMode: "interaction",
    nodeSizeScale: 0.0625,
  },
};

export function getGraphStyleConfig(theme: VisualTheme = "jspace"): GraphStyleConfig {
  const preset = themePresets[theme];
  const nodeTypes = theme === "jspace" ? jspaceNodeTypes : jarvisNodeTypes;
  return { ...preset, nodeTypes: { ...nodeTypes } };
}

export function getNodeTypeStyle(type: string, styles: GraphStyleConfig): NodeTypeStyle {
  return styles.nodeTypes[type] ?? styles.nodeTypes.other;
}

/** 节点较少时放大点、收紧布局，避免「散成星空」 */
export function adaptiveNodeSizeScale(base: number, nodeCount: number): number {
  if (nodeCount <= 50) return base * 2.1;
  if (nodeCount <= 100) return base * 1.75;
  if (nodeCount <= 200) return base * 1.35;
  return base;
}

export const filterableTypes: EntityType[] = ["place", "person", "event", "concept"];

export const NODE_SIZE_MULTIPLIER_MIN = 0.25;
export const NODE_SIZE_MULTIPLIER_MAX = 2;
export const NODE_SIZE_MULTIPLIER_DEFAULT = 0.65;
export const NODE_SIZE_MULTIPLIER_STEP = 0.05;
