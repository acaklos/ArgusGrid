import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { endpoints, PasswordSummary } from "../api/client";
import { useSession } from "../state/session";
import { usePasswordPolicy } from "../state/usePolicy";

/**
 * The one password input of the application (rules/17 section 5, rules/16, SOL-011).
 * - variant "current": a single field (login, current password).
 * - variant "new": generated mode shows ONE field, custom mode shows TWO (entry and confirm).
 *   Switching from custom to generated generates a password immediately (PWD-032).
 * - every field has a reveal control with tabIndex -1 (PWD-034) that hides again after the policy time.
 * - a live checklist shows the active rules read from the policy service (PWD-037).
 */

export interface RuleResult {
  key: string;
  count?: number;
  ok: boolean;
}

/** Client-side evaluation of the rules the server publishes. Server validation stays authoritative. */
export function evaluateRules(policy: PasswordSummary, password: string, username = ""): RuleResult[] {
  const rules: RuleResult[] = [];
  rules.push({ key: "min_length", count: policy.min_length, ok: password.length >= policy.min_length });
  rules.push({ key: "max_length", count: policy.max_length, ok: password.length <= policy.max_length });
  if (policy.require_upper) rules.push({ key: "upper", ok: /\p{Lu}/u.test(password) });
  if (policy.require_lower) rules.push({ key: "lower", ok: /\p{Ll}/u.test(password) });
  if (policy.require_digit) rules.push({ key: "digit", ok: /\p{Nd}/u.test(password) });
  if (policy.require_special) rules.push({ key: "special", ok: /[^\p{L}\p{N}\s]/u.test(password) });
  if (policy.reject_username && username) {
    rules.push({ key: "username", ok: !password.toLowerCase().includes(username.toLowerCase()) });
  }
  return rules;
}

interface RevealInputProps {
  id?: string;
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  autoComplete: string;
  autohideSeconds: number;
  invalid?: boolean;
  describedBy?: string;
  disabled?: boolean;
  name?: string;
  ariaLabel?: string;
  placeholder?: string;
}

function RevealInput({
  id, value, onChange, readOnly, autoComplete, autohideSeconds, invalid, describedBy, disabled, name, ariaLabel,
  placeholder,
}: RevealInputProps) {
  const { t } = useTranslation();
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (!shown || autohideSeconds <= 0) return;
    const timer = window.setTimeout(() => setShown(false), autohideSeconds * 1000);
    return () => window.clearTimeout(timer);
  }, [shown, autohideSeconds]);

  return (
    <div className="pwd__row">
      <input
        id={id}
        name={name}
        className="input"
        type={shown ? "text" : "password"}
        value={value}
        readOnly={readOnly}
        disabled={disabled}
        autoComplete={autoComplete}
        aria-label={ariaLabel}
        placeholder={placeholder}
        aria-describedby={describedBy}
        aria-invalid={invalid || undefined}
        onChange={(e) => onChange?.(e.target.value)}
        spellCheck={false}
        autoCapitalize="off"
      />
      {/* tabIndex -1: TAB goes from the user name straight to the password so managers can auto-type */}
      <button
        type="button"
        className="pwd__reveal"
        tabIndex={-1}
        aria-label={shown ? t("password.hide") : t("password.show")}
        aria-pressed={shown}
        onClick={() => setShown((s) => !s)}
      >
        {shown ? "🙈" : "👁"}
      </button>
    </div>
  );
}

interface BaseProps {
  label: string;
  error?: string | null;
  disabled?: boolean;
  name?: string;
}

interface CurrentProps extends BaseProps {
  variant: "current";
  value: string;
  onChange: (value: string) => void;
  autoComplete?: "current-password";
}

interface NewProps extends BaseProps {
  variant: "new";
  value: string;
  onChange: (value: string) => void;
  username?: string;
  defaultMode?: "generated" | "custom";
  allowGenerated?: boolean;
  showChecklist?: boolean;
  onValidChange?: (valid: boolean) => void;
}

interface SecretProps extends BaseProps {
  variant: "secret";
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export type PasswordFieldProps = CurrentProps | NewProps | SecretProps;

export function PasswordField(props: PasswordFieldProps) {
  if (props.variant === "current") return <CurrentPassword {...props} />;
  if (props.variant === "secret") return <SecretField {...props} />;
  return <NewPassword {...props} />;
}

/** A stored secret (for example the SMTP password): one field, never auto-filled by the browser. */
function SecretField({ label, value, onChange, error, disabled, name, placeholder }: SecretProps) {
  const { session } = useSession();
  const policy = usePasswordPolicy(!!session?.authenticated);
  const id = useId();
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <RevealInput
        id={id}
        name={name}
        value={value}
        onChange={onChange}
        autoComplete="off"
        autohideSeconds={policy?.reveal_autohide_seconds ?? 5}
        invalid={!!error}
        disabled={disabled}
        placeholder={placeholder}
      />
      {error && (
        <span className="field__error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

function CurrentPassword({ label, value, onChange, error, disabled, name }: CurrentProps) {
  // The policy needs a session; on the login page the default reveal time applies.
  const { session } = useSession();
  const policy = usePasswordPolicy(!!session?.authenticated);
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <RevealInput
        id={id}
        name={name}
        value={value}
        onChange={onChange}
        autoComplete="current-password"
        autohideSeconds={policy?.reveal_autohide_seconds ?? 5}
        invalid={!!error}
        describedBy={error ? errorId : undefined}
        disabled={disabled}
      />
      {error && (
        <span id={errorId} className="field__error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

function NewPassword({
  label, value, onChange, username = "", defaultMode = "generated", allowGenerated = true,
  showChecklist = true, onValidChange, error, disabled, name,
}: NewProps) {
  const { t } = useTranslation();
  const policy = usePasswordPolicy();
  const id = useId();
  const confirmId = `${id}-confirm`;
  const errorId = `${id}-error`;
  const [custom, setCustom] = useState(defaultMode === "custom" || !allowGenerated);
  const [confirm, setConfirm] = useState("");
  const [generating, setGenerating] = useState(false);
  const generatedOnce = useRef(false);

  const generate = useCallback(async () => {
    setGenerating(true);
    try {
      const { password } = await endpoints.generatePassword();
      onChange(password);
    } finally {
      setGenerating(false);
    }
  }, [onChange]);

  // Generated mode: produce a password as soon as the field appears and whenever the mode switches to it.
  useEffect(() => {
    if (!custom && !generatedOnce.current) {
      generatedOnce.current = true;
      void generate();
    }
  }, [custom, generate]);

  const switchMode = (nextCustom: boolean) => {
    setCustom(nextCustom);
    setConfirm("");
    if (nextCustom) {
      onChange("");
    } else {
      generatedOnce.current = true;
      void generate(); // PWD-032: generated immediately on switching
    }
  };

  const results = policy ? evaluateRules(policy, value, username) : [];
  const rulesOk = results.length > 0 && results.every((r) => r.ok);
  const matches = custom ? value !== "" && value === confirm : true;
  const valid = rulesOk && matches && !generating;

  useEffect(() => {
    onValidChange?.(valid);
  }, [valid, onValidChange]);

  const autohide = policy?.reveal_autohide_seconds ?? 5;
  const confirmMismatch = custom && confirm !== "" && confirm !== value;

  return (
    <div className="pwd">
      <div className="field">
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
        <RevealInput
          id={id}
          name={name}
          value={value}
          onChange={custom ? onChange : undefined}
          readOnly={!custom}
          autoComplete="new-password"
          autohideSeconds={autohide}
          invalid={!!error}
          describedBy={error ? errorId : undefined}
          disabled={disabled}
        />
      </div>

      {custom && (
        <div className="field">
          <label className="field__label" htmlFor={confirmId}>
            {t("password.confirm")}
          </label>
          <RevealInput
            id={confirmId}
            value={confirm}
            onChange={setConfirm}
            autoComplete="new-password"
            autohideSeconds={autohide}
            invalid={confirmMismatch}
            disabled={disabled}
          />
          {confirmMismatch && (
            <span className="field__error" role="alert">
              {t("password.mismatch")}
            </span>
          )}
        </div>
      )}

      {allowGenerated && (
        <div className="field field--inline">
          <input
            id={`${id}-custom`}
            type="checkbox"
            checked={custom}
            onChange={(e) => switchMode(e.target.checked)}
            disabled={disabled}
          />
          <label htmlFor={`${id}-custom`}>{t("password.custom")}</label>
          {!custom && (
            <button type="button" className="btn btn--small" onClick={() => void generate()} disabled={generating}>
              {t("password.generate_new")}
            </button>
          )}
        </div>
      )}

      {error && (
        <span id={errorId} className="field__error" role="alert">
          {error}
        </span>
      )}

      {showChecklist && results.length > 0 && (
        <ul className="pwd__rules" aria-label={t("password.rules")}>
          {results.map((r) => (
            <li key={r.key} data-ok={r.ok}>
              <span aria-hidden="true">{r.ok ? "✓" : "•"}</span>
              <span>
                {t(`password.rule.${r.key}`, { count: r.count })}
                <span className="sr-only">{r.ok ? ` ${t("password.rule_ok")}` : ` ${t("password.rule_open")}`}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
