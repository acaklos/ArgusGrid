import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, endpoints, IncidentDto, Page } from "../api/client";
import { Column, DataTable } from "../components/DataTable";
import { SelectField } from "../components/Field";
import { IncidentPanel, SeverityBadge } from "../components/IncidentPanel";
import { incidentTitle } from "../components/incidentTitle";
import { errorMessages } from "../i18n/errors";
import { useStream } from "../state/useStream";

/** All incidents with filters; the detail and workflow are the same panel the dashboard uses. */
export function IncidentsPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<Page<IncidentDto> | null>(null);
  const [filters, setFilters] = useState({ status: "", severity: "", type: "" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [tick, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const selected = Number(params.get("incident")) || null;

  const load = useCallback(async () => {
    try {
      setData(await endpoints.incidents({ ...filters, page, page_size: pageSize }));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  }, [filters, page, pageSize, t]);
  useEffect(() => {
    void load();
  }, [load, tick]);

  useStream(useCallback((m: { type: string }) => {
    if (m.type === "incident") setTick((n) => n + 1);
  }, []));

  const columns: Column<IncidentDto>[] = [
    { key: "code", header: t("incident.col.code"), render: (i) => (
      <button type="button" className="linklike mono" onClick={() => setParams({ incident: String(i.id) })}>
        {i.code}
      </button>) },
    { key: "title", header: t("incident.col.title"), render: (i) => incidentTitle(t, i) },
    { key: "severity", header: t("incident.col.severity"), render: (i) => <SeverityBadge value={i.severity} /> },
    { key: "status", header: t("incident.col.status"), render: (i) => t(`incident.status.${i.status}`) },
    { key: "type", header: t("incident.col.type"), render: (i) => t(`incident.type.${i.type}`) },
    { key: "zone", header: t("incident.col.zone"), render: (i) => i.zone ?? "—" },
    { key: "asset", header: t("incident.col.asset"), render: (i) => <span className="mono">{i.primary_asset ?? "—"}</span> },
    { key: "score", header: t("incident.col.score"), render: (i) => Math.round(i.score) },
    { key: "updated", header: t("incident.col.updated"), render: (i) => new Date(i.updated_at).toLocaleString() },
    { key: "open", header: "", render: (i) => <Link to={`/?incident=${i.id}`}>{t("incident.open_dashboard")}</Link> },
  ];

  const options = (prefix: string, values: string[]) => [
    { value: "", label: t("common.all") },
    ...values.map((v) => ({ value: v, label: t(`${prefix}.${v}`) })),
  ];

  return (
    <>
      <h1>{t("nav.incidents")}</h1>
      {error && <div className="banner banner--error" role="alert">{error}</div>}
      <div className="toolbar">
        <SelectField label={t("incident.col.status")} value={filters.status}
          options={options("incident.status", ["new", "triaged", "investigating", "contained", "closed"])}
          onChange={(e) => { setFilters({ ...filters, status: e.target.value }); setPage(1); }} />
        <SelectField label={t("incident.col.severity")} value={filters.severity}
          options={options("incident.severity", ["critical", "high", "medium", "low"])}
          onChange={(e) => { setFilters({ ...filters, severity: e.target.value }); setPage(1); }} />
        <SelectField label={t("incident.col.type")} value={filters.type}
          options={options("incident.type", ["hybrid", "physical", "cyber"])}
          onChange={(e) => { setFilters({ ...filters, type: e.target.value }); setPage(1); }} />
      </div>
      <div className="card">
        <DataTable columns={columns} rows={data?.items ?? []} rowKey={(i) => i.id} emptyText={t("incident.none")}
          rowClassName={(i) => (i.id === selected ? "is-selected" : undefined)}
          paging={{ page, pageSize, total: data?.total ?? 0, onChange: (p, s) => { setPage(p); setPageSize(s); } }} />
      </div>
      {selected && (
        <IncidentPanel incidentId={selected} tick={tick} onChanged={() => setTick((n) => n + 1)} />
      )}
    </>
  );
}
