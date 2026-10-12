import cytoscape, { Core, ElementDefinition } from "cytoscape";
import { useEffect, useMemo, useRef } from "react";
import type { IncidentGraph } from "../api/client";
import { layout, shapeOf } from "./layout";

interface Props {
  graph: IncidentGraph | null;
  theme: string;
  /** asset code highlighted from the other pane (map) or by selection */
  highlight?: string | null;
  onSelectNode?: (code: string | null) => void;
  ariaLabel: string;
  roleLabels: Record<string, string>;
}

function css(name: string, fallback = "#888"): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

/**
 * Topology of one incident (Cytoscape.js): the physical event, the exposed assets, the dependency path, the
 * compromised asset and the assets at risk by hop. Shapes carry the asset type, the ring carries the role, so
 * colour is never the only signal. The container exposes `data-nodes` (code:role) for tests and assistive use.
 */
export function TopologyGraph({ graph, theme, highlight, onSelectNode, ariaLabel, roleLabels }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const selectRef = useRef(onSelectNode);
  selectRef.current = onSelectNode;

  const positions = useMemo(() => (graph ? new Map(layout(graph.nodes).map((p) => [p.id, p])) : new Map()), [graph]);

  useEffect(() => {
    if (!host.current) return;
    const instance = cytoscape({ container: host.current, elements: [], userZoomingEnabled: true, minZoom: 0.3,
      maxZoom: 2.5, wheelSensitivity: 0.3 });
    instance.on("tap", "node", (e) => selectRef.current?.(e.target.data("code") as string));
    instance.on("tap", (e) => {
      if (e.target === instance) selectRef.current?.(null);
    });
    cy.current = instance;
    return () => {
      instance.destroy();
      cy.current = null;
    };
  }, []);

  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.elements().remove();
    if (!graph) return;
    const elements: ElementDefinition[] = [
      ...graph.nodes.map((n) => {
        const p = positions.get(n.id);
        return {
          group: "nodes" as const,
          data: { id: n.id, code: n.code, label: `${n.code}\n${roleLabels[n.role] ?? n.role}`, role: n.role,
            shape: shapeOf(n.asset_type), hop: n.hop },
          position: { x: p?.x ?? 0, y: p?.y ?? 0 },
          classes: `role-${n.role}`,
        };
      }),
      ...graph.edges.map((e) => ({
        group: "edges" as const,
        data: { id: e.id, source: e.source, target: e.target, kind: e.kind, relation: e.relation },
        classes: e.kind === "hybrid" ? "hybrid" : "relation",
      })),
    ];
    c.add(elements);
    c.style(styleSheet());
    c.fit(undefined, 28);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, theme, roleLabels]);

  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.nodes().removeClass("selected");
    if (highlight) c.nodes().filter((n) => n.data("code") === highlight).addClass("selected");
  }, [highlight, graph]);

  const nodesAttr = graph ? graph.nodes.map((n) => `${n.code}:${n.role}`).join(",") : "";
  return <div ref={host} className="topology" role="img" aria-label={ariaLabel} data-testid="topology"
    data-nodes={nodesAttr} />;
}

function styleSheet(): cytoscape.StylesheetStyle[] {
  const text = css("--color-text");
  const muted = css("--color-text-muted");
  const surface = css("--color-surface-raised");
  const error = css("--color-error");
  const warning = css("--color-warning");
  const primary = css("--color-primary");
  const accent = css("--color-accent");
  return [
    { selector: "node", style: {
      "shape": "data(shape)" as unknown as cytoscape.Css.Node["shape"], "label": "data(label)", "color": text,
      "font-size": 12, "text-wrap": "wrap", "text-valign": "bottom", "text-margin-y": 6, "width": 38, "height": 38,
      "background-color": surface, "border-width": 2, "border-color": muted,
    } },
    { selector: "node.role-physical_event", style: {
      "border-color": accent, "border-width": 4, "background-color": surface, "width": 46, "height": 46,
    } },
    { selector: "node.role-entry", style: { "border-color": accent, "border-width": 3 } },
    { selector: "node.role-path", style: { "border-color": primary, "border-width": 3 } },
    { selector: "node.role-compromised", style: {
      "border-color": error, "border-width": 5, "background-color": error, "background-opacity": 0.25,
    } },
    { selector: "node.role-at_risk", style: {
      "border-color": warning, "border-style": "dashed", "border-width": 3,
    } },
    { selector: "node.role-at_risk[hop > 1]", style: { "border-color": muted, "opacity": 0.85 } },
    { selector: "node.selected", style: { "overlay-color": primary, "overlay-opacity": 0.25, "overlay-padding": 8 } },
    { selector: "edge", style: {
      "width": 2, "line-color": muted, "target-arrow-color": muted, "target-arrow-shape": "triangle",
      "curve-style": "bezier", "arrow-scale": 0.9,
    } },
    { selector: "edge.hybrid", style: {
      "line-color": accent, "target-arrow-color": accent, "line-style": "dashed", "width": 3,
    } },
  ];
}
