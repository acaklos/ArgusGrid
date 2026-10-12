import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { CheckboxField } from "../components/Field";
import { ageSeconds } from "../map/geometry";
import { Layers, SiteMap } from "../map/SiteMap";
import { useLiveOperations, useThemeKey } from "../state/useLiveOperations";
import { useTerm } from "../state/useTerm";

export const DEFAULT_LAYERS: Layers = {
  zones: true, buildings: true, airspace: true, sensors: true, assets: false, trails: true,
};

export function MapPage() {
  const { t } = useTranslation();
  const term = useTerm();
  const theme = useThemeKey();
  const live = useLiveOperations(false);
  const { site, sensors, assets, tracks, activeTracks, trails, alarms, threatened, status, error, now } = live;
  const [layers, setLayers] = useState<Layers>(DEFAULT_LAYERS);

  const labels = useMemo(() => ({
    sensorOnline: t("map.sensor_online"), sensorOffline: t("map.sensor_offline"), altitude: t("map.altitude"),
  }), [t]);

  const toggle = (key: keyof Layers) => setLayers((l) => ({ ...l, [key]: !l[key] }));

  return (
    <>
      <h1>{term("nav.map")}</h1>
      {error && <div className="banner banner--error" role="alert">{error}</div>}
      <div className="toolbar">
        <span className={`badge ${status === "open" ? "badge--ok" : "badge--warn"}`} data-testid="stream-status">
          {t(`map.stream.${status}`)}
        </span>
        {(["zones", "buildings", "airspace", "sensors", "assets", "trails"] as const).map((key) => (
          <CheckboxField key={key} label={t(`map.layer.${key}`)} checked={layers[key]} onChange={() => toggle(key)} />
        ))}
      </div>

      <div className="mapgrid">
        <div className="card mapcard">
          <SiteMap site={site} sensors={sensors} assets={assets} tracks={tracks} trails={trails}
            threatened={threatened} layers={layers} theme={theme} labels={labels} />
        </div>

        <div>
          <section className="card" aria-label={t("map.threatened")}>
            <h2>{t("map.threatened")}</h2>
            {threatened.length === 0 && <p className="field__help" data-testid="no-threat">{t("map.no_threat")}</p>}
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {threatened.map((z) => (
                <li key={z.zone} data-testid={`threat-${z.zone}`}>
                  <span className={`badge ${z.severity === "critical" ? "badge--bad" : "badge--warn"}`}>
                    {t(`map.severity.${z.severity}`)}
                  </span>{" "}
                  <span className="mono">{z.zone}</span>{" "}
                  {site?.zones.find((s) => s.code === z.zone)?.name}
                </li>
              ))}
            </ul>
          </section>

          <section className="card" aria-label={t("map.tracks")}>
            <h2>{t("map.tracks")}</h2>
            {activeTracks.length === 0 && <p className="field__help">{t("map.no_tracks")}</p>}
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {activeTracks.map((tr) => (
                <li key={tr.track_id} data-testid={`track-${tr.track_id}`}>
                  <span className="mono">{tr.track_id}</span> · {tr.zone ?? "—"} · {t(`map.ring.${tr.ring}`, { defaultValue: tr.ring })}
                  {tr.altitude !== null && ` · ${Math.round(tr.altitude)} m`}
                  {tr.speed !== null && ` · ${tr.speed.toFixed(1)} m/s`}
                  <span className="field__help"> · {t("map.updated", { seconds: ageSeconds(tr.ts, now) })}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="card" aria-label={t("map.alarms")}>
            <h2>{t("map.alarms")}</h2>
            {alarms.length === 0 && <p className="field__help">{t("common.empty")}</p>}
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {alarms.slice(0, 8).map((a, i) => (
                <li key={`${a.ts}-${i}`}>
                  <span className={`badge ${a.severity === "critical" ? "badge--bad" : "badge--warn"}`}>{a.severity}</span>{" "}
                  <span className="mono">{a.kind}</span> · {a.asset}
                  {a.zone && ` · ${a.zone}`}
                  <span className="field__help"> · {new Date(a.ts).toLocaleTimeString()}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
