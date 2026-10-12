// Pure helpers of the operational map. The site uses a local metric frame: x east, y north, in metres.
import type { LatLngExpression } from "leaflet";

export type Severity = "info" | "warning" | "critical";

/** Leaflet's simple CRS is (lat, lng) = (y, x). */
export function toLatLng(x: number, y: number): [number, number] {
  return [y, x];
}

export function polygonToLatLngs(polygon: number[][]): LatLngExpression[] {
  return polygon.map(([x, y]) => toLatLng(x, y));
}

export function rectCorners(x: number, y: number, w: number, d: number): [[number, number], [number, number]] {
  return [toLatLng(x - w / 2, y - d / 2), toLatLng(x + w / 2, y + d / 2)];
}

const ORDER: Record<Severity, number> = { info: 0, warning: 1, critical: 2 };

export function maxSeverity(a: Severity, b: Severity): Severity {
  return ORDER[a] >= ORDER[b] ? a : b;
}

export function severityVar(severity: Severity): string {
  return severity === "critical" ? "--color-error" : severity === "warning" ? "--color-warning" : "--color-info";
}

/** Seconds since an ISO timestamp, never negative. */
export function ageSeconds(iso: string, now: number = Date.now()): number {
  return Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
}

export interface TrackState {
  track_id: string;
  ts: string;
  x: number;
  y: number;
  altitude: number | null;
  speed: number | null;
  heading: number | null;
  confidence: number | null;
  zone: string | null;
  ring: string;
  severity: Severity;
  kind: string;
  asset: string;
  active: boolean;
  above_ceiling: boolean;
}

export interface StreamEvent {
  asset: string;
  kind: string;
  type: string;
  track_id: string | null;
  x: number | null;
  y: number | null;
  altitude: number | null;
  speed: number | null;
  heading: number | null;
  confidence: number | null;
  zone: string | null;
  ring: string | null;
  severity: Severity;
  ts: string;
}

/** Radar and EO/IR give clean positions; RF and acoustic fixes are coarse and would make the track jump. */
export const PRECISE_KINDS = new Set(["radar", "eoir"]);
const PRECISE_WINDOW_MS = 5000;

/** Merge a live event into the track table. Events without a track or a position are ignored. */
export function applyEvent(tracks: Record<string, TrackState>, ev: StreamEvent): Record<string, TrackState> {
  if (!ev.track_id || ev.x === null || ev.y === null) return tracks;
  const previous = tracks[ev.track_id];
  const evTime = new Date(ev.ts).getTime();
  if (previous && new Date(previous.ts).getTime() > evTime) return tracks; // out of order
  if (previous && PRECISE_KINDS.has(previous.kind) && !PRECISE_KINDS.has(ev.kind) &&
      evTime - new Date(previous.ts).getTime() < PRECISE_WINDOW_MS) {
    return tracks; // a coarse fix right after a precise one adds nothing
  }
  return {
    ...tracks,
    [ev.track_id]: {
      track_id: ev.track_id, ts: ev.ts, x: ev.x, y: ev.y, altitude: ev.altitude, speed: ev.speed,
      heading: ev.heading, confidence: ev.confidence, zone: ev.zone, ring: ev.ring ?? previous?.ring ?? "outside",
      severity: ev.severity, kind: ev.kind, asset: ev.asset, active: true, above_ceiling: previous?.above_ceiling ?? false,
    },
  };
}

/** Zones that currently have an active track in them, with the worst severity. Background zones (the buffer
 *  that covers the site) locate a position but are not a threatened sector. */
export function threatenedZones(
  tracks: TrackState[], background: ReadonlySet<string> = new Set(),
): { zone: string; severity: Severity }[] {
  const worst = new Map<string, Severity>();
  for (const t of tracks) {
    if (!t.active || !t.zone || background.has(t.zone)) continue;
    worst.set(t.zone, maxSeverity(worst.get(t.zone) ?? "info", t.severity));
  }
  return [...worst.entries()].map(([zone, severity]) => ({ zone, severity })).sort((a, b) => a.zone.localeCompare(b.zone));
}

export const TRAIL_LIMIT = 240;

export function appendTrail(trail: [number, number][] | undefined, x: number, y: number): [number, number][] {
  const next = [...(trail ?? []), toLatLng(x, y)];
  return next.length > TRAIL_LIMIT ? next.slice(next.length - TRAIL_LIMIT) : next;
}
