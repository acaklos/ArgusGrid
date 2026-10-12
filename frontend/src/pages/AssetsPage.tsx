import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { ApiError, AssetDto, AssetVocabulary, endpoints, Page, ZoneDto } from "../api/client";
import { Column, DataTable } from "../components/DataTable";
import { Dialog } from "../components/Dialog";
import { CheckboxField, SelectField, TextField } from "../components/Field";
import { useNotify } from "../components/Notify";
import { SearchFilter } from "../components/SearchFilter";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";

function CriticalityBadge({ value }: { value: string }) {
  const { t } = useTranslation();
  const cls = value === "critical" ? "badge--bad" : value === "high" ? "badge--warn" : "";
  return <span className={`badge ${cls}`}>{t(`assets.criticality.${value}`, { defaultValue: value })}</span>;
}

function CreateAssetDialog({ open, vocab, zones, onClose, onCreated }: {
  open: boolean; vocab: AssetVocabulary | null; zones: ZoneDto[]; onClose: () => void; onCreated: (a: AssetDto) => void;
}) {
  const { t } = useTranslation();
  const notify = useNotify();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState("server");
  const [level, setLevel] = useState("");
  const [zone, setZone] = useState("");
  const [criticality, setCriticality] = useState("medium");
  const [ip, setIp] = useState("");
  const [exposure, setExposure] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const submit = async () => {
    setBusy(true);
    setErrors([]);
    try {
      const created = await endpoints.createAsset({
        code, name, asset_type: type, purdue_level: level, zone: zone || null, criticality, ip_address: ip, exposure,
      });
      notify.success(t("assets.created", { code: created.code }));
      onCreated(created);
      onClose();
    } catch (e) {
      setErrors(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()} title={t("assets.create")}
      primary={{ label: t("assets.create_submit"), onClick: () => void submit(), busy, disabled: !code || !name }}>
      {errors.length > 0 && (
        <div className="banner banner--error" role="alert">
          <ul>{errors.map((m) => <li key={m}>{m}</li>)}</ul>
        </div>
      )}
      <div className="grid-2">
        <TextField label={t("assets.code")} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" />
        <TextField label={t("assets.name")} value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
        <SelectField label={t("assets.type")} value={type} onChange={(e) => setType(e.target.value)}
          options={Object.keys(vocab?.types ?? {}).map((x) => ({ value: x, label: t(`assets.type.${x}`, { defaultValue: x }) }))} />
        <SelectField label={t("assets.level")} value={level} onChange={(e) => setLevel(e.target.value)}
          options={[{ value: "", label: "—" }, ...(vocab?.levels ?? []).map((l) => ({ value: l, label: l }))]} />
        <SelectField label={t("assets.zone")} value={zone} onChange={(e) => setZone(e.target.value)}
          options={[{ value: "", label: "—" }, ...zones.map((z) => ({ value: z.code, label: `${z.code} ${z.name}` }))]} />
        <SelectField label={t("assets.criticality")} value={criticality} onChange={(e) => setCriticality(e.target.value)}
          options={(vocab?.criticality ?? []).map((c) => ({ value: c, label: t(`assets.criticality.${c}`, { defaultValue: c }) }))} />
      </div>
      <TextField label={t("assets.ip")} value={ip} onChange={(e) => setIp(e.target.value)} autoComplete="off" />
      <fieldset className="field" style={{ border: 0, padding: 0 }}>
        <legend className="field__label">{t("assets.exposure")}</legend>
        <div className="caps">
          {(vocab?.exposure ?? []).map((x) => (
            <CheckboxField key={x} label={t(`assets.exposure.${x}`, { defaultValue: x })} checked={exposure.includes(x)}
              onChange={(e) => setExposure(e.target.checked ? [...exposure, x] : exposure.filter((v) => v !== x))} />
          ))}
        </div>
      </fieldset>
    </Dialog>
  );
}

export function AssetsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { can } = useSession();
  const [data, setData] = useState<Page<AssetDto> | null>(null);
  const [vocab, setVocab] = useState<AssetVocabulary | null>(null);
  const [zones, setZones] = useState<ZoneDto[]>([]);
  const [filters, setFilters] = useState({ search: "", asset_type: "", zone: "", status: "", level: "" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await endpoints.listAssets({ ...filters, page, page_size: pageSize }));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  }, [filters, page, pageSize, t]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    void endpoints.vocabulary().then(setVocab).catch(() => undefined);
    void endpoints.zones().then(setZones).catch(() => undefined);
  }, []);

  const set = (patch: Partial<typeof filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };

  const columns: Column<AssetDto>[] = [
    {
      key: "code", header: t("assets.code"),
      render: (a) => (
        <button type="button" className="btn btn--ghost btn--small mono" onClick={() => navigate(`/assets/${a.id}`)}>
          {a.code}
        </button>
      ),
    },
    { key: "name", header: t("assets.name"), render: (a) => a.name },
    { key: "type", header: t("assets.type"), render: (a) => t(`assets.type.${a.asset_type}`, { defaultValue: a.asset_type }) },
    { key: "level", header: t("assets.level"), render: (a) => a.purdue_level || "—" },
    { key: "zone", header: t("assets.zone"), render: (a) => a.zone ?? "—" },
    { key: "crit", header: t("assets.criticality"), render: (a) => <CriticalityBadge value={a.criticality} /> },
    {
      key: "status", header: t("assets.status"),
      render: (a) => <span className="badge">{t(`assets.status.${a.status}`, { defaultValue: a.status })}</span>,
    },
    { key: "ip", header: t("assets.ip"), render: (a) => <span className="mono">{a.ip_address || "—"}</span> },
  ];

  return (
    <>
      <h1>{t("nav.assets")}</h1>
      {error && <div className="banner banner--error" role="alert">{error}</div>}
      <div className="toolbar">
        <SearchFilter value={filters.search} onChange={(search) => set({ search })} label={t("assets.search")} />
        <label>
          <span className="sr-only">{t("assets.type")}</span>
          <select className="select" value={filters.asset_type} onChange={(e) => set({ asset_type: e.target.value })}>
            <option value="">{t("assets.all_types")}</option>
            {Object.keys(vocab?.types ?? {}).map((x) => (
              <option key={x} value={x}>{t(`assets.type.${x}`, { defaultValue: x })}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">{t("assets.zone")}</span>
          <select className="select" value={filters.zone} onChange={(e) => set({ zone: e.target.value })}>
            <option value="">{t("assets.all_zones")}</option>
            {zones.map((z) => (
              <option key={z.code} value={z.code}>{`${z.code} ${z.name}`}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">{t("assets.status")}</span>
          <select className="select" value={filters.status} onChange={(e) => set({ status: e.target.value })}>
            <option value="">{t("assets.all_statuses")}</option>
            {(vocab?.statuses ?? []).map((x) => (
              <option key={x} value={x}>{t(`assets.status.${x}`, { defaultValue: x })}</option>
            ))}
          </select>
        </label>
        {can("asset.create") && (
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>{t("assets.create")}</button>
        )}
      </div>
      <div className="card">
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(a) => a.id}
          rowClassName={(a) => (a.status === "decommissioned" ? "row--muted" : undefined)}
          paging={{ page, pageSize, total: data?.total ?? 0, onChange: (p, s) => { setPage(p); setPageSize(s); } }}
        />
      </div>
      <CreateAssetDialog open={creating} vocab={vocab} zones={zones} onClose={() => setCreating(false)}
        onCreated={(a) => navigate(`/assets/${a.id}`)} />
    </>
  );
}
