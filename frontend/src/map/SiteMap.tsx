import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { polygonToLatLngs, rectCorners, Severity, severityVar, toLatLng, TrackState } from "./geometry";

// The physical context of the operator dashboard: floor plan of the site in metres (Leaflet simple CRS).
export interface SiteData {
  width_m: number;
  height_m: number;
  zones: { code: string; name: string; criticality: string; polygon: number[][]; background?: boolean }[];
  buildings: { code: string; name: string; x: number; y: number; w: number; d: number }[];
  gates: { code: string; name: string; x: number; y: number }[];
  airspace: { centre_x: number; centre_y: number; alert_m: number; warning_m: number; critical_m: number };
}

export interface MapSensor {
  code: string;
  name: string;
  x: number | null;
  y: number | null;
  online: boolean;
}

export interface MapAsset {
  code: string;
  name: string;
  x: number | null;
  y: number | null;
  category: string;
  criticality: string;
}

export interface Layers {
  zones: boolean;
  buildings: boolean;
  airspace: boolean;
  sensors: boolean;
  assets: boolean;
  trails: boolean;
}

interface Props {
  site: SiteData | null;
  sensors: MapSensor[];
  assets: MapAsset[];
  tracks: TrackState[];
  trails: Record<string, [number, number][]>;
  threatened: { zone: string; severity: Severity }[];
  layers: Layers;
  theme: string;
  onSelectTrack?: (trackId: string) => void;
  /** Hybrid links of the selected incident: a line from the track to every exposed asset (metres). */
  links?: { from: [number, number]; to: [number, number] }[];
  labels: { sensorOnline: string; sensorOffline: string; altitude: string };
}

function css(name: string, fallback = "#888"): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

const CRITICALITY_COLOUR: Record<string, string> = {
  critical: "--color-error", high: "--color-warning", medium: "--color-primary", low: "--color-text-muted",
};

export function SiteMap({ site, sensors, assets, tracks, trails, threatened, layers, theme, onSelectTrack, links,
  labels }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const groups = useRef<Record<string, L.LayerGroup>>({});
  const fitted = useRef(false);

  // -- map instance -----------------------------------------------------------------------------
  useEffect(() => {
    if (!host.current || map.current) return;
    const instance = L.map(host.current, {
      crs: L.CRS.Simple, minZoom: -3, maxZoom: 3, zoomSnap: 0.25, attributionControl: false, zoomControl: true,
    });
    for (const name of ["zones", "buildings", "airspace", "assets", "sensors", "trails", "tracks", "links"]) {
      groups.current[name] = L.layerGroup().addTo(instance);
    }
    map.current = instance;
    return () => {
      instance.remove();
      map.current = null;
      groups.current = {};
    };
  }, []);

  // -- static picture ---------------------------------------------------------------------------
  useEffect(() => {
    const m = map.current;
    if (!m || !site) return;
    const zones = groups.current.zones;
    const buildings = groups.current.buildings;
    const rings = groups.current.airspace;
    zones.clearLayers();
    buildings.clearLayers();
    rings.clearLayers();

    // the whole-site fallback zone (Z0) is drawn as the site boundary, not as a filled sector
    for (const z of site.zones) {
      const isFallback = z.code === "Z0";
      const colour = css(CRITICALITY_COLOUR[z.criticality] ?? "--color-primary");
      const threat = threatened.find((t) => t.zone === z.code);
      const className = `zone zone-${z.code}${threat ? ` zone--${threat.severity}` : ""}`;
      const poly = L.polygon(polygonToLatLngs(z.polygon), {
        color: threat ? css(severityVar(threat.severity)) : colour, weight: isFallback ? 1 : threat ? 3 : 1.5,
        fillColor: threat ? css(severityVar(threat.severity)) : colour,
        fillOpacity: isFallback ? 0 : threat ? 0.28 : 0.1, dashArray: isFallback ? "6 6" : undefined, className,
      });
      poly.bindTooltip(`${z.code} ${z.name}`, { sticky: true });
      zones.addLayer(poly);
    }
    for (const b of site.buildings) {
      const rect = L.rectangle(rectCorners(b.x, b.y, Math.max(b.w, 6), Math.max(b.d, 6)), {
        color: css("--color-text-muted"), weight: 1, fillColor: css("--color-surface-raised"), fillOpacity: 0.9,
        className: `building building-${b.code}`,
      });
      rect.bindTooltip(`${b.code} ${b.name}`);
      buildings.addLayer(rect);
    }
    for (const g of site.gates) {
      buildings.addLayer(L.circleMarker(toLatLng(g.x, g.y), { radius: 5, color: css("--color-text"), weight: 2,
        fillOpacity: 0, className: `gate gate-${g.code}` }).bindTooltip(`${g.code} ${g.name}`));
    }
    const a = site.airspace;
    for (const [radius, key] of [[a.alert_m, "--color-info"], [a.warning_m, "--color-warning"],
      [a.critical_m, "--color-error"]] as const) {
      rings.addLayer(L.circle(toLatLng(a.centre_x, a.centre_y), {
        radius, color: css(key), weight: 1, fillOpacity: 0, dashArray: "4 8", interactive: false,
        className: "airspace-ring",
      }));
    }
    if (!fitted.current) {
      const margin = 0.15 * Math.max(site.width_m, site.height_m);
      m.fitBounds([[-margin, -margin], [site.height_m + margin, site.width_m + margin]]);
      fitted.current = true;
    }
  }, [site, threatened, theme]);

  // -- sensors and assets -----------------------------------------------------------------------
  useEffect(() => {
    const g = groups.current.sensors;
    if (!g) return;
    g.clearLayers();
    for (const s of sensors) {
      if (s.x === null || s.y === null) continue;
      const colour = css(s.online ? "--color-success" : "--color-text-muted");
      const marker = L.circleMarker(toLatLng(s.x, s.y), {
        radius: 5, color: colour, weight: 2, fillColor: colour, fillOpacity: s.online ? 0.9 : 0.15,
        className: `sensor sensor-${s.code} ${s.online ? "sensor--online" : "sensor--offline"}`,
      });
      marker.bindTooltip(`${s.code} · ${s.online ? labels.sensorOnline : labels.sensorOffline}`);
      g.addLayer(marker);
    }
  }, [sensors, theme, labels]);

  useEffect(() => {
    const g = groups.current.assets;
    if (!g) return;
    g.clearLayers();
    for (const a of assets) {
      if (a.x === null || a.y === null || a.category === "device" && a.code.match(/^(RAD|RF|EO|AC|FOS|ACR|WX)-/)) continue;
      const colour = css(CRITICALITY_COLOUR[a.criticality] ?? "--color-primary");
      g.addLayer(L.rectangle([toLatLng(a.x - 3, a.y - 3), toLatLng(a.x + 3, a.y + 3)], {
        color: colour, weight: 1, fillColor: colour, fillOpacity: 0.7, className: `asset asset-${a.code}`,
      }).bindTooltip(`${a.code} ${a.name}`));
    }
  }, [assets, theme]);

  // -- tracks and trails ------------------------------------------------------------------------
  useEffect(() => {
    const g = groups.current.tracks;
    const tr = groups.current.trails;
    if (!g || !tr) return;
    g.clearLayers();
    tr.clearLayers();
    for (const t of tracks) {
      const colour = css(t.active ? "--color-accent" : "--color-text-muted");
      if (layers.trails && trails[t.track_id]?.length) {
        tr.addLayer(L.polyline(trails[t.track_id], { color: colour, weight: 2, opacity: 0.7, dashArray: "2 6",
          interactive: false, className: "uav-trail" }));
      }
      const heading = t.heading ?? 0;
      const icon = L.divIcon({
        className: "uav-icon",
        html: `<div class="uav ${t.active ? "uav--active" : "uav--stale"} uav--${t.severity}" data-track="${t.track_id}"` +
          ` style="--uav-colour:${colour};transform:rotate(${heading}deg)">&#9650;</div>`,
        iconSize: [26, 26], iconAnchor: [13, 13],
      });
      const marker = L.marker(toLatLng(t.x, t.y), { icon, keyboard: false });
      const alt = t.altitude !== null ? ` · ${labels.altitude} ${Math.round(t.altitude)} m` : "";
      marker.bindTooltip(`${t.track_id}${alt}${t.zone ? ` · ${t.zone}` : ""}`, { permanent: true, direction: "right",
        offset: [10, 0], className: "uav-label" });
      marker.on("click", () => onSelectTrack?.(t.track_id));
      g.addLayer(marker);
    }
  }, [tracks, trails, layers.trails, theme, labels, onSelectTrack]);

  // -- hybrid links of the selected incident ----------------------------------------------------
  useEffect(() => {
    const g = groups.current.links;
    if (!g) return;
    g.clearLayers();
    for (const l of links ?? []) {
      g.addLayer(L.polyline([toLatLng(l.from[0], l.from[1]), toLatLng(l.to[0], l.to[1])], {
        color: css("--color-accent"), weight: 3, dashArray: "8 6", interactive: false, className: "hybrid-link",
      }));
    }
  }, [links, theme]);

  // -- layer visibility -------------------------------------------------------------------------
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const visible: Record<string, boolean> = {
      zones: layers.zones, buildings: layers.buildings, airspace: layers.airspace, sensors: layers.sensors,
      assets: layers.assets, trails: layers.trails, tracks: true,
    };
    for (const [name, group] of Object.entries(groups.current)) {
      const on = visible[name] ?? true;
      if (on && !m.hasLayer(group)) group.addTo(m);
      if (!on && m.hasLayer(group)) m.removeLayer(group);
    }
  }, [layers]);

  return <div ref={host} className="sitemap" role="application" aria-label="Site map" />;
}
