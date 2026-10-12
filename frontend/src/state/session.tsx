import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, endpoints, SessionInfo } from "../api/client";

interface SessionState {
  loading: boolean;
  session: SessionInfo | null;
  login: (username: string, password: string) => Promise<SessionInfo>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  can: (capability: string) => boolean;
}

const SessionContext = createContext<SessionState | null>(null);

const ANONYMOUS: SessionInfo = {
  profile: { name: "civil", marking: "" },
  authenticated: false,
  user: null,
  csrf_token: null,
  must_change_password: false,
  capabilities: [],
  dev_loginless: false,
  dev_banner: "",
  password_expires_at: null,
};

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const apply = useCallback((info: SessionInfo) => {
    api.setCsrfToken(info.csrf_token);
    // the profile belongs to the deployment, so it survives logout and an expired session
    setSession((previous) => (info === ANONYMOUS && previous ? { ...info, profile: previous.profile } : info));
  }, []);

  const refresh = useCallback(async () => {
    try {
      apply(await endpoints.session());
    } catch {
      apply(ANONYMOUS);
    } finally {
      setLoading(false);
    }
  }, [apply]);

  useEffect(() => {
    void refresh();
    return api.onUnauthorized(() => apply(ANONYMOUS));
  }, [refresh, apply]);

  const login = useCallback(
    async (username: string, password: string) => {
      const info = await endpoints.login(username, password);
      apply(info);
      return info;
    },
    [apply],
  );

  const logout = useCallback(async () => {
    try {
      await endpoints.logout();
    } finally {
      apply(ANONYMOUS);
    }
  }, [apply]);

  const value = useMemo<SessionState>(
    () => ({
      loading,
      session,
      login,
      logout,
      refresh,
      can: (capability: string) =>
        !!session?.authenticated &&
        (session.capabilities.includes("*") || session.capabilities.includes(capability)),
    }),
    [loading, session, login, logout, refresh],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside SessionProvider");
  return ctx;
}
