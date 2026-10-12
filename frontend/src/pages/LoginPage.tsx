import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { TextField } from "../components/Field";
import { PasswordField } from "../components/PasswordField";
import { useSession } from "../state/session";

export function LoginPage() {
  const { t } = useTranslation();
  const { session, login } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (session?.authenticated) return <Navigate to="/" replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "network_error";
      // One message for every credential failure: the screen never says why (LCK-011).
      setError(t(code === "too_many_requests" || code === "network_error" ? `errors.${code}` : "auth.invalid"));
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <form className="card auth__card" onSubmit={(e) => void submit(e)} noValidate>
        <div className="auth__brand">
          <img src="/favicon.svg" alt="" />
          <div>
            <h1 style={{ margin: 0 }}>{t("app.name")}</h1>
            <span className="field__help">{t("app.tagline")}</span>
          </div>
        </div>
        {error && (
          <div className="banner banner--error" role="alert">
            {error}
          </div>
        )}
        <div className="field">
          <TextField
            label={t("auth.username")}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            autoCapitalize="off"
            spellCheck={false}
          />
        </div>
        <PasswordField variant="current" label={t("auth.password")} value={password} onChange={setPassword} />
        <button type="submit" className="btn btn--primary" style={{ width: "100%" }} disabled={busy || !username || !password}>
          {busy ? t("common.working") : t("auth.sign_in")}
        </button>
      </form>
    </div>
  );
}
