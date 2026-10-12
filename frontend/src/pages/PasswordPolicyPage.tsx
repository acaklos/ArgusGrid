import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, endpoints, PasswordPolicy } from "../api/client";
import { CheckboxField, NumberField } from "../components/Field";
import { useNotify } from "../components/Notify";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";
import { fieldErrors, useLoad } from "../state/useLoad";
import { invalidatePolicy } from "../state/usePolicy";

type NumericKey =
  | "min_length" | "max_length" | "expiration_months" | "expiry_notice_days"
  | "history_count" | "min_age_hours" | "reveal_autohide_seconds";
type BooleanKey =
  | "require_upper" | "require_lower" | "require_digit" | "require_special" | "expiration_enabled"
  | "history_applies_to_admin_set" | "reject_username" | "reject_common";

const NUMBERS: NumericKey[] = [
  "min_length", "max_length", "expiration_months", "expiry_notice_days", "history_count", "min_age_hours",
  "reveal_autohide_seconds",
];
const FLAGS: BooleanKey[] = [
  "require_upper", "require_lower", "require_digit", "require_special", "expiration_enabled",
  "history_applies_to_admin_set", "reject_username", "reject_common",
];

/** All password settings on one page; the values shown on first open are the defaults (D-16). */
export function PasswordPolicyPage() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("policy.password.edit");
  const { data, setData, error, loading } = useLoad(endpoints.getPasswordPolicy);
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const [perField, setPerField] = useState<Record<string, string[]>>({});

  if (loading) return <p>{t("common.loading")}</p>;
  if (error || !data) return <div className="banner banner--error">{t(`errors.${error?.code ?? "unknown"}`)}</div>;
  const policy = data.policy;

  const update = <K extends keyof PasswordPolicy>(key: K, value: PasswordPolicy[K]) =>
    setData({ ...data, policy: { ...policy, [key]: value } });

  const save = async () => {
    setBusy(true);
    setProblems([]);
    setPerField({});
    try {
      const saved = await endpoints.putPasswordPolicy(policy);
      setData(saved);
      invalidatePolicy();
      notify.success(t("settings.saved"));
    } catch (e) {
      if (e instanceof ApiError) {
        setProblems(errorMessages(t, e));
        setPerField(fieldErrors(e.details, (c) => t(`errors.${c}`, { defaultValue: c })));
      }
      notify.error(t("settings.not_saved"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1>{t("nav.password_policy")}</h1>
      <p className="field__help">{t("password_policy.intro")}</p>
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
      <form className="card" onSubmit={(e) => { e.preventDefault(); void save(); }}>
        <div className="grid-2">
          {NUMBERS.map((key) => (
            <NumberField
              key={key}
              label={t(`field.${key}`)}
              help={t(`help.${key}`)}
              value={policy[key]}
              disabled={!editable}
              error={perField[key]?.join("; ")}
              onChange={(e) => update(key, Number(e.target.value))}
            />
          ))}
        </div>
        <div className="grid-2">
          {FLAGS.map((key) => (
            <CheckboxField
              key={key}
              label={t(`field.${key}`)}
              checked={policy[key]}
              disabled={!editable}
              error={perField[key]?.join("; ")}
              onChange={(e) => update(key, e.target.checked)}
            />
          ))}
        </div>
        {editable && (
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? t("common.working") : t("common.save")}
          </button>
        )}
      </form>
    </>
  );
}
