import { useEffect, useState } from "react";
import { endpoints, PasswordSummary } from "../api/client";

// Reads the active password policy from the server once and shares it (rules/16 usePolicy).
let cached: PasswordSummary | null = null;
let inflight: Promise<PasswordSummary> | null = null;

export function invalidatePolicy(): void {
  cached = null;
  inflight = null;
}

function load(): Promise<PasswordSummary> {
  if (cached) return Promise.resolve(cached);
  if (!inflight) {
    inflight = endpoints
      .passwordSummary()
      .then((summary) => {
        cached = summary;
        return summary;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

export function usePasswordPolicy(enabled = true): PasswordSummary | null {
  const [policy, setPolicy] = useState<PasswordSummary | null>(cached);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    load()
      .then((p) => alive && setPolicy(p))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [enabled]);
  return policy;
}
