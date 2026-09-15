declare module "d3-force-3d" {
  export function forceSimulation<N extends SimulationNode>(
    nodes: N[],
    numDimensions?: number,
  ): Simulation<N>;
  export function forceLink<N extends SimulationNode, L extends SimulationLink>(
    links?: L[],
  ): ForceLink<N, L>;
  export function forceManyBody<N extends SimulationNode>(): ForceManyBody<N>;
  export function forceCenter(x?: number, y?: number, z?: number): ForceCenter;

  export interface SimulationNode {
    index?: number;
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

  export interface SimulationLink {
    source: string | SimulationNode;
    target: string | SimulationNode;
  }

  export interface Simulation<N extends SimulationNode> {
    force(name: string, force?: unknown): this;
    stop(): this;
    tick(): this;
  }

  export interface ForceLink<N extends SimulationNode, L extends SimulationLink> {
    id(accessor: (node: N) => string): this;
    distance(distance: number | ((link: L) => number)): this;
    strength(strength: number | ((link: L) => number)): this;
  }

  export interface ForceManyBody<N extends SimulationNode> {
    strength(strength: number | ((node: N, index: number) => number)): this;
  }

  export interface ForceCenter {
    (nodes: SimulationNode[]): void;
    strength?(strength: number): this;
  }
}
