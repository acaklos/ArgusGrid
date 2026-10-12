import { describe, expect, it } from "vitest";
import { appendTrail, applyEvent, maxSeverity, rectCorners, StreamEvent, threatenedZones, toLatLng, TRAIL_LIMIT, TrackState } from "./geometry";

const event = (over: Partial<StreamEvent> = {}): StreamEvent => ({
  asset: "RAD-01", kind: "radar", type: "track", track_id: "UAV-001", x: 470, y: 322, altitude: 30, speed: 1,
  heading: 90, confidence: 0.9, zone: "Z2", ring: "critical", severity: "critical", ts: "2026-10-12T08:00:10Z", ...over,
});

describe("map geometry", () => {
  it("maps site metres to Leaflet (lat = y, lng = x)", () => {
    expect(toLatLng(470, 322)).toEqual([322, 470]);
    expect(rectCorners(100, 50, 20, 10)).toEqual([[45, 90], [55, 110]]);
  });

  it("keeps the worse severity", () => {
    expect(maxSeverity("info", "critical")).toBe("critical");
    expect(maxSeverity("warning", "info")).toBe("warning");
  });

  it("applies a live event to the track table and ignores out-of-order or position-less events", () => {
    let tracks: Record<string, TrackState> = {};
    tracks = applyEvent(tracks, event());
    expect(tracks["UAV-001"].zone).toBe("Z2");
    const older = applyEvent(tracks, event({ x: 1, y: 1, ts: "2026-10-12T08:00:05Z" }));
    expect(older["UAV-001"].x).toBe(470); // out of order: ignored
    expect(applyEvent(tracks, event({ x: null, y: null }))).toBe(tracks);
    expect(applyEvent(tracks, event({ track_id: null }))).toBe(tracks);
    const newer = applyEvent(tracks, event({ x: 480, ts: "2026-10-12T08:00:20Z" }));
    expect(newer["UAV-001"].x).toBe(480);
  });

  it("lists threatened zones with the worst severity of active tracks only", () => {
    const base = applyEvent({}, event())["UAV-001"];
    const tracks: TrackState[] = [
      base,
      { ...base, track_id: "UAV-002", severity: "warning", zone: "Z2" },
      { ...base, track_id: "UAV-003", severity: "critical", zone: "Z4", active: false },
      { ...base, track_id: "UAV-004", severity: "warning", zone: "Z6" },
    ];
    expect(threatenedZones(tracks)).toEqual([
      { zone: "Z2", severity: "critical" },
      { zone: "Z6", severity: "warning" },
    ]);
  });

  it("ignores background zones and keeps the precise position against a coarse fix", () => {
    const base = applyEvent({}, event())["UAV-001"];
    const tracks: TrackState[] = [{ ...base, zone: "Z0", severity: "warning" }, { ...base, zone: "Z2" }];
    expect(threatenedZones(tracks, new Set(["Z0"]))).toEqual([{ zone: "Z2", severity: "critical" }]);

    const precise = applyEvent({}, event({ kind: "radar", x: 470, ts: "2026-10-12T08:00:10Z" }));
    const coarse = applyEvent(precise, event({ kind: "rf", x: 520, ts: "2026-10-12T08:00:11Z" }));
    expect(coarse["UAV-001"].x).toBe(470);
    const later = applyEvent(precise, event({ kind: "rf", x: 520, ts: "2026-10-12T08:00:30Z" }));
    expect(later["UAV-001"].x).toBe(520);
  });

  it("bounds the length of a trail", () => {
    let trail: [number, number][] | undefined;
    for (let i = 0; i < TRAIL_LIMIT + 50; i++) trail = appendTrail(trail, i, i);
    expect(trail).toHaveLength(TRAIL_LIMIT);
    expect(trail![trail!.length - 1]).toEqual([TRAIL_LIMIT + 49, TRAIL_LIMIT + 49]);
  });
});
