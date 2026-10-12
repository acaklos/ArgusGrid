import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, AssetDto, AssetVocabulary, CredentialDto, endpoints, RelationDto, ZoneDto } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Dialog } from "../components/Dialog";
import { CheckboxField, NumberField, SelectField, TextAreaField, TextField } from "../components/Field";
import { useNotify } from "../components/Notify";
import { Tabs } from "../components/Tabs";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";
import { TableWrap } from "../components/TableWrap";

function Problems({ messages }: { messages: string[] }) {
  if (messages.length === 0) return null;
  return (
    <div className="banner banner--error" role="alert">
      <ul>{messages.map((m) => <li key={m}>{m}</li>)}</ul>
    </div>
  );
}

// ---- Overview -----------------------------------------------------------------------------------
function Overview({ asset, vocab, zones, onSaved }: {
  asset: AssetDto; vocab: AssetVocabulary; zones: ZoneDto[]; onSaved: (a: AssetDto) => void;
}) {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("asset.edit");
  const [form, setForm] = useState({ ...asset, x: asset.x ?? "", y: asset.y ?? "" } as Record<string, unknown>);
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => setForm({ ...asset, x: asset.x ?? "", y: asset.y ?? "" } as Record<string, unknown>), [asset]);

  const set = (key: string, value: unknown) => setForm((f) => ({ ...f, [key]: value }));
  const allowed = vocab.transitions[asset.status] ?? [asset.status];

  const save = async () => {
    setBusy(true);
    setProblems([]);
    try {
      const body: Record<string, unknown> = {};
      for (const k of ["name", "asset_type", "purdue_level", "location", "criticality", "status", "vendor", "model",
        "firmware_version", "ip_address", "mac_address", "notes", "exposure", "protocols"]) body[k] = form[k];
      body.zone = form.zone || null;
      body.x = form.x === "" ? null : Number(form.x);
      body.y = form.y === "" ? null : Number(form.y);
      onSaved(await endpoints.updateAsset(asset.id, body));
      notify.success(t("assets.saved"));
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  const exposure = (form.exposure as string[]) ?? [];
  return (
    <form className="card" onSubmit={(e) => { e.preventDefault(); void save(); }}>
      <Problems messages={problems} />
      <div className="grid-2">
        <TextField label={t("assets.code")} value={asset.code} disabled readOnly />
        <TextField label={t("assets.name")} value={String(form.name ?? "")} disabled={!editable}
          onChange={(e) => set("name", e.target.value)} />
        <SelectField label={t("assets.type")} value={String(form.asset_type)} disabled={!editable}
          onChange={(e) => set("asset_type", e.target.value)}
          options={Object.keys(vocab.types).map((x) => ({ value: x, label: t(`assets.type.${x}`, { defaultValue: x }) }))} />
        <SelectField label={t("assets.status")} value={String(form.status)} disabled={!editable}
          onChange={(e) => set("status", e.target.value)}
          options={allowed.map((x) => ({ value: x, label: t(`assets.status.${x}`, { defaultValue: x }) }))} />
        <SelectField label={t("assets.level")} value={String(form.purdue_level ?? "")} disabled={!editable}
          onChange={(e) => set("purdue_level", e.target.value)}
          options={[{ value: "", label: "—" }, ...vocab.levels.map((l) => ({ value: l, label: l }))]} />
        <SelectField label={t("assets.zone")} value={String(form.zone ?? "")} disabled={!editable}
          onChange={(e) => set("zone", e.target.value)}
          options={[{ value: "", label: "—" }, ...zones.map((z) => ({ value: z.code, label: `${z.code} ${z.name}` }))]} />
        <SelectField label={t("assets.criticality")} value={String(form.criticality)} disabled={!editable}
          onChange={(e) => set("criticality", e.target.value)}
          options={vocab.criticality.map((c) => ({ value: c, label: t(`assets.criticality.${c}`, { defaultValue: c }) }))} />
        <TextField label={t("assets.location")} value={String(form.location ?? "")} disabled={!editable}
          onChange={(e) => set("location", e.target.value)} />
        <TextField label={t("assets.vendor")} value={String(form.vendor ?? "")} disabled={!editable}
          onChange={(e) => set("vendor", e.target.value)} />
        <TextField label={t("assets.model")} value={String(form.model ?? "")} disabled={!editable}
          onChange={(e) => set("model", e.target.value)} />
        <TextField label={t("assets.firmware")} value={String(form.firmware_version ?? "")} disabled={!editable}
          onChange={(e) => set("firmware_version", e.target.value)} />
        <TextField label={t("assets.ip")} value={String(form.ip_address ?? "")} disabled={!editable}
          onChange={(e) => set("ip_address", e.target.value)} />
        <TextField label={t("assets.mac")} value={String(form.mac_address ?? "")} disabled={!editable}
          onChange={(e) => set("mac_address", e.target.value)} />
        <TextField label={t("assets.protocols")} help={t("assets.protocols_help")}
          value={((form.protocols as string[]) ?? []).join(", ")} disabled={!editable}
          onChange={(e) => set("protocols", e.target.value.split(",").map((p) => p.trim()).filter(Boolean))} />
        <NumberField label="X (m)" value={String(form.x ?? "")} disabled={!editable}
          onChange={(e) => set("x", e.target.value)} />
        <NumberField label="Y (m)" value={String(form.y ?? "")} disabled={!editable}
          onChange={(e) => set("y", e.target.value)} />
      </div>
      <fieldset className="field" style={{ border: 0, padding: 0 }}>
        <legend className="field__label">{t("assets.exposure")}</legend>
        <p className="field__help">{t("assets.exposure_help")}</p>
        <div className="caps">
          {vocab.exposure.map((x) => (
            <CheckboxField key={x} label={t(`assets.exposure.${x}`, { defaultValue: x })} checked={exposure.includes(x)}
              disabled={!editable}
              onChange={(e) => set("exposure", e.target.checked ? [...exposure, x] : exposure.filter((v) => v !== x))} />
          ))}
        </div>
      </fieldset>
      <TextAreaField label={t("assets.notes")} value={String(form.notes ?? "")} disabled={!editable}
        onChange={(e) => set("notes", e.target.value)} />
      {editable && (
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? t("common.working") : t("common.save")}
        </button>
      )}
    </form>
  );
}

// ---- Software -----------------------------------------------------------------------------------
function SoftwareTab({ asset, onSaved }: { asset: AssetDto; onSaved: (a: AssetDto) => void }) {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("asset.edit");
  const [items, setItems] = useState(asset.software ?? []);
  const [problems, setProblems] = useState<string[]>([]);
  useEffect(() => setItems(asset.software ?? []), [asset]);

  const change = (i: number, key: string, value: string) =>
    setItems((cur) => cur.map((it, idx) => (idx === i ? { ...it, [key]: value } : it)));

  const save = async () => {
    setProblems([]);
    try {
      onSaved(await endpoints.setSoftware(asset.id, items));
      notify.success(t("assets.saved"));
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    }
  };

  return (
    <section className="card">
      <p className="field__help">{t("assets.software_help")}</p>
      <Problems messages={problems} />
      {items.length === 0 && <p>{t("common.empty")}</p>}
      {items.map((it, i) => (
        <div key={i} className="grid-2" style={{ gridTemplateColumns: "2fr 1.5fr 1fr 2fr auto", alignItems: "end" }}>
          <TextField label={t("assets.software_name")} value={it.name} disabled={!editable}
            onChange={(e) => change(i, "name", e.target.value)} />
          <TextField label={t("assets.vendor")} value={it.vendor} disabled={!editable}
            onChange={(e) => change(i, "vendor", e.target.value)} />
          <TextField label={t("assets.software_version")} value={it.version} disabled={!editable}
            onChange={(e) => change(i, "version", e.target.value)} />
          <TextField label="CPE" value={it.cpe} disabled={!editable} onChange={(e) => change(i, "cpe", e.target.value)} />
          {editable && (
            <div className="field">
              <button type="button" className="btn btn--danger btn--small"
                onClick={() => setItems(items.filter((_, idx) => idx !== i))}>{t("common.remove")}</button>
            </div>
          )}
        </div>
      ))}
      {editable && (
        <div className="row-actions">
          <button type="button" className="btn" onClick={() => setItems([...items, { name: "", vendor: "", version: "", cpe: "" }])}>
            {t("assets.software_add")}
          </button>
          <button type="button" className="btn btn--primary" onClick={() => void save()}>{t("common.save")}</button>
        </div>
      )}
    </section>
  );
}

// ---- Relations ----------------------------------------------------------------------------------
function RelationsTab({ asset, vocab, onChanged }: { asset: AssetDto; vocab: AssetVocabulary; onChanged: () => void }) {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("asset.edit");
  const [target, setTarget] = useState("");
  const [relation, setRelation] = useState(vocab.relations[0]);
  const [protocol, setProtocol] = useState("");
  const [direction, setDirection] = useState("outgoing");
  const [problems, setProblems] = useState<string[]>([]);
  const rel = asset.relations ?? { outgoing: [], incoming: [] };

  const add = async () => {
    setProblems([]);
    try {
      await endpoints.addRelation(asset.id, { target, relation, protocol, note: "", direction });
      setTarget("");
      setProtocol("");
      onChanged();
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    }
  };
  const remove = async (id: number) => {
    try {
      await endpoints.removeRelation(asset.id, id);
      notify.success(t("assets.relation_removed"));
      onChanged();
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  };

  const list = (title: string, rows: RelationDto[], other: "target" | "source") => (
    <section className="card" aria-label={title}>
      <h2>{title}</h2>
      {rows.length === 0 && <p>{t("common.empty")}</p>}
      <ul style={{ margin: 0, paddingLeft: 20 }}>
        {rows.map((r) => (
          <li key={r.id}>
            <span className="mono">{r[other]}</span> · {t(`assets.relation.${r.relation}`, { defaultValue: r.relation })}
            {r.protocol && <span className="field__help"> · {r.protocol}</span>}
            {r.note && <span className="field__help"> · {r.note}</span>}{" "}
            {editable && (
              <button type="button" className="btn btn--danger btn--small" onClick={() => void remove(r.id)}>
                {t("common.remove")}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );

  return (
    <>
      <div className="grid-2">
        {list(t("assets.relations_out"), rel.outgoing, "target")}
        {list(t("assets.relations_in"), rel.incoming, "source")}
      </div>
      {editable && (
        <section className="card">
          <h2>{t("assets.relation_add")}</h2>
          <Problems messages={problems} />
          <div className="grid-2">
            <SelectField label={t("assets.direction")} value={direction} onChange={(e) => setDirection(e.target.value)}
              options={[{ value: "outgoing", label: t("assets.direction.outgoing") },
                { value: "incoming", label: t("assets.direction.incoming") }]} />
            <TextField label={t("assets.relation_target")} value={target} onChange={(e) => setTarget(e.target.value)} />
            <SelectField label={t("assets.relation_kind")} value={relation} onChange={(e) => setRelation(e.target.value)}
              options={vocab.relations.map((r) => ({ value: r, label: t(`assets.relation.${r}`, { defaultValue: r }) }))} />
            <TextField label={t("assets.relation_protocol")} value={protocol} onChange={(e) => setProtocol(e.target.value)} />
          </div>
          <button type="button" className="btn btn--primary" disabled={!target} onClick={() => void add()}>
            {t("assets.relation_add")}
          </button>
        </section>
      )}
    </>
  );
}

// ---- Credentials --------------------------------------------------------------------------------
function CredentialsTab({ asset, vocab }: { asset: AssetDto; vocab: AssetVocabulary }) {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const manage = can("asset.credential.rotate");
  const [rows, setRows] = useState<CredentialDto[]>([]);
  const [creating, setCreating] = useState(false);
  const [scopes, setScopes] = useState<string[]>([]);
  const [networks, setNetworks] = useState("");
  const [days, setDays] = useState(90);
  const [problems, setProblems] = useState<string[]>([]);
  const [shown, setShown] = useState<CredentialDto | null>(null);
  const [confirm, setConfirm] = useState<{ kind: "rotate" | "revoke"; cred: CredentialDto } | null>(null);

  const load = useCallback(() => void endpoints.credentials(asset.id).then(setRows).catch(() => undefined), [asset.id]);
  useEffect(() => load(), [load]);

  const create = async () => {
    setProblems([]);
    try {
      const created = await endpoints.createCredential(asset.id, {
        scopes, allowed_networks: networks.split(/[\s,]+/).filter(Boolean), valid_days: days,
      });
      setCreating(false);
      setShown(created);
      load();
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    }
  };

  const run = async () => {
    if (!confirm) return;
    try {
      if (confirm.kind === "rotate") setShown(await endpoints.rotateCredential(confirm.cred.key_id, 0));
      else {
        await endpoints.revokeCredential(confirm.cred.key_id);
        notify.success(t("assets.credential_revoked"));
      }
      setConfirm(null);
      load();
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
      setConfirm(null);
    }
  };

  return (
    <>
      <section className="card">
        <p className="field__help">{t("assets.credentials_help")}</p>
        {manage && asset.can_ingest && asset.status !== "decommissioned" && (
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
            {t("assets.credential_create")}
          </button>
        )}
        {!asset.can_ingest && <div className="banner">{t("assets.credential_type_hint")}</div>}
        <TableWrap>
          <table className="table">
            <thead>
              <tr>
                <th>{t("assets.credential_key")}</th><th>{t("assets.credential_scopes")}</th>
                <th>{t("assets.credential_networks")}</th><th>{t("assets.status")}</th>
                <th>{t("assets.credential_expires")}</th><th>{t("assets.credential_used")}</th><th />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={7}>{t("common.empty")}</td></tr>}
              {rows.map((c) => (
                <tr key={c.key_id}>
                  <td className="mono">{c.key_id}</td>
                  <td>{c.scopes.join(", ")}</td>
                  <td className="mono">{c.allowed_networks.join(", ")}</td>
                  <td>
                    <span className={`badge ${c.state === "active" ? "badge--ok" : c.state === "retiring" ? "badge--warn" : "badge--bad"}`}>
                      {t(`assets.credential_state.${c.state}`, { defaultValue: c.state })}
                    </span>
                  </td>
                  <td>{new Date(c.expires_at).toLocaleDateString()}</td>
                  <td>{c.last_used_at ? new Date(c.last_used_at).toLocaleString() : "—"}</td>
                  <td>
                    {manage && (c.state === "active" || c.state === "retiring") && (
                      <div className="row-actions">
                        <button type="button" className="btn btn--small" onClick={() => setConfirm({ kind: "rotate", cred: c })}>
                          {t("assets.credential_rotate")}
                        </button>
                        <button type="button" className="btn btn--danger btn--small"
                          onClick={() => setConfirm({ kind: "revoke", cred: c })}>{t("assets.credential_revoke")}</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </section>

      <Dialog open={creating} onOpenChange={setCreating} title={t("assets.credential_create")}
        primary={{ label: t("assets.credential_create_submit"), onClick: () => void create(), disabled: scopes.length === 0 }}>
        <Problems messages={problems} />
        <fieldset className="field" style={{ border: 0, padding: 0 }}>
          <legend className="field__label">{t("assets.credential_scopes")}</legend>
          <div className="caps">
            {vocab.scopes.filter((s) => s !== "ingest:heartbeat").map((s) => (
              <CheckboxField key={s} label={s} checked={scopes.includes(s)}
                onChange={(e) => setScopes(e.target.checked ? [...scopes, s] : scopes.filter((v) => v !== s))} />
            ))}
          </div>
        </fieldset>
        <TextField label={t("assets.credential_networks")} help={t("assets.credential_networks_help")} value={networks}
          onChange={(e) => setNetworks(e.target.value)} />
        <NumberField label={t("assets.credential_days")} value={days} onChange={(e) => setDays(Number(e.target.value))} />
      </Dialog>

      <Dialog open={!!shown} onOpenChange={() => undefined} dismissible={false} title={t("assets.credential_once_title")}
        description={t("assets.credential_once_text")}
        primary={{ label: t("assets.credential_stored"), onClick: () => setShown(null) }}>
        {shown && (
          <>
            <TextField label={t("assets.credential_key")} value={shown.key_id} readOnly />
            <TextField label={t("assets.credential_secret")} value={shown.secret ?? ""} readOnly />
            <button type="button" className="btn" onClick={() => void navigator.clipboard?.writeText(shown.secret ?? "")}>
              {t("assets.credential_copy")}
            </button>
          </>
        )}
      </Dialog>

      <ConfirmDialog
        open={!!confirm}
        title={confirm ? t(`assets.credential_${confirm.kind}_title`) : ""}
        message={confirm ? t(`assets.credential_${confirm.kind}_text`, { key: confirm.cred.key_id }) : ""}
        confirmLabel={confirm ? t(`assets.credential_${confirm.kind}`) : ""}
        danger={confirm?.kind === "revoke"}
        onConfirm={() => void run()}
        onCancel={() => setConfirm(null)}
      />
    </>
  );
}

// ---- Page ---------------------------------------------------------------------------------------
export function AssetDetailPage() {
  const { t } = useTranslation();
  const notify = useNotify();
  const navigate = useNavigate();
  const { can } = useSession();
  const { id } = useParams();
  const assetId = Number(id);
  const [asset, setAsset] = useState<AssetDto | null>(null);
  const [vocab, setVocab] = useState<AssetVocabulary | null>(null);
  const [zones, setZones] = useState<ZoneDto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("overview");
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      setAsset(await endpoints.getAsset(assetId));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  }, [assetId, t]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    void endpoints.vocabulary().then(setVocab).catch(() => undefined);
    void endpoints.zones().then(setZones).catch(() => undefined);
  }, []);

  if (error) return <div className="banner banner--error" role="alert">{error}</div>;
  if (!asset || !vocab) return <p>{t("common.loading")}</p>;

  const remove = async () => {
    try {
      await endpoints.deleteAsset(asset.id);
      notify.success(t("assets.deleted"));
      navigate("/assets");
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
      setDeleting(false);
    }
  };

  return (
    <>
      <p><Link to="/assets">{t("assets.back")}</Link></p>
      <h1>
        <span className="mono">{asset.code}</span> <span className="field__help">{asset.name}</span>
      </h1>
      <div className="toolbar">
        <span className="badge">{t(`assets.status.${asset.status}`, { defaultValue: asset.status })}</span>
        <span className={`badge ${asset.criticality === "critical" ? "badge--bad" : ""}`}>
          {t(`assets.criticality.${asset.criticality}`, { defaultValue: asset.criticality })}
        </span>
        {asset.is_demo && <span className="badge badge--warn">{t("assets.demo")}</span>}
        {asset.last_seen_at && <span className="field__help">{t("assets.last_seen", {
          time: new Date(asset.last_seen_at).toLocaleString() })}</span>}
        {can("asset.delete") && (asset.status === "planned" || asset.status === "decommissioned") && (
          <button type="button" className="btn btn--danger" onClick={() => setDeleting(true)}>{t("assets.delete")}</button>
        )}
      </div>
      <Tabs
        label={asset.code}
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "overview", label: t("assets.tab_overview"),
            content: <Overview asset={asset} vocab={vocab} zones={zones} onSaved={setAsset} /> },
          { id: "software", label: t("assets.tab_software"), content: <SoftwareTab asset={asset} onSaved={setAsset} /> },
          { id: "relations", label: t("assets.tab_relations"),
            content: <RelationsTab asset={asset} vocab={vocab} onChanged={() => void load()} /> },
          { id: "credentials", label: t("assets.tab_credentials"), content: <CredentialsTab asset={asset} vocab={vocab} /> },
        ]}
      />
      <ConfirmDialog open={deleting} title={t("assets.delete_title", { code: asset.code })}
        message={t("assets.delete_text")} confirmLabel={t("assets.delete")} danger
        onConfirm={() => void remove()} onCancel={() => setDeleting(false)} />
    </>
  );
}
