import type { EntityType, GraphData } from "../types";

export type LayoutType = "jspace_cloud" | "force_3d" | "cluster_3d" | "semantic_orbit";
export type VisualTheme = "jspace" | "jarvis";
export type LabelMode = "interaction" | "cluster" | "both";

export interface NodeTypeStyle {
  label: string;
  color: string;
  emissive: string;
  bgClass: string;
}

export interface GraphStyleConfig {
  theme: VisualTheme;
  background: string;
  gridColor: string;
  edgeColor: string;
  edgeHighlightColor: string;
  showEdges: boolean;
  /** J-space 下选中节点时临时显示关联边 */
  showEdgesOnSelect?: boolean;
  enableBloom: boolean;
  showGrid: boolean;
  showParticles: boolean;
  labelMode: LabelMode;
  nodeSizeScale: number;
  /** 用户手动调节的点大小倍率（1 = 默认） */
  nodeSizeMultiplier?: number;
  nodeTypes: Record<string, NodeTypeStyle>;
}

export interface RenderNode {
  id: string;
  label: string;
  type: EntityType | string;
  group: string;
  size: number;
  score: number;
  summary: string;
  x: number;
  y: number;
  z: number;
  color: string;
  emissive: string;
  evidenceIds: string[];
  metadata: Record<string, unknown>;
}

export interface RenderLink {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string;
  weight: number;
  confidence: number;
  evidenceId?: string;
  metadata: Record<string, unknown>;
}

export interface RenderEvidence {
  id: string;
  sourceDoc: string;
  title: string;
  page: string;
  text: string;
  relatedLinkId?: string;
  confidence: number;
}

export interface RenderGraphData {
  graphId: string;
  name: string;
  skillId: string;
  nodes: RenderNode[];
  links: RenderLink[];
  evidence: RenderEvidence[];
  styles: GraphStyleConfig;
}

export interface NodePosition {
  id: string;
  x: number;
  y: number;
  z: number;
}

export interface GraphSelectionState {
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  highlightedNodeIds: Set<string>;
  highlightedLinkIds: Set<string>;
}

export interface GraphFilterState {
  activeTypes: Set<EntityType>;
  searchQuery: string;
  layoutType: LayoutType;
  visualTheme: VisualTheme;
}

export type RawGraphInput = GraphData;
