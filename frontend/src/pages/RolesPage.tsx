import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, endpoints, RoleDto } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Dialog } from "../components/Dialog";
import { CheckboxField, NumberField, TextField } from "../components/Field";
import { useNotify } from "../components/Notify";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";

function groupCapabilities(all: string[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const cap of all) (groups[cap.split(".")[0]] ??= []).push(cap);
  return groups;
}

export function RolesPage() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("role.manage");
  const [roles, setRoles] = useState<RoleDto[]>([]);
  const [catalogue, setCatalogue] = useState<string[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<RoleDto | null>(null);
  const [name, setName] = useState("");
  const [level, setLevel] = useState(40);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await endpoints.listRoles();
      setRoles(data.roles);
      setCatalogue(data.capabilities);
    } catch (e) {
      setErrors(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const role = roles.find((r) => r.id === selected) ?? null;
  useEffect(() => {
    setDraft(new Set(role?.capabilities ?? []));
    setErrors([]);
  }, [role?.id, role?.capabilities.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const groups = useMemo(() => groupCapabilities(catalogue), [catalogue]);
  const fixed = !editable || !role || role.locked;

  const save = async () => {
    if (!role) return;
    setBusy(true);
    setErrors([]);
    try {
      await endpoints.updateRole(role.id, { capabilities: [...draft].sort() });
      notify.success(t("roles.saved"));
      await load();
    } catch (e) {
      setErrors(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  const create = async () => {
    setBusy(true);
    try {
      const created = await endpoints.createRole({ name, description: "", security_level: level, capabilities: [] });
      notify.success(t("roles.created", { name: created.name }));
      setCreating(false);
      setName("");
      await load();
      setSelected(created.id);
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e).join(" ") : t("errors.network_error"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!deleting) return;
    setBusy(true);
    try {
      await endpoints.deleteRole(deleting.id);
      notify.success(t("roles.deleted"));
      setDeleting(null);
      setSelected(null);
      await load();
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
      setDeleting(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1>{t("nav.roles")}</h1>
      <p className="field__help">{t("roles.intro")}</p>
      <div className="toolbar">
        {editable && (
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>{t("roles.create")}</button>
        )}
      </div>
      <div className="grid-2">
        <section className="card" aria-label={t("nav.roles")}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {roles.map((r) => (
              <li key={r.id}>
                <button type="button" className="btn btn--ghost" style={{ width: "100%", justifyContent: "space-between" }}
                  aria-pressed={r.id === selected} onClick={() => setSelected(r.id)}>
                  <span>
                    {r.name} <span className="field__help">({r.user_count})</span>
                  </span>
                  <span className="field__help">{t("roles.level", { level: r.security_level })}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="card" aria-label={t("roles.capabilities")}>
          {!role && <p>{t("roles.select")}</p>}
          {role && (
            <>
              <h2>{role.name}</h2>
              <p className="field__help">{role.description}</p>
              {role.locked && <div className="banner">{t("roles.administrator_fixed")}</div>}
              {errors.length > 0 && (
                <div className="banner banner--error" role="alert">
                  <ul>{errors.map((m) => <li key={m}>{m}</li>)}</ul>
                </div>
              )}
              {Object.entries(groups).map(([group, caps]) => (
                <fieldset key={group} className="field" style={{ border: 0, padding: 0 }}>
                  <legend className="field__label">{t(`roles.group.${group}`, { defaultValue: group })}</legend>
                  <div className="caps">
                    {caps.map((cap) => (
                      <CheckboxField
                        key={cap}
                        label={cap}
                        checked={role.locked ? role.capabilities.includes(cap) : draft.has(cap)}
                        disabled={fixed}
                        onChange={(e) => {
                          const next = new Set(draft);
                          if (e.target.checked) next.add(cap);
                          else next.delete(cap);
                          setDraft(next);
                        }}
                      />
                    ))}
                  </div>
                </fieldset>
              ))}
              {!fixed && (
                <div className="row-actions">
                  <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void save()}>
                    {t("common.save")}
                  </button>
                  {!role.is_system && (
                    <button type="button" className="btn btn--danger" onClick={() => setDeleting(role)}>
                      {t("roles.delete")}
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </div>

      <Dialog open={creating} onOpenChange={setCreating} title={t("roles.create")}
        primary={{ label: t("roles.create_submit"), onClick: () => void create(), busy, disabled: name.trim().length < 3 }}>
        <TextField label={t("roles.name")} value={name} onChange={(e) => setName(e.target.value)} />
        <NumberField label={t("roles.security_level")} help={t("roles.security_level_help")} value={level}
          onChange={(e) => setLevel(Number(e.target.value))} />
      </Dialog>
      <ConfirmDialog open={!!deleting} title={t("roles.delete_title", { name: deleting?.name ?? "" })}
        message={t("roles.delete_text")} confirmLabel={t("roles.delete")} danger busy={busy}
        onConfirm={() => void remove()} onCancel={() => setDeleting(null)} />
    </>
  );
}
