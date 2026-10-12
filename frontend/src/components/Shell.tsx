import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router-dom";
import { LANGUAGES, Language, setLanguage } from "../i18n";
import { useSession } from "../state/session";
import { useTerm } from "../state/useTerm";
import { ChangePasswordDialog } from "./ChangePasswordDialog";

type Theme = "dark" | "light";

function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem("argus.theme");
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* ignore */
  }
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("argus.theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

/** Page / layout shell: header, navigation, user menu (change password, logout), content (rules/16). */
export function Shell() {
  const { t, i18n } = useTranslation();
  const { session, logout, can } = useSession();
  const [theme, toggleTheme] = useTheme();
  const term = useTerm();
  const [changeOpen, setChangeOpen] = useState(false);
  const forced = !!session?.must_change_password;

  return (
    <div className="shell">
      {session?.dev_loginless && session.dev_banner && (
        <div className="shell__devbanner" role="note">
          {session.dev_banner}
        </div>
      )}
      <header className="shell__header">
        <NavLink to="/" className="shell__brand">
          <img src="/favicon.svg" alt="" />
          <span>{t("app.name")}</span>
        </NavLink>
        <span className="shell__spacer" />
        <label>
          <span className="sr-only">{t("shell.language")}</span>
          <select
            className="select"
            value={i18n.language}
            onChange={(e) => setLanguage(e.target.value as Language)}
          >
            {LANGUAGES.map((l) => (
              <option key={l} value={l}>
                {l.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn btn--ghost" onClick={toggleTheme} aria-pressed={theme === "light"}>
          {theme === "dark" ? t("shell.theme_light") : t("shell.theme_dark")}
        </button>
        {session?.user && session.user.username && (
          <span className="mono" aria-label={t("shell.signed_in_as")}>
            {session.user.username}
          </span>
        )}
        {session?.user?.username && (
          <button type="button" className="btn" onClick={() => setChangeOpen(true)}>
            {t("auth.change_password")}
          </button>
        )}
        <button type="button" className="btn" onClick={() => void logout()}>
          {t("auth.sign_out")}
        </button>
      </header>

      <nav className="shell__nav" aria-label={t("shell.navigation")}>
        <NavLink to="/" end>
          {term("nav.dashboard")}
        </NavLink>
        {can("incident.view") && <NavLink to="/incidents">{t("nav.incidents")}</NavLink>}
        {can("asset.view") && <NavLink to="/map">{term("nav.map")}</NavLink>}
        {can("asset.view") && <NavLink to="/assets">{t("nav.assets")}</NavLink>}
        {can("intel.view") && <NavLink to="/intel">{t("nav.intel")}</NavLink>}
        {(can("user.view") || can("role.view") || can("role.manage") || can("audit.view") ||
          can("settings.email.view")) && (
          <>
            <h2>{t("nav.administration")}</h2>
            {can("user.view") && <NavLink to="/users">{t("nav.users")}</NavLink>}
            {(can("role.view") || can("role.manage")) && <NavLink to="/roles">{t("nav.roles")}</NavLink>}
            {can("audit.view") && <NavLink to="/audit">{t("nav.audit")}</NavLink>}
            {can("settings.email.view") && <NavLink to="/settings/email">{t("nav.email")}</NavLink>}
          </>
        )}
        {(can("policy.password.view") || can("policy.lockout.view") || can("policy.session.view")) && (
          <>
            <h2>{t("nav.settings")}</h2>
            {can("policy.password.view") && <NavLink to="/settings/password">{t("nav.password_policy")}</NavLink>}
            {can("policy.lockout.view") && <NavLink to="/settings/lockout">{t("nav.lockout")}</NavLink>}
            {can("policy.session.view") && <NavLink to="/settings/sessions">{t("nav.sessions")}</NavLink>}
          </>
        )}
      </nav>

      <main className="shell__main">
        <Outlet />
      </main>

      {/* The forced first-login change uses the same dialog and cannot be dismissed (IDN-013). */}
      <ChangePasswordDialog open={forced || changeOpen} forced={forced} onClose={() => setChangeOpen(false)} />
    </div>
  );
}
