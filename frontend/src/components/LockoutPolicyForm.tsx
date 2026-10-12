import { useTranslation } from "react-i18next";
import { LockoutPolicy } from "../api/client";
import { CheckboxField, NumberField, SelectField, TextField } from "./Field";

interface Props {
  title: string;
  policy: LockoutPolicy;
  roleNames: string[];
  disabled: boolean;
  errors: Record<string, string[]>;
  onChange: (policy: LockoutPolicy) => void;
  onRemove?: () => void;
}

function parseDurations(text: string): number[] {
  return text
    .split(/[,\s]+/)
    .filter(Boolean)
    .map((p) => Number(p))
    .filter((n) => Number.isFinite(n));
}

/** One lockout policy (rules/18 section 1). Used for the default policy and for each role override. */
export function LockoutPolicyForm({ title, policy, roleNames, disabled, errors, onChange, onRemove }: Props) {
  const { t } = useTranslation();
  const set = <K extends keyof LockoutPolicy>(key: K, value: LockoutPolicy[K]) => onChange({ ...policy, [key]: value });
  const err = (key: string) => errors[key]?.join("; ");

  const toggleUnlocker = (role: string, on: boolean) =>
    set("unlockers", on ? [...policy.unlockers, role] : policy.unlockers.filter((r) => r !== role));

  return (
    <section className="card" aria-label={title}>
      <h2>{title}</h2>
      <div className="grid-2">
        <SelectField
          label={t("lockout.mode")}
          value={policy.mode}
          disabled={disabled}
          error={err("mode")}
          onChange={(e) => set("mode", e.target.value as LockoutPolicy["mode"])}
          options={[
            { value: "auto_unlock", label: t("lockout.mode.auto_unlock") },
            { value: "escalating", label: t("lockout.mode.escalating") },
            { value: "permanent", label: t("lockout.mode.permanent") },
          ]}
        />
        <SelectField
          label={t("lockout.after_unlock")}
          value={policy.after_unlock}
          disabled={disabled}
          error={err("after_unlock")}
          onChange={(e) => set("after_unlock", e.target.value as LockoutPolicy["after_unlock"])}
          options={[
            { value: "none", label: t("lockout.after_unlock.none") },
            { value: "require_password_change", label: t("lockout.after_unlock.require_password_change") },
            { value: "reset_password", label: t("lockout.after_unlock.reset_password") },
          ]}
        />
        <NumberField
          label={t("lockout.threshold")}
          value={policy.threshold}
          disabled={disabled}
          error={err("threshold")}
          onChange={(e) => set("threshold", Number(e.target.value))}
        />
        <NumberField
          label={t("lockout.window")}
          value={policy.window_minutes}
          disabled={disabled}
          error={err("window_minutes")}
          onChange={(e) => set("window_minutes", Number(e.target.value))}
        />
        {policy.mode !== "permanent" && (
          <TextField
            label={t("lockout.durations")}
            help={t("lockout.durations_help")}
            value={policy.durations_minutes.join(", ")}
            disabled={disabled}
            error={err("durations_minutes")}
            onChange={(e) => set("durations_minutes", parseDurations(e.target.value))}
          />
        )}
        {policy.mode !== "permanent" && (
          <NumberField
            label={t("lockout.cycles")}
            help={t("lockout.cycles_help")}
            value={policy.cycles_before_permanent ?? ""}
            disabled={disabled}
            error={err("cycles_before_permanent")}
            onChange={(e) => set("cycles_before_permanent", e.target.value === "" ? null : Number(e.target.value))}
          />
        )}
      </div>
      <fieldset className="field" style={{ border: 0, padding: 0 }}>
        <legend className="field__label">{t("lockout.unlockers")}</legend>
        {roleNames.map((role) => (
          <CheckboxField
            key={role}
            label={role}
            checked={policy.unlockers.includes(role)}
            disabled={disabled}
            onChange={(e) => toggleUnlocker(role, e.target.checked)}
          />
        ))}
        {err("unlockers") && <span className="field__error">{err("unlockers")}</span>}
      </fieldset>
      <div className="grid-2">
        <CheckboxField
          label={t("lockout.revoke_sessions")}
          checked={policy.revoke_sessions}
          disabled={disabled}
          onChange={(e) => set("revoke_sessions", e.target.checked)}
        />
        <CheckboxField
          label={t("lockout.notify")}
          checked={policy.notify}
          disabled={disabled}
          onChange={(e) => set("notify", e.target.checked)}
        />
      </div>
      {onRemove && !disabled && (
        <button type="button" className="btn btn--danger btn--small" onClick={onRemove}>
          {t("lockout.remove_override")}
        </button>
      )}
    </section>
  );
}
