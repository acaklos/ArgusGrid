import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";

/** One loading pattern for settings pages: data, loading flag, error and reload. */
export function useLoad<T>(loader: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await run());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "network_error"));
    } finally {
      setLoading(false);
    }
  }, [run]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, setData, error, loading, reload };
}

/** Group server problems by field so each control can show its own message. */
export function fieldErrors(details: unknown, translate: (code: string) => string): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  if (!Array.isArray(details)) return out;
  for (const problem of details as { code?: string; fields?: string[] }[]) {
    if (!problem || typeof problem !== "object" || !problem.code) continue;
    for (const f of problem.fields ?? []) {
      (out[f] ??= []).push(translate(problem.code));
    }
  }
  return out;
}
