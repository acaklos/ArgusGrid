import type { TFunction } from "i18next";
import { ApiError, ProblemDetail } from "../api/client";

/** Maps server error codes to catalogue messages. The server never sends raw text (rules/16 section 3). */
export function errorMessages(t: TFunction, error: ApiError): string[] {
  const details = error.details;
  // password.rejected: details is the list of all failed rule codes (PWD-006)
  if (error.code === "password.rejected" && Array.isArray(details)) {
    return (details as string[]).map((code) => t(`errors.${code}`, { defaultValue: code }));
  }
  // inconsistent policy: one message per problem, naming the settings involved
  if (Array.isArray(details) && details.length > 0 && typeof details[0] === "object") {
    return (details as ProblemDetail[]).map((p) => {
      const names = (p.fields ?? []).map((f) => t(`field.${f}`, { defaultValue: f })).join(", ");
      const scope = p.scope && p.scope !== "global" ? `[${p.scope}] ` : "";
      return `${scope}${t(`errors.${p.code}`, { defaultValue: p.code })}${names ? ` (${names})` : ""}`;
    });
  }
  return [t(`errors.${error.code}`, { defaultValue: t("errors.unknown") })];
}
