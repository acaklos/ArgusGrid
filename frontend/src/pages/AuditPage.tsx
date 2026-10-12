import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, AuditFilters, AuditRow, endpoints, Page } from "../api/client";
import { Column, DataTable } from "../components/DataTable";
import { DateTimeField } from "../components/Field";
import { useNotify } from "../components/Notify";
import { SearchFilter } from "../components/SearchFilter";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function Changes({ row }: { row: AuditRow }) {
  const { t } = useTranslation();
  const entries = Object.entries(row.changes ?? {});
  if (entries.length === 0) return <span className="field__help">—</span>;
  return (
    <dl className="kv" aria-label={t("audit.changes")}>
      {entries.map(([field, change]) => (
        <div key={field} style={{ display: "contents" }}>
          <dt className="mono">{field}</dt>
          <dd style={{ margin: 0 }}>
            <span className="badge">{formatValue(change.old)}</span> → <span className="badge badge--ok">{formatValue(change.new)}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function AuditPage() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const [data, setData] = useState<Page<AuditRow> | null>(null);
  const [filters, setFilters] = useState<AuditFilters>({});
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await endpoints.listAudit({ ...filters, page, page_size: pageSize }));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  }, [filters, page, pageSize, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const set = (patch: AuditFilters) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };

  const verify = async () => {
    try {
      const r = await endpoints.verifyAudit();
      if (r.intact) notify.success(t("audit.chain_ok"));
      else notify.error(t("audit.chain_broken"));
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  };

  const columns: Column<AuditRow>[] = [
    { key: "ts", header: t("audit.when"), render: (r) => <span className="mono">{new Date(r.ts).toLocaleString()}</span> },
    { key: "actor", header: t("audit.who"), render: (r) => r.actor || "—" },
    { key: "action", header: t("audit.what"), render: (r) => <span className="mono">{r.action}</span> },
    {
      key: "object", header: t("audit.object"),
      render: (r) => (r.object_type ? `${r.object_type}${r.object_id ? ` #${r.object_id}` : ""}` : "—"),
    },
    {
      key: "how", header: t("audit.how"),
      render: (r) => (
        <>
          {r.channel}
          {r.source_ip && <span className="field__help"> · {r.source_ip}</span>}
        </>
      ),
    },
    {
      key: "result", header: t("audit.result"),
      render: (r) => <span className={`badge ${r.result === "success" ? "badge--ok" : r.result === "failure" ? "badge--bad" : "badge--warn"}`}>{r.result}</span>,
    },
    { key: "changes", header: t("audit.changes"), render: (r) => <Changes row={r} /> },
  ];

  return (
    <>
      <h1>{t("nav.audit")}</h1>
      {error && <div className="banner banner--error" role="alert">{error}</div>}
      <div className="toolbar">
        <SearchFilter value={filters.q ?? ""} onChange={(q) => set({ q })} label={t("audit.search")} />
        <label>
          <span className="sr-only">{t("audit.result")}</span>
          <select className="select" value={filters.result ?? ""} onChange={(e) => set({ result: e.target.value })}>
            <option value="">{t("audit.all_results")}</option>
            <option value="success">success</option>
            <option value="failure">failure</option>
            <option value="info">info</option>
          </select>
        </label>
        <label>
          <span className="sr-only">{t("audit.action_prefix")}</span>
          <select className="select" value={filters.action ?? ""} onChange={(e) => set({ action: e.target.value })}>
            <option value="">{t("audit.all_actions")}</option>
            {["auth.", "user.", "role.", "policy.", "settings.", "audit."].map((p) => (
              <option key={p} value={p}>{p}*</option>
            ))}
          </select>
        </label>
        <DateTimeField label={t("audit.from")}
          onChange={(e) => set({ date_from: e.target.value ? new Date(e.target.value).toISOString() : "" })} />
        <DateTimeField label={t("audit.to")}
          onChange={(e) => set({ date_to: e.target.value ? new Date(e.target.value).toISOString() : "" })} />
        <button type="button" className="btn" onClick={() => void verify()}>{t("audit.verify")}</button>
        {can("audit.export") && (
          <a className="btn" href={endpoints.auditExportUrl(filters)} download>{t("audit.export")}</a>
        )}
      </div>
      <div className="card">
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(r) => r.id}
          paging={{ page, pageSize, total: data?.total ?? 0, onChange: (p, s) => { setPage(p); setPageSize(s); } }}
        />
      </div>
    </>
  );
}
