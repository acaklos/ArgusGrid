import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, endpoints, LockoutPolicy, LockoutSettings } from "../api/client";
import { CheckboxField, NumberField, SelectField } from "../components/Field";
import { LockoutPolicyForm } from "../components/LockoutPolicyForm";
import { useNotify } from "../components/Notify";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";
import { useLoad } from "../state/useLoad";

type TFn = (key: string, options?: Record<string, unknown>) => string;

/** Plain-words description of what a policy does, so the page states the effective behaviour (LCK section 3). */
export function describePolicy(t: TFn, who: string, p: LockoutPolicy): string {
  const unlockers = p.unlockers.join(", ");
  if (p.mode === "permanent") {
    return t("lockout.summary.permanent", { who, threshold: p.threshold, window: p.window_minutes, unlockers });
  }
  const permanent =
    p.cycles_before_permanent != null ? t("lockout.summary.then_permanent", { cycles: p.cycles_before_permanent }) : "";
  if (p.mode === "escalating") {
    return t("lockout.summary.escalating", {
      who, threshold: p.threshold, window: p.window_minutes, durations: p.durations_minutes.join(", "), permanent, unlockers,
    });
  }
  return t("lockout.summary.auto_unlock", {
    who, threshold: p.threshold, window: p.window_minutes, minutes: p.durations_minutes[0] ?? 0, permanent, unlockers,
  });
}

export function LockoutPage() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("policy.lockout.edit");
  const { data, setData, error, loading } = useLoad(endpoints.getLockout);
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const [perScope, setPerScope] = useState<Record<string, Record<string, string[]>>>({});
  const [globalErrors, setGlobalErrors] = useState<Record<string, string[]>>({});
  const [overrideRole, setOverrideRole] = useState("");

  if (loading) return <p>{t("common.loading")}</p>;
  if (error || !data) return <div className="banner banner--error">{t(`errors.${error?.code ?? "unknown"}`)}</div>;

  const settings = data.settings;
  const roleNames = Object.keys(data.roles).sort((a, b) => data.roles[b] - data.roles[a]);
  const without = roleNames.filter((r) => !(r in settings.roles));
  const setSettings = (next: LockoutSettings) => setData({ ...data, settings: next });

  const save = async () => {
    setBusy(true);
    setProblems([]);
    setPerScope({});
    setGlobalErrors({});
    try {
      setData(await endpoints.putLockout(settings));
      notify.success(t("settings.saved"));
    } catch (e) {
      if (e instanceof ApiError) {
        setProblems(errorMessages(t, e));
        const scopes: Record<string, Record<string, string[]>> = {};
        const globals: Record<string, string[]> = {};
        if (Array.isArray(e.details)) {
          for (const p of e.details as { code: string; scope?: string; fields?: string[] }[]) {
            const message = t(`errors.${p.code}`, { defaultValue: p.code });
            for (const f of p.fields ?? []) {
              const target = !p.scope || p.scope === "global" ? globals : (scopes[p.scope] ??= {});
              (target[f] ??= []).push(message);
            }
          }
        }
        setPerScope(scopes);
        setGlobalErrors(globals);
      }
      notify.error(t("settings.not_saved"));
    } finally {
      setBusy(false);
    }
  };

  const description = [
    describePolicy(t as TFn, t("lockout.who_default"), settings.default),
    ...Object.entries(settings.roles).map(([role, p]) => describePolicy(t as TFn, role, p)),
  ];

  return (
    <>
      <h1>{t("nav.lockout")}</h1>
      <div className="banner" aria-label={t("lockout.effective")}>
        <strong>{t("lockout.effective")}</strong>
        <ul>
          {description.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <p style={{ margin: 0 }}>
          {settings.exempt_last_administrator ? t("lockout.exempt_on_text") : t("lockout.exempt_off_text")}
        </p>
      </div>
      {problems.length > 0 && (
        <div className="banner banner--error" role="alert">
          <strong>{t("settings.inconsistent")}</strong>
          <ul>
            {problems.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); void save(); }}>
        <section className="card">
          <h2>{t("lockout.global")}</h2>
          <CheckboxField
            label={t("lockout.exempt_last_admin")}
            help={t("lockout.exempt_last_admin_help")}
            checked={settings.exempt_last_administrator}
            disabled={!editable}
            error={globalErrors["exempt_last_administrator"]?.join("; ")}
            onChange={(e) => setSettings({ ...settings, exempt_last_administrator: e.target.checked })}
          />
          <NumberField
            label={t("lockout.throttle")}
            help={t("lockout.throttle_help")}
            value={settings.source_throttle_per_minute}
            disabled={!editable}
            error={globalErrors["source_throttle_per_minute"]?.join("; ")}
            onChange={(e) => setSettings({ ...settings, source_throttle_per_minute: Number(e.target.value) })}
          />
        </section>

        <LockoutPolicyForm
          title={t("lockout.default_policy")}
          policy={settings.default}
          roleNames={roleNames}
          disabled={!editable}
          errors={perScope["default"] ?? {}}
          onChange={(p) => setSettings({ ...settings, default: p })}
        />
        {Object.entries(settings.roles).map(([role, p]) => (
          <LockoutPolicyForm
            key={role}
            title={t("lockout.role_policy", { role })}
            policy={p}
            roleNames={roleNames}
            disabled={!editable}
            errors={perScope[role] ?? {}}
            onChange={(next) => setSettings({ ...settings, roles: { ...settings.roles, [role]: next } })}
            onRemove={() => {
              const { [role]: _removed, ...rest } = settings.roles;
              setSettings({ ...settings, roles: rest });
            }}
          />
        ))}

        {editable && without.length > 0 && (
          <div className="card">
            <SelectField
              label={t("lockout.add_override")}
              value={overrideRole}
              onChange={(e) => setOverrideRole(e.target.value)}
              options={[{ value: "", label: "—" }, ...without.map((r) => ({ value: r, label: r }))]}
            />
            <button
              type="button"
              className="btn"
              disabled={!overrideRole}
              onClick={() => {
                setSettings({ ...settings, roles: { ...settings.roles, [overrideRole]: { ...settings.default } } });
                setOverrideRole("");
              }}
            >
              {t("lockout.add_override_button")}
            </button>
          </div>
        )}

        {editable && (
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? t("common.working") : t("common.save")}
          </button>
        )}
      </form>
    </>
  );
}
