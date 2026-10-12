import { useTranslation } from "react-i18next";
import { useSession } from "./session";

/**
 * Terminology of the deployment profile (ARG-021): the same key with the profile as i18next context,
 * for example `nav.map_defense`; a key without such a variant falls back to the plain text.
 */
export function useTerm(): (key: string) => string {
  const { t } = useTranslation();
  const { session } = useSession();
  const profile = session?.profile?.name ?? "civil";
  return (key: string) => t(key, { context: profile === "defense" ? "defense" : undefined });
}
