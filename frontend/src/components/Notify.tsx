import { createContext, ReactNode, useCallback, useContext, useMemo, useRef, useState } from "react";

// One notification API and one style set (rules/16): success, error, warning, info.
type Kind = "success" | "error" | "warning" | "info";
interface Item {
  id: number;
  kind: Kind;
  message: string;
}

interface NotifyApi {
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
}

const NotifyContext = createContext<NotifyApi | null>(null);
const DISPLAY_MS = 6000;

export function NotifyProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const counter = useRef(0);

  const push = useCallback((kind: Kind, message: string) => {
    const id = ++counter.current;
    setItems((current) => [...current, { id, kind, message }]);
    window.setTimeout(() => setItems((current) => current.filter((i) => i.id !== id)), DISPLAY_MS);
  }, []);

  const api = useMemo<NotifyApi>(
    () => ({
      success: (m) => push("success", m),
      error: (m) => push("error", m),
      warning: (m) => push("warning", m),
      info: (m) => push("info", m),
    }),
    [push],
  );

  return (
    <NotifyContext.Provider value={api}>
      {children}
      <div className="notify" role="status" aria-live="polite">
        {items.map((item) => (
          <div key={item.id} className="notify__item" data-kind={item.kind}>
            {item.message}
          </div>
        ))}
      </div>
    </NotifyContext.Provider>
  );
}

export function useNotify(): NotifyApi {
  const ctx = useContext(NotifyContext);
  if (!ctx) throw new Error("useNotify outside NotifyProvider");
  return ctx;
}
