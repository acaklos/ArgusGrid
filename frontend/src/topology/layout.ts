// Layered layout of an incident graph: the physical event at the top, then the exposed assets, the dependency
// path, the compromised asset and the assets at risk by hop distance. Pure and deterministic.
import type { IncidentGraph } from "../api/client";

export type GraphNode = IncidentGraph["nodes"][number];

export interface Positioned {
  id: string;
  x: number;
  y: number;
  layer: number;
}

export const LAYER_GAP = 100;
export const NODE_GAP = 120;
/** A wide layer is wrapped into several rows so the graph stays readable in a half-screen pane. */
export const ROW_MAX = 6;

export function layerOf(node: GraphNode, maxPathLayer: number): number {
  switch (node.role) {
    case "physical_event":
      return 0;
    case "entry":
      return 1;
    case "path":
      return 2;
    case "compromised":
      return Math.max(3, maxPathLayer + 1);
    default:
      return Math.max(3, maxPathLayer + 1) + Math.max(1, node.hop);
  }
}

export function layout(nodes: GraphNode[]): Positioned[] {
  const maxPath = nodes.some((n) => n.role === "path") ? 2 : 1;
  const layers = new Map<number, GraphNode[]>();
  for (const n of nodes) {
    const l = layerOf(n, maxPath);
    layers.set(l, [...(layers.get(l) ?? []), n]);
  }
  const result: Positioned[] = [];
  const sorted = [...layers.keys()].sort((a, b) => a - b);
  let row = 0;
  for (const layer of sorted) {
    const items = layers.get(layer)!.sort((a, b) => a.code.localeCompare(b.code));
    for (let start = 0; start < items.length; start += ROW_MAX) {
      const chunk = items.slice(start, start + ROW_MAX);
      const width = (chunk.length - 1) * NODE_GAP;
      chunk.forEach((n, i) => result.push({ id: n.id, x: i * NODE_GAP - width / 2, y: row * LAYER_GAP, layer }));
      row += 1;
    }
  }
  return result;
}

/** Cytoscape shape per asset type (plan 3.5): hexagon controllers, rectangle servers, diamond network gear. */
export function shapeOf(assetType: string): string {
  switch (assetType) {
    case "plc":
    case "rtu":
    case "ied":
      return "hexagon";
    case "server":
    case "time_server":
      return "round-rectangle";
    case "firewall":
    case "gateway":
    case "router":
    case "switch":
    case "wireless_ap":
      return "diamond";
    case "physical_event":
      return "star";
    default:
      return "ellipse";
  }
}
