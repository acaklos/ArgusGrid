import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, AssetDto, endpoints, IncidentDto } from "../api/client";
import { errorMessages } from "../i18n/errors";
import {
  ageSeconds, appendTrail, applyEvent, PRECISE_KINDS, StreamEvent, threatenedZones, toLatLng, TrackState,
} from "../map/geometry";
import { MapAsset, MapSensor, SiteData } from "../map/SiteMap";
import { StreamStatus, useStream } from "./useStream";

export interface AlarmRow {
  ts: string;
  asset: string;
  kind: string;
  type: string;
  track_id: string | null;
  zone: string | null;
  severity: string;
}

interface StateResponse {
  server_time: string;
  tracks: TrackState[];
  threatened_zones: { zone: string; severity: "info" | "warning" | "critical" }[];
  sensors: (MapSensor & { zone: string | null; last_seen_at: string | null })[];
  alarms: AlarmRow[];
}

export interface LiveOperations {
  site: SiteData | null;
  assets: MapAsset[];
  sensors: MapSensor[];
  tracks: (TrackState & { active: boolean })[];
  activeTracks: (TrackState & { active: boolean })[];
  trails: Record<string, [number, number][]>;
  alarms: AlarmRow[];
  threatened: ReturnType<typeof threatenedZones>;
  incidents: IncidentDto[];
  /** Changes whenever an incident message arrives; pages reload the detail of the selected incident on it. */
  incidentTick: number;
  status: StreamStatus;
  error: string | null;
  now: number;
}

/**
 * The live picture shared by the map page and the operator dashboard (SOL-006): site, assets, sensors, tracks,
 * trails, alarms and the active incidents, kept current by one WebSocket and a slow refresh.
 * `withIncidents` is off for users that may not see incidents.
 */
export function useLiveOperations(withIncidents: boolean): LiveOperations {
  const { t } = useTranslation();
  const [site, setSite] = useState<SiteData | null>(null);
  const [assets, setAssets] = useState<MapAsset[]>([]);
  const [sensors, setSensors] = useState<MapSensor[]>([]);
  const [tracks, setTracks] = useState<Record<string, TrackState>>({});
  const [trails, setTrails] = useState<Record<string, [number, number][]>>({});
  const [alarms, setAlarms] = useState<AlarmRow[]>([]);
  const [incidents, setIncidents] = useState<IncidentDto[]>([]);
  const [incidentTick, setIncidentTick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());

  const loadState = useCallback(async () => {
    try {
      const state = await api.get<StateResponse>("/api/v1/telemetry/state");
      const byId: Record<string, TrackState> = {};
      for (const tr of state.tracks) byId[tr.track_id] = tr;
      setTracks(byId);
      setSensors(state.sensors);
      setAlarms(state.alarms);
      // trails of the live tracks come from the stored history, later points arrive over the stream
      const next: Record<string, [number, number][]> = {};
      await Promise.all(state.tracks.filter((x) => x.active).map(async (tr) => {
        const points = await api.get<{ x: number; y: number }[]>(`/api/v1/telemetry/tracks/${tr.track_id}?minutes=30`);
        next[tr.track_id] = points.slice(-240).map((p) => toLatLng(p.x, p.y));
      }));
      setTrails((cur) => ({ ...cur, ...next }));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  }, [t]);

  const loadIncidents = useCallback(async () => {
    if (!withIncidents) return;
    try {
      const page = await endpoints.incidents({ active: true, page_size: 50 });
      setIncidents(page.items);
    } catch {
      /* the picture still works without the incident list */
    }
  }, [withIncidents]);

  useEffect(() => {
    void api.get<SiteData>("/api/v1/site").then(setSite).catch(() => undefined);
    void endpoints.listAssets({ page_size: 200 }).then((p) => setAssets(p.items.map((a: AssetDto) => ({
      code: a.code, name: a.name, x: a.x, y: a.y, category: a.category, criticality: a.criticality,
    })))).catch(() => undefined);
    void loadState();
    void loadIncidents();
    const refresh = window.setInterval(() => {
      void loadState();
      void loadIncidents();
    }, 30000);
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      window.clearInterval(refresh);
      window.clearInterval(clock);
    };
  }, [loadState, loadIncidents]);

  const onMessage = useCallback((message: { type: string; events?: unknown[]; incident?: IncidentDto }) => {
    if (message.type === "incident" && message.incident && withIncidents) {
      const inc = message.incident;
      setIncidents((cur) => {
        const rest = cur.filter((i) => i.id !== inc.id);
        return inc.status === "closed" ? rest : [inc, ...rest];
      });
      setIncidentTick((n) => n + 1);
      return;
    }
    if (message.type !== "telemetry" || !message.events) return;
    const events = message.events as StreamEvent[];
    setTracks((cur) => events.reduce((acc, ev) => applyEvent(acc, ev), cur));
    setTrails((cur) => {
      const next = { ...cur };
      for (const ev of events) {
        if (ev.track_id && ev.x !== null && ev.y !== null && PRECISE_KINDS.has(ev.kind)) {
          next[ev.track_id] = appendTrail(next[ev.track_id], ev.x, ev.y);
        }
      }
      return next;
    });
    setSensors((cur) => cur.map((s) => (events.some((e) => e.asset === s.code) ? { ...s, online: true } : s)));
    const alarmEvents = events.filter((e) => e.type === "alarm");
    if (alarmEvents.length > 0) {
      setAlarms((cur) => [...alarmEvents.map((e) => ({ ts: e.ts, asset: e.asset, kind: e.kind, type: e.type,
        track_id: e.track_id, zone: e.zone, severity: e.severity })), ...cur].slice(0, 50));
    }
  }, [withIncidents]);
  const status = useStream(onMessage as (m: { type: string; events?: unknown[] }) => void);

  // a track that stops updating becomes stale after 90 s (same rule as the server)
  const trackList = useMemo(
    () => Object.values(tracks).map((tr) => ({ ...tr, active: ageSeconds(tr.ts, now) <= 90 })),
    [tracks, now],
  );
  const background = useMemo(
    () => new Set((site?.zones ?? []).filter((z) => z.background).map((z) => z.code)),
    [site],
  );
  const threatened = useMemo(() => threatenedZones(trackList, background), [trackList, background]);
  const activeTracks = useMemo(() => trackList.filter((x) => x.active), [trackList]);

  return {
    site, assets, sensors, tracks: trackList, activeTracks, trails, alarms, threatened, incidents, incidentTick,
    status, error, now,
  };
}

export function useThemeKey(): string {
  const [theme, setTheme] = useState(document.documentElement.dataset.theme ?? "dark");
  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(document.documentElement.dataset.theme ?? "dark"));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return theme;
}
