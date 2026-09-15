import { forceCenter, forceLink, forceManyBody, forceSimulation } from "d3-force-3d";
import type { LayoutType, NodePosition } from "./graphTypes";

interface LayoutNode {
  id: string;
  type: string;
  label?: string;
  sourceKey?: string;
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
  fx?: number | null;
  fy?: number | null;
  fz?: number | null;
}

interface LayoutLink {
  source: string;
  target: string;
  bridge?: boolean;
}

interface LayoutMessage {
  nodes: LayoutNode[];
  links: LayoutLink[];
  layoutType: LayoutType;
  nodeCount: number;
  visualTheme?: "jspace" | "jarvis";
  clusterBySource?: boolean;
}

function layoutRadius(nodeCount: number, base: number): number {
  if (nodeCount <= 60) return base * 0.48;
  if (nodeCount <= 120) return base * 0.62;
  if (nodeCount <= 250) return base * 0.82;
  return base;
}

const HUB_LABELS = ["丝绸之路", "大明宫", "遗产点位", "西安", "唐长安城"];

function findHubId(nodes: LayoutNode[], links: LayoutLink[]): string {
  for (const keyword of HUB_LABELS) {
    const match = nodes.find((node) => node.label?.includes(keyword));
    if (match) return match.id;
  }
  const degree = new Map<string, number>();
  links.forEach((link) => {
    degree.set(link.source, (degree.get(link.source) ?? 0) + 1);
    degree.set(link.target, (degree.get(link.target) ?? 0) + 1);
  });
  return nodes.reduce((best, node) =>
    (degree.get(node.id) ?? 0) > (degree.get(best.id) ?? 0) ? node : best,
  ).id;
}

function buildAdjacency(links: LayoutLink[]): Map<string, string[]> {
  const adjacency = new Map<string, string[]>();
  links.forEach((link) => {
    if (!adjacency.has(link.source)) adjacency.set(link.source, []);
    if (!adjacency.has(link.target)) adjacency.set(link.target, []);
    adjacency.get(link.source)!.push(link.target);
    adjacency.get(link.target)!.push(link.source);
  });
  return adjacency;
}

function computeDepth(hubId: string, nodes: LayoutNode[], links: LayoutLink[]): Map<string, number> {
  const structuralLinks = links.filter((link) => !link.bridge);
  const adjacency = buildAdjacency(structuralLinks.length > 0 ? structuralLinks : links);
  const depth = new Map<string, number>([[hubId, 0]]);
  const queue = [hubId];

  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentDepth = depth.get(current)!;
    (adjacency.get(current) ?? []).forEach((neighbor) => {
      if (!depth.has(neighbor)) {
        depth.set(neighbor, currentDepth + 1);
        queue.push(neighbor);
      }
    });
  }

  let fallbackDepth = 1;
  nodes.forEach((node) => {
    if (!depth.has(node.id)) {
      depth.set(node.id, fallbackDepth);
      fallbackDepth += 1;
    }
  });
  return depth;
}

function pinNode(node: LayoutNode, x: number, y: number, z: number): void {
  node.x = x;
  node.y = y;
  node.z = z;
  node.fx = x;
  node.fy = y;
  node.fz = z;
}

function releaseNode(node: LayoutNode): void {
  node.fx = null;
  node.fy = null;
  node.fz = null;
}

function normalizeAroundHub(nodes: LayoutNode[], hubId: string, targetRadius: number): void {
  const hub = nodes.find((node) => node.id === hubId);
  if (!hub) return;

  pinNode(hub, 0, 0, 0);

  let maxDistance = 0;
  nodes.forEach((node) => {
    if (node.id === hubId) return;
    const distance = Math.hypot(node.x ?? 0, node.y ?? 0, node.z ?? 0);
    maxDistance = Math.max(maxDistance, distance);
  });

  if (maxDistance < 0.001) return;
  const scale = targetRadius / maxDistance;
  nodes.forEach((node) => {
    if (node.id === hubId) return;
    node.x = (node.x ?? 0) * scale;
    node.y = (node.y ?? 0) * scale;
    node.z = (node.z ?? 0) * scale;
  });
}

function semanticOrbitLayout(nodes: LayoutNode[], links: LayoutLink[], hubId: string): void {
  const depthMap = computeDepth(hubId, nodes, links);
  const rings = new Map<number, LayoutNode[]>();

  nodes.forEach((node) => {
    const depth = depthMap.get(node.id) ?? 1;
    if (!rings.has(depth)) rings.set(depth, []);
    rings.get(depth)!.push(node);
  });

  const hub = nodes.find((node) => node.id === hubId);
  if (hub) pinNode(hub, 0, 0, 0);

  const sortedDepths = [...rings.keys()].sort((left, right) => left - right);
  sortedDepths.forEach((depth) => {
    if (depth === 0) return;

    const ringNodes = rings.get(depth) ?? [];
    const typeOrder = ["concept", "place", "person", "event"];
    ringNodes.sort((left, right) => {
      const typeDiff = typeOrder.indexOf(left.type) - typeOrder.indexOf(right.type);
      if (typeDiff !== 0) return typeDiff;
      return (left.label ?? left.id).localeCompare(right.label ?? right.id, "zh-CN");
    });

    const radius = 6 + depth * 9;
    const verticalSpread = Math.min(4, 1.2 + depth * 0.6);
    const angleStep = (Math.PI * 2) / Math.max(ringNodes.length, 1);

    ringNodes.forEach((node, index) => {
      const angle = index * angleStep + depth * 0.35;
      const wobble = Math.sin(index * 1.7 + depth) * 0.8;
      pinNode(
        node,
        Math.cos(angle) * (radius + wobble),
        Math.sin(index * 0.9 + depth) * verticalSpread,
        Math.sin(angle) * (radius + wobble),
      );
    });
  });

  normalizeAroundHub(nodes, hubId, 32);
}

function clusterByType(nodes: LayoutNode[], hubId: string): void {
  const typeIndex = new Map<string, number>();
  let index = 0;
  nodes.forEach((node) => {
    if (!typeIndex.has(node.type)) {
      typeIndex.set(node.type, index);
      index += 1;
    }
  });

  const clusterCount = Math.max(typeIndex.size, 1);
  nodes.forEach((node, nodeIndex) => {
    if (node.id === hubId) {
      pinNode(node, 0, 0, 0);
      return;
    }
    const cluster = typeIndex.get(node.type) ?? 0;
    const sectorAngle = (Math.PI * 2) / clusterCount;
    const baseAngle = cluster * sectorAngle;
    const nodesInCluster = nodes.filter((item) => item.type === node.type && item.id !== hubId);
    const indexInCluster = nodesInCluster.findIndex((item) => item.id === node.id);
    const angle = baseAngle + (indexInCluster / Math.max(nodesInCluster.length, 1)) * sectorAngle * 0.85;
    const radius = 10 + cluster * 4 + (indexInCluster % 3) * 2.5;
    pinNode(
      node,
      Math.cos(angle) * radius,
      Math.sin(nodeIndex * 0.7) * 2.5,
      Math.sin(angle) * radius,
    );
  });

  normalizeAroundHub(nodes, hubId, 30);
}

function runForceRefinement(
  simNodes: LayoutNode[],
  links: LayoutLink[],
  hubId: string,
  iterations: number,
): void {
  const hub = simNodes.find((node) => node.id === hubId);
  if (hub) pinNode(hub, hub.x ?? 0, hub.y ?? 0, hub.z ?? 0);

  const linkForce = forceLink<LayoutNode, LayoutLink>(links)
    .id((node) => node.id)
    .distance((link) => (link.bridge ? 16 : 9))
    .strength((link) => (link.bridge ? 0.12 : 0.62));

  const centerForce = forceCenter(0, 0, 0);
  centerForce.strength?.(0.08);

  const simulation = forceSimulation(simNodes, 3)
    .force("link", linkForce)
    .force("charge", forceManyBody().strength(-22))
    .force("center", centerForce)
    .stop();

  for (let step = 0; step < iterations; step += 1) {
    simulation.tick();
  }

  if (hub) pinNode(hub, 0, 0, 0);
  simNodes.forEach((node) => {
    if (node.id !== hubId) releaseNode(node);
  });
}

function hashSeed(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash) / 2147483647;
}

function jspaceCloudLayout(nodes: LayoutNode[], links: LayoutLink[], nodeCount: number): void {
  const typeGroups = new Map<string, LayoutNode[]>();
  nodes.forEach((node) => {
    if (!typeGroups.has(node.type)) typeGroups.set(node.type, []);
    typeGroups.get(node.type)!.push(node);
  });

  const types = [...typeGroups.keys()];
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const centers = new Map<string, { x: number; y: number; z: number }>();
  const clusterSpread = nodeCount <= 120 ? 0.55 : nodeCount <= 250 ? 0.75 : 1;

  types.forEach((type, index) => {
    const t = (index + 0.5) / Math.max(types.length, 1);
    const inclination = Math.acos(1 - 2 * t);
    const azimuth = goldenAngle * index;
    const radius = (4.5 + (index % 3) * 1.8) * clusterSpread;
    centers.set(type, {
      x: radius * Math.sin(inclination) * Math.cos(azimuth),
      y: (radius * Math.sin(inclination) * Math.sin(azimuth) * 0.45) + (index % 2 === 0 ? 1 : -1),
      z: radius * Math.cos(inclination),
    });
  });

  nodes.forEach((node) => {
    const center = centers.get(node.type) ?? { x: 0, y: 0, z: 0 };
    const clusterSize = typeGroups.get(node.type)?.length ?? 1;
    const sigma = (1.1 + Math.sqrt(clusterSize) * 0.32) * clusterSpread;
    const seed = hashSeed(node.id);
    const seed2 = hashSeed(`${node.id}_y`);
    const seed3 = hashSeed(`${node.id}_z`);
    node.x = center.x + (seed - 0.5) * sigma * 1.6;
    node.y = center.y + (seed2 - 0.5) * sigma * 1.1;
    node.z = center.z + (seed3 - 0.5) * sigma * 1.6;
  });

  runJspaceForce(nodes, links, nodeCount <= 120 ? 220 : 180);
  normalizeCloud(nodes, layoutRadius(nodeCount, 16));
}

function runJspaceForce(simNodes: LayoutNode[], links: LayoutLink[], iterations: number): void {
  const linkForce = forceLink<LayoutNode, LayoutLink>(links)
    .id((node) => node.id)
    .distance((link) => (link.bridge ? 6 : 3.2))
    .strength((link) => (link.bridge ? 0.06 : 0.42));

  const centerForce = forceCenter(0, 0, 0);
  centerForce.strength?.(0.06);

  const simulation = forceSimulation(simNodes, 3)
    .force("link", linkForce)
    .force("charge", forceManyBody().strength(-2.5))
    .force("center", centerForce)
    .stop();

  for (let step = 0; step < iterations; step += 1) {
    simulation.tick();
  }
}

function normalizeCloud(nodes: LayoutNode[], targetRadius: number): void {
  let maxDistance = 0;
  nodes.forEach((node) => {
    const distance = Math.hypot(node.x ?? 0, node.y ?? 0, node.z ?? 0);
    maxDistance = Math.max(maxDistance, distance);
  });
  if (maxDistance < 0.001) return;
  const scale = targetRadius / maxDistance;
  nodes.forEach((node) => {
    node.x = (node.x ?? 0) * scale;
    node.y = (node.y ?? 0) * scale;
    node.z = (node.z ?? 0) * scale;
  });
}

function sourcePlanetLayout(nodes: LayoutNode[], links: LayoutLink[], nodeCount: number): void {
  const clusters = new Map<string, LayoutNode[]>();
  nodes.forEach((node) => {
    const key = node.sourceKey || "unknown";
    if (!clusters.has(key)) clusters.set(key, []);
    clusters.get(key)!.push(node);
  });

  const clusterEntries = [...clusters.entries()]
    .map(([id, clusterNodes], index) => ({ id, clusterNodes, index }))
    .sort((left, right) => right.clusterNodes.length - left.clusterNodes.length);

  if (clusterEntries.length <= 1) {
    jspaceCloudLayout(nodes, links, nodeCount);
    normalizeCloud(nodes, layoutRadius(nodeCount, 16));
    return;
  }

  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const satelliteCount = clusterEntries.length - 1;
  const orbitRadius = 14 + satelliteCount * 7;

  clusterEntries.forEach(({ clusterNodes, index }) => {
    const clusterIds = new Set(clusterNodes.map((node) => node.id));
    const clusterLinks = links.filter((link) => clusterIds.has(link.source) && clusterIds.has(link.target));
    const localNodes: LayoutNode[] = clusterNodes.map((node) => ({
      ...node,
      x: 0,
      y: 0,
      z: 0,
      fx: null,
      fy: null,
      fz: null,
    }));

    jspaceCloudLayout(localNodes, clusterLinks, clusterNodes.length);
    const localRadius = Math.min(20, 5 + Math.sqrt(clusterNodes.length) * 1.35);
    normalizeCloud(localNodes, localRadius);

    let cx = 0;
    let cy = 0;
    let cz = 0;
    if (index > 0) {
      const orbitIndex = index - 1;
      const t = (orbitIndex + 0.5) / Math.max(satelliteCount, 1);
      const inclination = Math.acos(1 - 2 * t);
      const azimuth = goldenAngle * orbitIndex;
      cx = orbitRadius * Math.sin(inclination) * Math.cos(azimuth);
      cy = orbitRadius * Math.sin(inclination) * Math.sin(azimuth) * 0.35;
      cz = orbitRadius * Math.cos(inclination);
    }

    localNodes.forEach((node) => {
      const target = clusterNodes.find((item) => item.id === node.id);
      if (!target) return;
      target.x = (node.x ?? 0) + cx;
      target.y = (node.y ?? 0) + cy;
      target.z = (node.z ?? 0) + cz;
    });
  });
}

self.onmessage = (event: MessageEvent<LayoutMessage>) => {
  const { nodes, links, layoutType, nodeCount, visualTheme = "jspace", clusterBySource = false } = event.data;
  const hubId = findHubId(nodes, links);

  const simNodes: LayoutNode[] = nodes.map((node) => ({
    ...node,
    x: 0,
    y: 0,
    z: 0,
    fx: null,
    fy: null,
    fz: null,
  }));

  if (clusterBySource) {
    sourcePlanetLayout(simNodes, links, nodeCount);
  } else if (layoutType === "jspace_cloud") {
    jspaceCloudLayout(simNodes, links, nodeCount);
  } else if (layoutType === "semantic_orbit") {
    semanticOrbitLayout(simNodes, links, hubId);
    runForceRefinement(simNodes, links, hubId, 80);
    normalizeAroundHub(simNodes, hubId, layoutRadius(nodeCount, 32));
  } else if (layoutType === "cluster_3d") {
    clusterByType(simNodes, hubId);
    runForceRefinement(simNodes, links, hubId, 100);
    normalizeAroundHub(simNodes, hubId, layoutRadius(nodeCount, 30));
  } else if (visualTheme === "jspace") {
    jspaceCloudLayout(simNodes, links, nodeCount);
  } else {
    const hub = simNodes.find((node) => node.id === hubId);
    if (hub) pinNode(hub, 0, 0, 0);

    simNodes.forEach((node, index) => {
      if (node.id === hubId) return;
      const angle = (index / simNodes.length) * Math.PI * 2;
      const radius = 8 + (index % 4) * 2;
      node.x = Math.cos(angle) * radius;
      node.y = Math.sin(index * 0.8) * 2;
      node.z = Math.sin(angle) * radius;
    });

    runForceRefinement(simNodes, links, hubId, 220);
    normalizeAroundHub(simNodes, hubId, layoutRadius(nodeCount, 34));
  }

  const positions: NodePosition[] = simNodes.map((node) => ({
    id: node.id,
    x: node.x ?? 0,
    y: node.y ?? 0,
    z: node.z ?? 0,
  }));

  self.postMessage({ positions });
};

export {};
