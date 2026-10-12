import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { useSearchParams } from "react-router-dom";
import { endpoints, IncidentGraph } from "../api/client";
import { IncidentPanel, SeverityBadge } from "../components/IncidentPanel";
import { Tabs } from "../components/Tabs";
import { Layers, SiteMap } from "../map/SiteMap";
import { useSession } from "../state/session";
import { useTerm } from "../state/useTerm";
import { useLiveOperations, useThemeKey } from "../state/useLiveOperations";
import { TopologyGraph } from "../topology/TopologyGraph";

// the splitter handle points at its panel with aria-controls, so the pane carries the same DOM id
const MAP_PANEL = "dash-map-panel";
const GRAPH_PANEL = "dash-graph-panel";
const LAYERS: Layers = { zones: true, buildings: true, airspace: true, sensors: true, assets: true, trails: true };

type Mode = "wide" | "stacked" | "tabs";

function useMode(): Mode {
  const compute = (): Mode => (window.innerWidth >= 1024 ? "wide" : window.innerWidth >= 768 ? "stacked" : "tabs");
  const [mode, setMode] = useState<Mode>(compute);
  useEffect(() => {
    const onResize = () => setMode(compute());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return mode;
}

/**
 * Operator dashboard (ARG-019): physical context (map) and cyber context (topology) side by side, one shared
 * incident state. The incident strip selects the incident; selecting an asset in the graph or the blast radius
 * highlights it in both panes.
 */
export function DashboardPage() {
  const { t } = useTranslation();
  const term = useTerm();
  const { can } = useSession();
  const theme = useThemeKey();
  const mode = useMode();
  const canIncidents = can("incident.view");
  const live = useLiveOperations(canIncidents);
  const [params, setParams] = useSearchParams();
  const [graph, setGraph] = useState<IncidentGraph | null>(null);
  const [asset, setAsset] = useState<string | null>(null);
  const [tab, setTab] = useState("map");

  const requested = Number(params.get("incident")) || null;
  const selected = useMemo(() => {
    if (requested && live.incidents.some((i) => i.id === requested)) return requested;
    return live.incidents[0]?.id ?? null;
  }, [requested, live.incidents]);

  useEffect(() => {
    if (!selected) {
      setGraph(null);
      return;
    }
    let cancelled = false;
    void endpoints.incidentGraph(selected).then((g) => {
      if (!cancelled) setGraph(g);
    }).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [selected, live.incidentTick]);

  const select = (id: number) => {
    setAsset(null);
    setParams({ incident: String(id) });
  };

  // hybrid link drawn on the map: from the track to each exposed asset of the selected incident
  const links = useMemo(() => {
    const physical = graph?.incident.evidence?.physical;
    if (!physical) return [];
    const from: [number, number] = [physical.track.x, physical.track.y];
    const codes = new Set((physical.link?.candidates ?? []).map((c) => c.asset));
    if (physical.link?.exposed_asset) codes.add(physical.link.exposed_asset);
    return live.assets.filter((a) => codes.has(a.code) && a.x !== null && a.y !== null)
      .map((a) => ({ from, to: [a.x as number, a.y as number] as [number, number] }));
  }, [graph, live.assets]);

  const labels = useMemo(() => ({
    sensorOnline: t("map.sensor_online"), sensorOffline: t("map.sensor_offline"), altitude: t("map.altitude"),
  }), [t]);
  const roleLabels = useMemo(() => ({
    physical_event: t("incident.role.physical_event"), entry: t("incident.role.entry"),
    path: t("incident.role.path"), compromised: t("incident.role.compromised"), at_risk: t("incident.role.at_risk"),
  }), [t]);

  const map = (
    <div className="dash__pane" id={MAP_PANEL} data-testid="pane-map">
      <SiteMap site={live.site} sensors={live.sensors} assets={live.assets} tracks={live.tracks}
        trails={live.trails} threatened={live.threatened} layers={LAYERS} theme={theme} labels={labels}
        links={links} />
    </div>
  );
  const topology = (
    <div className="dash__pane" id={GRAPH_PANEL} data-testid="pane-graph">
      {graph ? (
        <TopologyGraph graph={graph} theme={theme} highlight={asset} onSelectNode={setAsset}
          ariaLabel={t("dashboard.graph_label")} roleLabels={roleLabels} />
      ) : (
        <p className="dash__empty" data-testid="no-incident">{t("dashboard.no_incident")}</p>
      )}
    </div>
  );
  const detail = selected ? (
    <IncidentPanel incidentId={selected} tick={live.incidentTick} selectedAsset={asset} onSelectAsset={setAsset} />
  ) : null;

  return (
    <div className="dash">
      <h1 className="sr-only">{term("home.title")}</h1>
      <div className="dash__strip" data-testid="incident-strip" role="group" aria-label={t("dashboard.strip")}>
        <span className={`badge ${live.status === "open" ? "badge--ok" : "badge--warn"}`} data-testid="stream-status">
          {t(`map.stream.${live.status}`)}
        </span>
        {live.threatened.map((z) => (
          <span key={z.zone} className={`badge ${z.severity === "critical" ? "badge--bad" : "badge--warn"}`}
            data-testid={`threat-${z.zone}`}>{z.zone} · {t(`map.severity.${z.severity}`)}</span>
        ))}
        {canIncidents && live.incidents.length === 0 && (
          <span className="field__help" data-testid="no-incidents">{t("dashboard.no_incidents")}</span>
        )}
        {live.incidents.map((i) => (
          <button key={i.id} type="button" data-testid={`incident-chip-${i.code}`}
            className={`incident-chip${i.id === selected ? " is-selected" : ""}`} onClick={() => select(i.id)}
            aria-pressed={i.id === selected}>
            <SeverityBadge value={i.severity} /> <span className="mono">{i.code}</span>{" "}
            {i.zone && <span className="mono">{i.zone}</span>}{" "}
            <span className="field__help">{t(`incident.status.${i.status}`)}</span>
          </button>
        ))}
      </div>

      {live.error && <div className="banner banner--error" role="alert">{live.error}</div>}

      {mode === "tabs" ? (
        <>
          <Tabs label={t("dashboard.views")} active={tab} onChange={setTab} tabs={[
            { id: "map", label: t("dashboard.tab_map"), content: map },
            { id: "graph", label: t("dashboard.tab_graph"), content: topology },
            ...(canIncidents ? [{ id: "incident", label: t("dashboard.tab_incident"),
              content: detail ?? <p className="dash__empty">{t("dashboard.no_incident")}</p> }] : []),
          ]} />
        </>
      ) : (
        <>
          <PanelGroup direction={mode === "wide" ? "horizontal" : "vertical"} className="dash__split"
            autoSaveId={`argus.split.${mode}`}>
            <Panel id={MAP_PANEL} order={1} defaultSize={50} minSize={25}>{map}</Panel>
            <PanelResizeHandle className={`dash__handle dash__handle--${mode}`} aria-label={t("dashboard.splitter")} />
            <Panel id={GRAPH_PANEL} order={2} defaultSize={50} minSize={25}>{topology}</Panel>
          </PanelGroup>
          {detail}
        </>
      )}
    </div>
  );
}
