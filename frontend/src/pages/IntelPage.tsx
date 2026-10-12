import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ApiError, Classification, endpoints, FindingDto, IntelOverview, IntelPolicyDto, IntelSourceDto, Page,
  VulnerabilityDto,
} from "../api/client";
import { Column, DataTable } from "../components/DataTable";
import { Dialog } from "../components/Dialog";
import { CheckboxField, FileField, NumberField, SelectField, TextAreaField, TextField } from "../components/Field";
import { useNotify } from "../components/Notify";
import { SearchFilter } from "../components/SearchFilter";
import { Tabs } from "../components/Tabs";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";
import { TableWrap } from "../components/TableWrap";

function ClassBadge({ value }: { value: Classification }) {
  const { t } = useTranslation();
  const cls = value === "zero_day" ? "badge--bad" : value === "zero_hour" ? "badge--warn" : "";
  return <span className={`badge ${cls}`} data-class={value}>{t(`intel.class.${value}`)}</span>;
}

function SeverityBadge({ value }: { value: string }) {
  const { t } = useTranslation();
  const cls = value === "critical" ? "badge--bad" : value === "high" ? "badge--warn" : "";
  return <span className={`badge ${cls}`}>{t(`intel.severity.${value}`, { defaultValue: value })}</span>;
}

function Problems({ messages }: { messages: string[] }) {
  if (messages.length === 0) return null;
  return (
    <div className="banner banner--error" role="alert">
      <ul>{messages.map((m) => <li key={m}>{m}</li>)}</ul>
    </div>
  );
}

// ---- Findings -----------------------------------------------------------------------------------
function FindingsTab() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const [data, setData] = useState<Page<FindingDto> | null>(null);
  const [overview, setOverview] = useState<IntelOverview | null>(null);
  const [filters, setFilters] = useState({ status: "open", classification: "", severity: "", q: "" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [editing, setEditing] = useState<FindingDto | null>(null);
  const [status, setStatus] = useState("acknowledged");
  const [note, setNote] = useState("");
  const [problems, setProblems] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      setData(await endpoints.findings({ ...filters, page, page_size: pageSize }));
      setOverview(await endpoints.intelOverview());
    } catch {
      /* the banner of the page covers permission errors */
    }
  }, [filters, page, pageSize]);
  useEffect(() => {
    void load();
  }, [load]);

  const set = (patch: Partial<typeof filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };

  const save = async () => {
    if (!editing) return;
    setProblems([]);
    try {
      await endpoints.updateFinding(editing.id, status, note);
      notify.success(t("intel.finding_saved"));
      setEditing(null);
      await load();
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    }
  };

  const columns: Column<FindingDto>[] = [
    { key: "class", header: t("intel.classification"), render: (f) => <ClassBadge value={f.classification} /> },
    { key: "sev", header: t("intel.severity"), render: (f) => <SeverityBadge value={f.vulnerability.severity} /> },
    {
      key: "vuln", header: t("intel.vulnerability"),
      render: (f) => (
        <>
          <span className="mono">{f.vulnerability.vuln_id}</span>
          <br />
          <span className="field__help">{f.vulnerability.title}</span>
        </>
      ),
    },
    {
      key: "asset", header: t("intel.asset"),
      render: (f) => (
        <>
          <span className="mono">{f.asset?.code}</span>
          {f.asset?.zone && <span className="field__help"> · {f.asset.zone}</span>}
        </>
      ),
    },
    {
      key: "match", header: t("intel.matched_on"),
      render: (f) => (
        <>
          {f.matched_on}
          <br />
          <span className="field__help">
            {t(`intel.basis.${f.match_basis}`, { defaultValue: f.match_basis })}
            {f.confidence === "low" && ` · ${t("intel.low_confidence")}`}
          </span>
        </>
      ),
    },
    { key: "fix", header: t("intel.fix"), render: (f) => t(`intel.fix_status.${f.vulnerability.fix_status}`, { defaultValue: f.vulnerability.fix_status }) },
    { key: "status", header: t("intel.status"), render: (f) => <span className="badge">{t(`intel.finding_status.${f.status}`)}</span> },
    {
      key: "actions", header: t("users.actions"),
      render: (f) => can("intel.ack") && (
        <button type="button" className="btn btn--small" onClick={() => { setEditing(f); setStatus(f.status === "open" ? "acknowledged" : f.status); setNote(f.note); }}>
          {t("intel.update")}
        </button>
      ),
    },
  ];

  return (
    <>
      {overview && (
        <div className="toolbar" aria-label={t("intel.overview")}>
          <span className="badge badge--bad" data-testid="count-zero-day">{t("intel.class.zero_day")}: {overview.open_findings.zero_day}</span>
          <span className="badge badge--warn" data-testid="count-zero-hour">{t("intel.class.zero_hour")}: {overview.open_findings.zero_hour}</span>
          <span className="badge">{t("intel.class.ordinary")}: {overview.open_findings.ordinary}</span>
          <span className="field__help">{t("intel.known_vulns", { count: overview.vulnerabilities })}</span>
        </div>
      )}
      <div className="toolbar">
        <SearchFilter value={filters.q} onChange={(q) => set({ q })} label={t("intel.search")} />
        <label>
          <span className="sr-only">{t("intel.classification")}</span>
          <select className="select" value={filters.classification} onChange={(e) => set({ classification: e.target.value })}>
            <option value="">{t("intel.all_classes")}</option>
            {(["zero_day", "zero_hour", "ordinary"] as const).map((c) => <option key={c} value={c}>{t(`intel.class.${c}`)}</option>)}
          </select>
        </label>
        <label>
          <span className="sr-only">{t("intel.status")}</span>
          <select className="select" value={filters.status} onChange={(e) => set({ status: e.target.value })}>
            <option value="">{t("intel.all_statuses")}</option>
            {(["open", "acknowledged", "mitigated", "false_positive"] as const).map((s) => (
              <option key={s} value={s}>{t(`intel.finding_status.${s}`)}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="card">
        <DataTable columns={columns} rows={data?.items ?? []} rowKey={(f) => f.id}
          paging={{ page, pageSize, total: data?.total ?? 0, onChange: (p, s) => { setPage(p); setPageSize(s); } }} />
      </div>
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}
        title={editing ? t("intel.update_title", { id: editing.vulnerability.vuln_id, asset: editing.asset?.code ?? "" }) : ""}
        primary={{ label: t("common.save"), onClick: () => void save() }}>
        <Problems messages={problems} />
        <SelectField label={t("intel.status")} value={status} onChange={(e) => setStatus(e.target.value)}
          options={(["open", "acknowledged", "mitigated", "false_positive"] as const).map((s) => ({ value: s, label: t(`intel.finding_status.${s}`) }))} />
        <TextAreaField label={t("intel.note")} value={note} onChange={(e) => setNote(e.target.value)} />
      </Dialog>
    </>
  );
}

// ---- Vulnerabilities ----------------------------------------------------------------------------
function VulnerabilitiesTab() {
  const { t } = useTranslation();
  const [data, setData] = useState<Page<VulnerabilityDto> | null>(null);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [detail, setDetail] = useState<VulnerabilityDto | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await endpoints.vulnerabilities({ q, page, page_size: pageSize }));
    } catch {
      /* handled by the page banner */
    }
  }, [q, page, pageSize]);
  useEffect(() => {
    void load();
  }, [load]);

  const columns: Column<VulnerabilityDto>[] = [
    {
      key: "id", header: t("intel.vulnerability"),
      render: (v) => (
        <button type="button" className="btn btn--ghost btn--small mono"
          onClick={() => void endpoints.vulnerability(v.vuln_id).then(setDetail)}>{v.vuln_id}</button>
      ),
    },
    { key: "title", header: t("assets.name"), render: (v) => v.title },
    { key: "class", header: t("intel.classification"), render: (v) => <ClassBadge value={v.classification} /> },
    { key: "sev", header: t("intel.severity"), render: (v) => <SeverityBadge value={v.severity} /> },
    { key: "cvss", header: "CVSS", render: (v) => v.cvss ?? "—" },
    { key: "epss", header: "EPSS", render: (v) => (v.epss === null ? "—" : v.epss.toFixed(2)) },
    { key: "kev", header: t("intel.exploited"), render: (v) => (v.kev ? t("common.yes") : "—") },
    { key: "fix", header: t("intel.fix"), render: (v) => t(`intel.fix_status.${v.fix_status}`, { defaultValue: v.fix_status }) },
    { key: "assets", header: t("intel.affected_assets"), render: (v) => v.affected_assets ?? 0 },
  ];

  return (
    <>
      <div className="toolbar">
        <SearchFilter value={q} onChange={(v) => { setQ(v); setPage(1); }} label={t("intel.search_vulns")} />
      </div>
      <div className="card">
        <DataTable columns={columns} rows={data?.items ?? []} rowKey={(v) => v.id}
          paging={{ page, pageSize, total: data?.total ?? 0, onChange: (p, s) => { setPage(p); setPageSize(s); } }} />
      </div>
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)} title={detail?.vuln_id ?? ""}
        description={detail?.title}>
        {detail && (
          <>
            <p>{detail.description}</p>
            <h3>{t("intel.affected_versions")}</h3>
            <ul>
              {(detail.affected ?? []).map((a, i) => (
                <li key={i}>
                  <span className="mono">{a.vendor} {a.product}</span>{" "}
                  <span className="field__help">{JSON.stringify(a.versions)}</span>
                </li>
              ))}
            </ul>
            <h3>{t("intel.affected_assets")}</h3>
            <ul>
              {(detail.findings ?? []).map((f) => (
                <li key={f.id}><span className="mono">{f.asset?.code}</span> · {f.matched_on}</li>
              ))}
              {(detail.findings ?? []).length === 0 && <li>{t("common.empty")}</li>}
            </ul>
          </>
        )}
      </Dialog>
    </>
  );
}

// ---- Sources ------------------------------------------------------------------------------------
function SourcesTab() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const manage = can("intel.sources.manage");
  const [sources, setSources] = useState<IntelSourceDto[]>([]);
  const [importing, setImporting] = useState(false);
  const [format, setFormat] = useState("bundle");
  const [text, setText] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => void endpoints.intelSources().then(setSources).catch(() => undefined), []);
  useEffect(() => load(), [load]);

  const toggle = async (s: IntelSourceDto) => {
    try {
      await endpoints.updateIntelSource(s.key, { enabled: !s.enabled });
      load();
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  };
  const run = async (s: IntelSourceDto) => {
    setBusy(true);
    try {
      const r = await endpoints.runIntelSource(s.key);
      if (r.last_status === "ok") notify.success(t("intel.run_ok", { count: r.report?.created ?? 0 }));
      else notify.error(t("intel.run_failed", { error: r.last_error }));
      load();
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    } finally {
      setBusy(false);
    }
  };
  const doImport = async () => {
    setProblems([]);
    setBusy(true);
    try {
      const payload = JSON.parse(text);
      const r = await endpoints.importIntel(format, payload);
      notify.success(t("intel.import_ok", { created: r.created, updated: r.updated, findings: r.new_findings }));
      setImporting(false);
      setText("");
      load();
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("intel.import_not_json")]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TableWrap card>
        <table className="table">
          <thead>
            <tr>
              <th>{t("assets.name")}</th><th>{t("intel.kind")}</th><th>{t("intel.enabled")}</th>
              <th>{t("intel.last_run")}</th><th>{t("assets.status")}</th><th />
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.key} data-source={s.key}>
                <td>{s.name}<br /><span className="field__help mono">{s.url || "—"}</span></td>
                <td>{s.kind}</td>
                <td>
                  {manage && s.kind !== "bundle" ? (
                    <CheckboxField label={t("intel.enabled")} checked={s.enabled} onChange={() => void toggle(s)} />
                  ) : (s.enabled ? t("common.yes") : "—")}
                </td>
                <td>{s.last_run_at ? new Date(s.last_run_at).toLocaleString() : "—"}</td>
                <td>
                  <span className={`badge ${s.last_status === "ok" ? "badge--ok" : s.last_status === "error" ? "badge--bad" : ""}`}>
                    {t(`intel.source_status.${s.last_status}`, { defaultValue: s.last_status })}
                  </span>
                  {s.last_error && <span className="field__help"> {s.last_error}</span>}
                </td>
                <td>
                  {manage && s.url && s.kind !== "bundle" && (
                    <button type="button" className="btn btn--small" disabled={busy} onClick={() => void run(s)}>{t("intel.run_now")}</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      {manage && (
        <button type="button" className="btn btn--primary" onClick={() => setImporting(true)}>{t("intel.import")}</button>
      )}
      <Dialog open={importing} onOpenChange={setImporting} title={t("intel.import")}
        primary={{ label: t("intel.import_submit"), onClick: () => void doImport(), busy, disabled: !text.trim() }}>
        <Problems messages={problems} />
        <SelectField label={t("intel.format")} value={format} onChange={(e) => setFormat(e.target.value)}
          options={["bundle", "kev", "nvd", "epss", "csaf", "records"].map((f) => ({ value: f, label: t(`intel.format.${f}`) }))} />
        <FileField label={t("intel.file")} accept=".json,application/json"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void f.text().then(setText); }} />
        <TextAreaField label={t("intel.content")} value={text} onChange={(e) => setText(e.target.value)} />
      </Dialog>
    </>
  );
}

// ---- Policy and trust ---------------------------------------------------------------------------
function PolicyTab() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const manage = can("intel.sources.manage");
  const [policy, setPolicy] = useState<IntelPolicyDto | null>(null);
  const [keys, setKeys] = useState<{ key_id: string; public_key: string; label: string }[]>([]);
  const [newKey, setNewKey] = useState({ key_id: "", public_key: "", label: "" });
  const [problems, setProblems] = useState<string[]>([]);

  useEffect(() => {
    void endpoints.intelPolicy().then(setPolicy).catch(() => undefined);
    if (manage) void endpoints.trustedKeys().then(setKeys).catch(() => undefined);
  }, [manage]);

  if (!policy) return <p>{t("common.loading")}</p>;
  const savePolicy = async () => {
    setProblems([]);
    try {
      setPolicy(await endpoints.putIntelPolicy(policy));
      notify.success(t("settings.saved"));
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    }
  };
  const saveKeys = async (next: typeof keys) => {
    try {
      setKeys(await endpoints.putTrustedKeys(next));
      setNewKey({ key_id: "", public_key: "", label: "" });
      notify.success(t("settings.saved"));
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  };

  return (
    <>
      <form className="card" onSubmit={(e) => { e.preventDefault(); void savePolicy(); }}>
        <h2>{t("intel.policy")}</h2>
        <Problems messages={problems} />
        <div className="grid-2">
          <NumberField label={t("intel.zero_hour_hours")} help={t("intel.zero_hour_help")} value={policy.zero_hour_hours}
            disabled={!manage} onChange={(e) => setPolicy({ ...policy, zero_hour_hours: Number(e.target.value) })} />
          <NumberField label={t("intel.epss_threshold")} help={t("intel.epss_help")} value={policy.epss_threshold} step="0.05"
            disabled={!manage} onChange={(e) => setPolicy({ ...policy, epss_threshold: Number(e.target.value) })} />
          <SelectField label={t("intel.notify_min")} value={policy.notify_min_severity} disabled={!manage}
            onChange={(e) => setPolicy({ ...policy, notify_min_severity: e.target.value })}
            options={["low", "medium", "high", "critical"].map((s) => ({ value: s, label: t(`intel.severity.${s}`) }))} />
        </div>
        <CheckboxField label={t("intel.notify")} checked={policy.notify} disabled={!manage}
          onChange={(e) => setPolicy({ ...policy, notify: e.target.checked })} />
        <CheckboxField label={t("intel.offline_only")} help={t("intel.offline_help")} checked={policy.offline_only}
          disabled={!manage} onChange={(e) => setPolicy({ ...policy, offline_only: e.target.checked })} />
        {manage && <button type="submit" className="btn btn--primary">{t("common.save")}</button>}
      </form>

      {manage && (
        <section className="card" aria-label={t("intel.trusted_keys")}>
          <h2>{t("intel.trusted_keys")}</h2>
          <p className="field__help">{t("intel.trusted_help")}</p>
          <ul>
            {keys.map((k) => (
              <li key={k.key_id}>
                <span className="mono">{k.key_id}</span> {k.label && `· ${k.label}`}{" "}
                <button type="button" className="btn btn--danger btn--small"
                  onClick={() => void saveKeys(keys.filter((x) => x.key_id !== k.key_id))}>{t("common.remove")}</button>
              </li>
            ))}
            {keys.length === 0 && <li>{t("common.empty")}</li>}
          </ul>
          <div className="grid-2">
            <TextField label={t("intel.key_id")} value={newKey.key_id} onChange={(e) => setNewKey({ ...newKey, key_id: e.target.value })} />
            <TextField label={t("intel.key_label")} value={newKey.label} onChange={(e) => setNewKey({ ...newKey, label: e.target.value })} />
          </div>
          <TextField label={t("intel.public_key")} value={newKey.public_key}
            onChange={(e) => setNewKey({ ...newKey, public_key: e.target.value })} />
          <button type="button" className="btn" disabled={!newKey.key_id || !newKey.public_key}
            onClick={() => void saveKeys([...keys, newKey])}>{t("intel.add_key")}</button>
        </section>
      )}
    </>
  );
}

export function IntelPage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [tab, setTab] = useState("findings");
  return (
    <>
      <h1>{t("nav.intel")}</h1>
      <Tabs
        label={t("nav.intel")}
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "findings", label: t("intel.tab_findings"), content: <FindingsTab /> },
          { id: "vulnerabilities", label: t("intel.tab_vulnerabilities"), content: <VulnerabilitiesTab /> },
          { id: "sources", label: t("intel.tab_sources"), content: <SourcesTab /> },
          ...(can("intel.view") ? [{ id: "policy", label: t("intel.tab_policy"), content: <PolicyTab /> }] : []),
        ]}
      />
    </>
  );
}
