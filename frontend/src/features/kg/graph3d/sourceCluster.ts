import type { GraphData } from "../types";
import type { RenderGraphData, RenderLink, RenderNode } from "./graphTypes";

export type SourceClusterMode = "unified" | "by_source";

export interface SourceClusterInfo {
  id: string;
  label: string;
  nodeCount: number;
  color: string;
}

const CLUSTER_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ef4444", "#06b6d4", "#ec4899", "#84cc16"];

export function buildEntitySourceMap(raw: GraphData): Map<string, string> {
  const map = new Map<string, string>();
  const fileIds = new Set(raw.nodes.filter((node) => node.data.type === "file").map((node) => node.data.id));

  raw.nodes.forEach((node) => {
    if (node.data.type === "file") return;
    const source = node.data.source_file;
    if (typeof source === "string" && source) {
      map.set(node.data.id, source);
    }
  });

  raw.edges.forEach((edge) => {
    const relation = edge.data.relation || edge.data.label;
    if (relation !== "CONTAINS") return;
    const fileId = edge.data.source;
    const entityId = edge.data.target;
    if (fileIds.has(fileId)) {
      map.set(entityId, fileId);
    }
  });

  return map;
}

export function resolveSourceLabel(sourceId: string, fileNameMap?: Map<string, string>): string {
  if (sourceId === "unknown") return "未标注来源";
  return fileNameMap?.get(sourceId) ?? sourceId;
}

export function annotateSourceClusters(
  graph: RenderGraphData,
  entitySourceMap: Map<string, string>,
  fileNameMap?: Map<string, string>,
): { graph: RenderGraphData; clusters: SourceClusterInfo[] } {
  const counts = new Map<string, number>();
  graph.nodes.forEach((node) => {
    const sourceId = String(entitySourceMap.get(node.id) ?? node.metadata.source_file ?? "unknown");
    counts.set(sourceId, (counts.get(sourceId) ?? 0) + 1);
  });

  const clusters = [...counts.entries()]
    .sort((left, right) => right[1] - left[1])
    .map(([id, nodeCount], index) => ({
      id,
      label: resolveSourceLabel(id, fileNameMap),
      nodeCount,
      color: CLUSTER_COLORS[index % CLUSTER_COLORS.length],
    }));

  const colorBySource = new Map(clusters.map((cluster) => [cluster.id, cluster.color]));

  const nodes = graph.nodes.map((node) => {
    const sourceId = String(entitySourceMap.get(node.id) ?? node.metadata.source_file ?? "unknown");
    const clusterCount = counts.get(sourceId) ?? 1;
    return {
      ...node,
      metadata: {
        ...node.metadata,
        source_cluster_key: sourceId,
        source_label: resolveSourceLabel(sourceId, fileNameMap),
        source_cluster_color: colorBySource.get(sourceId) ?? CLUSTER_COLORS[0],
        source_cluster_node_count: clusterCount,
      },
    };
  });

  return { graph: { ...graph, nodes }, clusters };
}

export function filterLinksForClusterMode(
  links: RenderLink[],
  nodes: RenderNode[],
  mode: SourceClusterMode,
): RenderLink[] {
  if (mode !== "by_source") return links;
  const clusterByNode = new Map(nodes.map((node) => [node.id, String(node.metadata.source_cluster_key ?? "unknown")]));
  return links.filter((link) => clusterByNode.get(link.source) === clusterByNode.get(link.target));
}

export function filterNodesBySource(nodes: RenderNode[], sourceId: string | null): RenderNode[] {
  if (!sourceId) return nodes;
  return nodes.filter((node) => String(node.metadata.source_cluster_key ?? "unknown") === sourceId);
}

export interface ClusterBounds {
  id: string;
  label: string;
  color: string;
  x: number;
  y: number;
  z: number;
  radius: number;
  nodeCount: number;
}

export interface OverviewCameraTarget {
  x: number;
  y: number;
  z: number;
  distance: number;
}

function average(values: number[]): number {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function computeClusterBounds(nodes: RenderNode[], clusters: SourceClusterInfo[]): ClusterBounds[] {
  const colorById = new Map(clusters.map((cluster) => [cluster.id, cluster.color]));
  const labelById = new Map(clusters.map((cluster) => [cluster.id, cluster.label]));
  const groups = new Map<string, RenderNode[]>();

  nodes.forEach((node) => {
    const key = String(node.metadata.source_cluster_key ?? "unknown");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(node);
  });

  return [...groups.entries()].map(([id, groupNodes]) => {
    const cx = average(groupNodes.map((node) => node.x));
    const cy = average(groupNodes.map((node) => node.y));
    const cz = average(groupNodes.map((node) => node.z));
    let maxDistance = 0;
    groupNodes.forEach((node) => {
      maxDistance = Math.max(maxDistance, Math.hypot(node.x - cx, node.y - cy, node.z - cz));
    });
    return {
      id,
      label: labelById.get(id) ?? resolveSourceLabel(id),
      color: colorById.get(id) ?? CLUSTER_COLORS[0],
      x: cx,
      y: cy,
      z: cz,
      radius: Math.max(5, maxDistance + 3),
      nodeCount: groupNodes.length,
    };
  });
}

/** 根据所有文献簇的包围范围计算总览相机目标 */
export function computeOverviewCameraTarget(bounds: ClusterBounds[]): OverviewCameraTarget {
  if (!bounds.length) {
    return { x: 0, y: 0, z: 0, distance: 52 };
  }
  const cx = average(bounds.map((item) => item.x));
  const cy = average(bounds.map((item) => item.y));
  const cz = average(bounds.map((item) => item.z));
  let maxReach = 0;
  bounds.forEach((item) => {
    const reach = Math.hypot(item.x - cx, item.y - cy, item.z - cz) + item.radius;
    maxReach = Math.max(maxReach, reach);
  });
  return {
    x: cx,
    y: cy,
    z: cz,
    distance: Math.max(32, maxReach * 2.35 + 14),
  };
}
