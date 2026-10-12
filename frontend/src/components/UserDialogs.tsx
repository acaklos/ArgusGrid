import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, endpoints, UserDto } from "../api/client";
import { errorMessages } from "../i18n/errors";
import { Dialog } from "./Dialog";
import { CheckboxField, SelectField, TextField } from "./Field";
import { useNotify } from "./Notify";
import { PasswordField } from "./PasswordField";

type RoleOption = { id: number; name: string; security_level: number };

function ErrorBanner({ messages }: { messages: string[] }) {
  if (messages.length === 0) return null;
  return (
    <div className="banner banner--error" role="alert">
      <ul>
        {messages.map((m) => (
          <li key={m}>{m}</li>
        ))}
      </ul>
    </div>
  );
}

function useRoles(open: boolean): RoleOption[] {
  const [roles, setRoles] = useState<RoleOption[]>([]);
  useEffect(() => {
    if (open) void endpoints.assignableRoles().then(setRoles).catch(() => setRoles([]));
  }, [open]);
  return roles;
}

function reportDelivery(t: (k: string) => string, notify: ReturnType<typeof useNotify>, user: UserDto) {
  if (user.email_queued === false) notify.warning(t("users.email_missing"));
  else if (user.email_configured === false) notify.warning(t("users.email_not_configured"));
}

interface CreateProps {
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}

/** Create a user: generated password by default (one field), custom mode has entry and repeat fields. */
export function CreateUserDialog({ open, onClose, onDone }: CreateProps) {
  const { t, i18n } = useTranslation();
  const notify = useNotify();
  const roles = useRoles(open);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("");
  const [locale, setLocale] = useState(i18n.language.startsWith("sk") ? "sk" : "en");
  const [password, setPassword] = useState("");
  const [valid, setValid] = useState(false);
  const [sendEmail, setSendEmail] = useState(true);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    // the least privileged operational role is the safe default; the choice stays with the administrator
    if (roles.length > 0 && !role) setRole((roles.find((r) => r.name === "SOC Operator") ?? roles[roles.length - 1]).name);
  }, [roles, role]);

  const submit = async () => {
    setBusy(true);
    setErrors([]);
    try {
      const created = await endpoints.createUser({
        username, email, full_name: fullName, role, locale, password, send_email: sendEmail,
      });
      notify.success(t("users.created", { username: created.username }));
      if (sendEmail) reportDelivery(t, notify, created);
      onDone();
      onClose();
    } catch (e) {
      setErrors(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  const ready = username.length >= 3 && email.includes("@") && !!role && valid;
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t("users.create")}
      primary={{ label: t("users.create_submit"), onClick: () => void submit(), busy, disabled: !ready }}
    >
      <ErrorBanner messages={errors} />
      <TextField label={t("auth.username")} value={username} onChange={(e) => setUsername(e.target.value)}
        autoComplete="off" autoCapitalize="off" />
      <TextField label={t("users.email")} value={email} onChange={(e) => setEmail(e.target.value)}
        autoComplete="off" inputMode="email" />
      <TextField label={t("users.full_name")} value={fullName} onChange={(e) => setFullName(e.target.value)}
        autoComplete="off" />
      <div className="grid-2">
        <SelectField label={t("users.role")} value={role} onChange={(e) => setRole(e.target.value)}
          options={roles.map((r) => ({ value: r.name, label: r.name }))} />
        <SelectField label={t("users.language")} value={locale} onChange={(e) => setLocale(e.target.value)}
          options={[{ value: "en", label: "English" }, { value: "sk", label: "Slovenčina" }]} />
      </div>
      <PasswordField variant="new" label={t("users.initial_password")} value={password} onChange={setPassword}
        username={username} defaultMode="generated" onValidChange={setValid} />
      <CheckboxField label={t("users.send_email")} checked={sendEmail} onChange={(e) => setSendEmail(e.target.checked)} />
    </Dialog>
  );
}

interface EditProps {
  user: UserDto | null;
  onClose: () => void;
  onDone: () => void;
  canAssignRole: boolean;
}

export function EditUserDialog({ user, onClose, onDone, canAssignRole }: EditProps) {
  const { t } = useTranslation();
  const notify = useNotify();
  const roles = useRoles(!!user);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("");
  const [locale, setLocale] = useState("en");
  const [active, setActive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    if (user) {
      setEmail(user.email);
      setFullName(user.full_name);
      setRole(user.role);
      setLocale(user.locale);
      setActive(user.is_active);
      setErrors([]);
    }
  }, [user]);

  if (!user) return null;
  const submit = async () => {
    setBusy(true);
    setErrors([]);
    try {
      const body: Parameters<typeof endpoints.updateUser>[1] = {
        email, full_name: fullName, locale, is_active: active,
      };
      if (canAssignRole && role !== user.role) body.role = role;
      await endpoints.updateUser(user.id, body);
      notify.success(t("users.updated"));
      onDone();
      onClose();
    } catch (e) {
      setErrors(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  const options = roles.some((r) => r.name === user.role) ? roles : [{ id: -1, name: user.role, security_level: 0 }, ...roles];
  return (
    <Dialog
      open={!!user}
      onOpenChange={(o) => !o && onClose()}
      title={t("users.edit", { username: user.username })}
      primary={{ label: t("common.save"), onClick: () => void submit(), busy }}
    >
      <ErrorBanner messages={errors} />
      <TextField label={t("users.email")} value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
      <TextField label={t("users.full_name")} value={fullName} onChange={(e) => setFullName(e.target.value)}
        autoComplete="off" />
      <div className="grid-2">
        <SelectField label={t("users.role")} value={role} disabled={!canAssignRole}
          onChange={(e) => setRole(e.target.value)} options={options.map((r) => ({ value: r.name, label: r.name }))} />
        <SelectField label={t("users.language")} value={locale} onChange={(e) => setLocale(e.target.value)}
          options={[{ value: "en", label: "English" }, { value: "sk", label: "Slovenčina" }]} />
      </div>
      <CheckboxField label={t("users.active")} checked={active} onChange={(e) => setActive(e.target.checked)} />
    </Dialog>
  );
}

interface ResetProps {
  user: UserDto | null;
  onClose: () => void;
  onDone: () => void;
}

export function ResetPasswordDialog({ user, onClose, onDone }: ResetProps) {
  const { t } = useTranslation();
  const notify = useNotify();
  const [password, setPassword] = useState("");
  const [valid, setValid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  if (!user) return null;
  const submit = async () => {
    setBusy(true);
    setErrors([]);
    try {
      const result = await endpoints.resetPassword(user.id, password);
      notify.success(t("users.reset_done", { username: user.username }));
      reportDelivery(t, notify, result);
      setPassword("");
      onDone();
      onClose();
    } catch (e) {
      setErrors(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={!!user}
      onOpenChange={(o) => !o && onClose()}
      title={t("users.reset_title", { username: user.username })}
      description={t("users.reset_text")}
      primary={{ label: t("users.reset_submit"), onClick: () => void submit(), busy, disabled: !valid }}
    >
      <ErrorBanner messages={errors} />
      <PasswordField variant="new" label={t("users.temporary_password")} value={password} onChange={setPassword}
        username={user.username} defaultMode="generated" onValidChange={setValid} />
    </Dialog>
  );
}
