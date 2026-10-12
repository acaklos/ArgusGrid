import type { TFunction } from "i18next";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, endpoints, IncidentDto } from "../api/client";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";
import { Dialog } from "./Dialog";
import { incidentTitle } from "./incidentTitle";
import { TextAreaField } from "./Field";
import { useNotify } from "./Notify";

export function SeverityBadge({ value }: { value: string }) {
  const { t } = useTranslation();
  const cls = value === "critical" ? "badge--bad" : value === "high" || value === "medium" ? "badge--warn" : "";
  return <span className={`badge ${cls}`} data-severity={value}>{t(`incident.severity.${value}`)}</span>;
}

/** System entries are written in English for the log; the screen shows them in the user language. */
function eventText(t: TFunction, e: { kind: string; text: string }, incident: IncidentDto): string {
  if (e.kind === "created") return incidentTitle(t, incident);
  if (e.kind === "update" || e.kind === "notified") return t(`incident.event_text.${e.kind}`);
  return e.text;
}

type Action = { kind: "status"; status: string } | { kind: "escalate" } | { kind: "note" };

interface Props {
  incidentId: number;
  /** changes when the stream reports an incident change, the panel reloads the detail */
  tick: number;
  selectedAsset?: string | null;
  onSelectAsset?: (code: string | null) => void;
  onChanged?: (incident: IncidentDto) => void;
}

/** Detail and workflow of one incident; shared by the dashboard and the incident page. */
export function IncidentPanel({ incidentId, tick, selectedAsset, onSelectAsset, onChanged }: Props) {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const [incident, setIncident] = useState<IncidentDto | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [text, setText] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setIncident(await endpoints.incident(incidentId));
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    }
  }, [incidentId, t]);
  useEffect(() => {
    void load();
  }, [load, tick]);

  const close = () => {
    setAction(null);
    setText("");
    setProblems([]);
  };

  const submit = async () => {
    if (!action || !incident) return;
    setBusy(true);
    try {
      const updated = action.kind === "status"
        ? await endpoints.setIncidentStatus(incident.id, action.status, text)
        : action.kind === "escalate"
          ? await endpoints.escalateIncident(incident.id, text)
          : await endpoints.noteIncident(incident.id, text);
      setIncident(updated);
      onChanged?.(updated);
      notify.success(t("incident.saved"));
      close();
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  if (!incident) {
    return <div className="card" aria-busy="true">{problems[0] ?? t("common.loading")}</div>;
  }
  const physical = incident.evidence?.physical ?? null;
  const cyber = incident.evidence?.cyber;
  const canTriage = can("incident.triage");
  const allowed = (incident.transitions ?? []).filter((s) =>
    s === "closed" ? can("incident.close") : canTriage);
  const titleKey = action?.kind === "status" ? `incident.status.${action.status}` : action?.kind === "escalate"
    ? "incident.escalate" : "incident.add_note";

  return (
    <section className="card incident" aria-label={incident.code} data-testid="incident-panel"
      data-incident={incident.code}>
      <header className="incident__head">
        <h2><span className="mono">{incident.code}</span> {incidentTitle(t, incident)}</h2>
        <p>
          <SeverityBadge value={incident.severity} />{" "}
          <span className="badge" data-testid="incident-status">{t(`incident.status.${incident.status}`)}</span>{" "}
          <span className="badge">{t(`incident.type.${incident.type}`)}</span>{" "}
          {incident.escalated && <span className="badge badge--bad">{t("incident.escalated")}</span>}{" "}
          <span data-testid="incident-score">{t("incident.score", { score: Math.round(incident.score) })}</span>
        </p>
      </header>

      <div className="toolbar">
        {allowed.map((s) => (
          <button key={s} type="button" className="btn" onClick={() => setAction({ kind: "status", status: s })}
            data-testid={`incident-to-${s}`}>
            {t(`incident.action.${s}`)}
          </button>
        ))}
        {can("incident.escalate") && incident.status !== "closed" && !incident.escalated && (
          <button type="button" className="btn btn--danger" onClick={() => setAction({ kind: "escalate" })}
            data-testid="incident-escalate">{t("incident.escalate")}</button>
        )}
        {canTriage && (
          <button type="button" className="btn btn--ghost" onClick={() => setAction({ kind: "note" })}>
            {t("incident.add_note")}
          </button>
        )}
      </div>

      {physical && (
        <div className="incident__block">
          <h3>{t("incident.physical")}</h3>
          <p>
            <span className="mono">{physical.track.id}</span> · {physical.track.zone ?? "—"} ·{" "}
            {t(`map.ring.${physical.track.ring}`, { defaultValue: physical.track.ring })}
            {physical.track.altitude !== null && ` · ${Math.round(physical.track.altitude)} m`}
          </p>
          {physical.link && (
            <p>
              {physical.link.kind === "zone"
                ? t("incident.link.zone")
                : t("incident.link.proximity", {
                  asset: physical.link.exposed_asset, exposure: t(`incident.exposure.${physical.link.exposure}`,
                    { defaultValue: physical.link.exposure ?? "" }),
                  distance: Math.round(physical.link.distance_m),
                })}
            </p>
          )}
        </div>
      )}

      {cyber && (cyber.alarms.length > 0 || cyber.findings.length > 0) && (
        <div className="incident__block">
          <h3>{t("incident.cyber")}</h3>
          <ul>
            {cyber.alarms.slice(0, 4).map((a, i) => <li key={`a${i}`}>{a.summary}</li>)}
            {cyber.findings.map((f) => (
              <li key={f.vuln_id}>
                <span className="mono">{f.vuln_id}</span> · {f.title} ·{" "}
                <span className="badge badge--bad">{t(`intel.class.${f.classification}`, { defaultValue: f.classification })}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(incident.blast_radius?.length ?? 0) > 0 && (
        <div className="incident__block">
          <h3>{t("incident.blast")}</h3>
          <ol className="blast" data-testid="blast-radius">
            {incident.blast_radius!.slice(0, 12).map((b) => (
              <li key={b.asset}>
                <button type="button" className={`linklike${selectedAsset === b.asset ? " is-selected" : ""}`}
                  onClick={() => onSelectAsset?.(selectedAsset === b.asset ? null : b.asset)}>
                  <span className="mono">{b.asset}</span>
                </button>{" "}
                <span className="field__help">
                  {t("incident.hop", { hop: b.hop })} · {t(`incident.impact.${b.impact}`)} ·{" "}
                  {t(`intel.severity.${b.criticality}`, { defaultValue: b.criticality })}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {(incident.recommendations?.length ?? 0) > 0 && (
        <div className="incident__block">
          <h3>{t("incident.recommendations")}</h3>
          <p className="field__help">{t("incident.recommendations_note")}</p>
          <ul data-testid="recommendations">
            {incident.recommendations!.map((r, i) => (
              <li key={`${r.code}-${i}`} data-code={r.code}>
                {t(`incident.rec.${r.code}`, {
                  asset: r.asset ?? "", assets: (r.assets ?? []).join(", "), zone: r.zone ?? "",
                  defaultValue: r.code,
                })}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="incident__block">
        <h3>{t("incident.timeline")}</h3>
        <ul className="timeline">
          {(incident.timeline ?? []).map((e, i) => (
            <li key={i}>
              <span className="field__help">{new Date(e.ts).toLocaleString()} · {e.actor}</span>{" "}
              <span className="badge">{t(`incident.event.${e.kind}`, { defaultValue: e.kind })}</span> {eventText(t, e, incident)}
            </li>
          ))}
        </ul>
      </div>

      <Dialog open={action !== null} onOpenChange={(o) => !o && close()} title={action ? t(titleKey) : ""}
        primary={{ label: t("common.save"), onClick: () => void submit(), busy }}>
        {problems.length > 0 && (
          <div className="banner banner--error" role="alert">
            <ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        )}
        <TextAreaField label={t("incident.note")} value={text} maxLength={action?.kind === "status" ? 500 : 1000}
          onChange={(e) => setText(e.target.value)} rows={4} />
      </Dialog>
    </section>
  );
}
