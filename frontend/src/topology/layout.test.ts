import { describe, expect, it } from "vitest";
import { layout, shapeOf, GraphNode, ROW_MAX } from "./layout";

const n = (id: string, code: string, role: GraphNode["role"], hop = 0, type = "server"): GraphNode => ({
  id, asset_id: 1, code, name: code, asset_type: type, level: "3", zone: "Z2", criticality: "high", role, hop,
});

describe("incident graph layout", () => {
  const nodes = [
    n("event", "UAV-001", "physical_event", -2, "physical_event"),
    n("a1", "WIFI-AP-MNT", "entry", -1, "wireless_ap"),
    n("a2", "HMI-03", "path", -1, "hmi"),
    n("a3", "SCADA-SRV-01", "compromised"),
    n("a4", "PLC-GT1", "at_risk", 1, "plc"),
    n("a5", "PLC-SW1", "at_risk", 1, "plc"),
    n("a6", "PLC-GT3", "at_risk", 2, "plc"),
  ];

  it("places the event first and each hop one layer further down", () => {
    const pos = Object.fromEntries(layout(nodes).map((p) => [p.id, p]));
    expect(pos.event.y).toBeLessThan(pos.a1.y);
    expect(pos.a1.y).toBeLessThan(pos.a2.y);
    expect(pos.a2.y).toBeLessThan(pos.a3.y);
    expect(pos.a3.y).toBeLessThan(pos.a4.y);
    expect(pos.a4.y).toBe(pos.a5.y); // same hop, same row
    expect(pos.a4.y).toBeLessThan(pos.a6.y);
  });

  it("centres a row and never overlaps nodes of the same row", () => {
    const row = layout(nodes).filter((p) => p.layer === layout(nodes).find((q) => q.id === "a4")!.layer);
    const xs = row.map((p) => p.x).sort((a, b) => a - b);
    expect(xs[0]).toBeCloseTo(-xs[xs.length - 1]);
    expect(new Set(xs).size).toBe(xs.length);
  });

  it("wraps a wide layer into rows of at most ROW_MAX nodes without overlap", () => {
    const wide = [n("a3", "SCADA", "compromised"), ...Array.from({ length: 9 }, (_, i) => n(`p${i}`, `PLC-${i}`, "at_risk", 1, "plc"))];
    const pos = layout(wide).filter((p) => p.id.startsWith("p"));
    const rows = new Map<number, number[]>();
    for (const p of pos) rows.set(p.y, [...(rows.get(p.y) ?? []), p.x]);
    expect(rows.size).toBe(2);
    for (const xs of rows.values()) {
      expect(xs.length).toBeLessThanOrEqual(ROW_MAX);
      expect(new Set(xs).size).toBe(xs.length);
    }
  });

  it("is deterministic", () => {
    const byId = (a: { id: string }, b: { id: string }) => a.id.localeCompare(b.id);
    expect(layout([...nodes].reverse()).sort(byId)).toEqual(layout(nodes).sort(byId));
  });

  it("uses distinct shapes for controllers, servers and network equipment", () => {
    expect(shapeOf("plc")).toBe("hexagon");
    expect(shapeOf("server")).toBe("round-rectangle");
    expect(shapeOf("firewall")).toBe("diamond");
    expect(shapeOf("sensor")).toBe("ellipse");
    expect(shapeOf("physical_event")).toBe("star");
  });
});
