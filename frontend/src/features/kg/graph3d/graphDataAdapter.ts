import type { EntityType, GraphData } from "../types";
import { prepareDisplayGraph } from "../graphDisplay";
import { getGraphStyleConfig, getNodeTypeStyle, adaptiveNodeSizeScale } from "./graphStyleConfig";
import { annotateSourceClusters, buildEntitySourceMap } from "./sourceCluster";
import type { RenderEvidence, RenderGraphData, RenderLink, RenderNode, VisualTheme } from "./graphTypes";

function isStructuralEdge(relation: string | undefined): boolean {
  return relation === "CONTAINS";
}

function countConnections(nodeId: string, edges: GraphData["edges"]): number {
  return edges.filter((edge) => edge.data.source === nodeId || edge.data.target === nodeId).length;
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

function nodeSizeForTheme(connections: number, theme: VisualTheme): number {
  if (theme === "jspace") {
    return 1 + (hashString(String(connections)) % 3) * 0.15;
  }
  return Math.min(10, Math.max(3, 3 + Math.sqrt(connections) * 0.75));
}

export function adaptGraphData(
  raw: GraphData,
  graphId = "dmg_semantic_graph",
  theme: VisualTheme = "jspace",
  fileNameMap?: Map<string, string>,
): RenderGraphData {
  const styles = getGraphStyleConfig(theme);
  const entitySourceMap = buildEntitySourceMap(raw);
  const entityNodes = raw.nodes.filter((node) => node.data.type !== "file");
  const allowedIds = new Set(entityNodes.map((node) => node.data.id));
  const semanticEdges = raw.edges.filter(
    (edge) =>
      allowedIds.has(edge.data.source) &&
      allowedIds.has(edge.data.target) &&
      !isStructuralEdge(edge.data.relation) &&
      !isStructuralEdge(edge.data.label),
  );
  const display = prepareDisplayGraph(entityNodes, semanticEdges);

  const nodes: RenderNode[] = display.nodes.map((node) => {
    const type = node.data.type as EntityType;
    const typeStyle = getNodeTypeStyle(type, styles);
    const connections = countConnections(node.data.id, display.edges);
    return {
      id: node.data.id,
      label: node.data.name || node.data.label,
      type,
      group: typeStyle.label,
      size: nodeSizeForTheme(connections, theme),
      score: Math.min(5, Math.max(1, Math.round(connections / 3) + 1)),
      summary: node.data.description ?? "",
      x: 0,
      y: 0,
      z: 0,
      color: typeStyle.color,
      emissive: typeStyle.emissive,
      evidenceIds: node.data.source_file ? [`ev_${node.data.id}`] : [],
      metadata: {
        source_file: entitySourceMap.get(node.data.id) ?? node.data.source_file ?? null,
        connection_count: connections,
        semantic_value: Math.min(5, Math.max(1, Math.round(connections / 2))),
        public_perception: Math.min(5, Math.max(1, 3)),
        visibility: Math.min(5, Math.max(1, 2)),
        explanation: Math.min(5, Math.max(1, 2)),
      },
    };
  });

  const nodeIds = new Set(nodes.map((node) => node.id));
  const links: RenderLink[] = display.edges
    .filter((edge) => nodeIds.has(edge.data.source) && nodeIds.has(edge.data.target))
    .map((edge) => ({
      id: edge.data.id,
      source: edge.data.source,
      target: edge.data.target,
      type: edge.data.relation,
      label: edge.data.label || edge.data.relation,
      weight: edge.data.weight ?? 0.5,
      confidence: edge.data.weight ?? 0.5,
      evidenceId: `ev_link_${edge.data.id}`,
      metadata: {
        bridge: edge.data.bridge ?? false,
        confirmed: !edge.data.bridge,
      },
    }));

  const evidence: RenderEvidence[] = [];
  nodes.forEach((node) => {
    if (node.metadata.source_file) {
      evidence.push({
        id: `ev_${node.id}`,
        sourceDoc: String(node.metadata.source_file),
        title: `${node.label} 来源文献`,
        page: "-",
        text: node.summary || `${node.label} 的相关描述信息。`,
        relatedLinkId: links.find((link) => link.source === node.id || link.target === node.id)?.id,
        confidence: 0.85,
      });
    }
  });

  links.slice(0, 40).forEach((link) => {
    evidence.push({
      id: `ev_link_${link.id}`,
      sourceDoc: "graph_relation",
      title: `${link.label} 关系证据`,
      page: "-",
      text: `实体间存在「${link.label}」关系，置信度 ${(link.confidence * 100).toFixed(0)}%。`,
      relatedLinkId: link.id,
      confidence: link.confidence,
    });
  });

  const baseGraph = {
    graphId,
    name: "大明宫知识图谱",
    skillId: "default_semantic_skill",
    nodes,
    links,
    evidence,
    styles: {
      ...styles,
      nodeSizeScale: adaptiveNodeSizeScale(styles.nodeSizeScale, nodes.length),
    },
  };

  return annotateSourceClusters(baseGraph, entitySourceMap, fileNameMap).graph;
}

export function filterRenderGraph(
  graph: RenderGraphData,
  activeTypes: Set<EntityType>,
): RenderGraphData {
  const nodes = graph.nodes.filter((node) => activeTypes.has(node.type as EntityType));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const links = graph.links.filter((link) => nodeIds.has(link.source) && nodeIds.has(link.target));
  return { ...graph, nodes, links };
}

export function getFirstDegreeHighlight(
  graph: RenderGraphData,
  nodeId: string | null,
): { nodeIds: Set<string>; linkIds: Set<string> } {
  if (!nodeId) return { nodeIds: new Set(), linkIds: new Set() };
  const nodeIds = new Set<string>([nodeId]);
  const linkIds = new Set<string>();
  graph.links.forEach((link) => {
    if (link.source === nodeId || link.target === nodeId) {
      linkIds.add(link.id);
      nodeIds.add(link.source);
      nodeIds.add(link.target);
    }
  });
  return { nodeIds, linkIds };
}
