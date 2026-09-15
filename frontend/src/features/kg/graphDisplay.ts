import type { GraphEdge, GraphNode } from "./types";

function unionFindComponents(nodes: GraphNode[], edges: GraphEdge[]): Map<string, string[]> {
  const parent = new Map<string, string>();
  const find = (id: string): string => {
    let root = parent.get(id) ?? id;
    while (parent.get(root) !== root) {
      root = parent.get(root)!;
    }
    let current = id;
    while (current !== root) {
      const next = parent.get(current)!;
      parent.set(current, root);
      current = next;
    }
    return root;
  };
  const union = (left: string, right: string) => {
    const rootLeft = find(left);
    const rootRight = find(right);
    if (rootLeft !== rootRight) parent.set(rootRight, rootLeft);
  };

  nodes.forEach((node) => parent.set(node.data.id, node.data.id));
  edges.forEach((edge) => union(edge.data.source, edge.data.target));

  const groups = new Map<string, string[]>();
  nodes.forEach((node) => {
    const root = find(node.data.id);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root)!.push(node.data.id);
  });
  return groups;
}

function pickHubNode(nodes: GraphNode[]): GraphNode | undefined {
  const preferredNames = ["丝绸之路", "大明宫", "遗产点位", "西安"];
  for (const name of preferredNames) {
    const match = nodes.find((node) => node.data.name === name || node.data.name.includes(name));
    if (match) return match;
  }
  return nodes[0];
}

export function prepareDisplayGraph(nodes: GraphNode[], edges: GraphEdge[]) {
  const explicitEdges = edges.filter((edge) => edge.data.relation !== "相关");
  const relatedEdges = edges
    .filter((edge) => edge.data.relation === "相关" && (edge.data.weight ?? 0) >= 0.58)
    .sort((left, right) => (right.data.weight ?? 0) - (left.data.weight ?? 0));

  const perNodeLimit = 1;
  const relatedCount = new Map<string, number>();
  const trimmedRelated = relatedEdges.filter((edge) => {
    const sourceCount = relatedCount.get(edge.data.source) ?? 0;
    const targetCount = relatedCount.get(edge.data.target) ?? 0;
    if (sourceCount >= perNodeLimit || targetCount >= perNodeLimit) return false;
    relatedCount.set(edge.data.source, sourceCount + 1);
    relatedCount.set(edge.data.target, targetCount + 1);
    return true;
  });

  let displayEdges: GraphEdge[] = [...explicitEdges, ...trimmedRelated];
  const hub = pickHubNode(nodes);
  if (!hub) return { nodes, edges: displayEdges };

  const components = unionFindComponents(nodes, displayEdges);
  const sortedComponents = [...components.entries()].sort((left, right) => right[1].length - left[1].length);
  const mainRoot = sortedComponents[0]?.[0];

  sortedComponents.slice(1).forEach(([root, memberIds]) => {
    if (root === mainRoot) return;
    const anchorId = memberIds[0];
    const anchor = nodes.find((node) => node.data.id === anchorId);
    if (!anchor || anchor.data.id === hub.data.id) return;
    displayEdges = [
      ...displayEdges,
      {
        data: {
          id: `bridge_${anchor.data.id}_${hub.data.id}`,
          source: anchor.data.id,
          target: hub.data.id,
          label: "关联",
          relation: "关联",
          weight: 0.4,
          bridge: true,
        },
      },
    ];
  });

  return { nodes, edges: displayEdges };
}

export function obsidianLayoutConfig(nodeCount: number) {
  const scale = Math.max(1, nodeCount / 70);
  return {
    name: "fcose",
    quality: "default",
    randomize: true,
    animate: false,
    fit: true,
    padding: 48,
    nodeDimensionsIncludeLabels: true,
    idealEdgeLength: 88 * scale,
    nodeRepulsion: 4200,
    edgeElasticity: 0.45,
    nestingFactor: 0.1,
    gravity: 0.35,
    gravityRange: 3.2,
    numIter: 4000,
    tile: false,
    uniformNodeDimensions: true,
  } as const;
}
