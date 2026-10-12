import type { TFunction } from "i18next";
import type { IncidentDto } from "../api/client";

/**
 * Title of an incident in the language of the user. The server stores an English title for logs and e-mail;
 * the screens build theirs from the structured fields so that the catalogue translates it.
 */
export function incidentTitle(t: TFunction, inc: Pick<IncidentDto, "type" | "track_id" | "link_asset" | "primary_asset" | "zone" | "title">): string {
  const asset = inc.primary_asset ?? "";
  if (inc.type === "hybrid" && inc.track_id && asset) {
    return inc.link_asset
      ? t("incident.title.hybrid_via", { track: inc.track_id, link: inc.link_asset, asset })
      : t("incident.title.hybrid", { track: inc.track_id, asset });
  }
  if (inc.type === "physical" && inc.track_id) return t("incident.title.physical", { track: inc.track_id, zone: inc.zone ?? "" });
  if (inc.type === "cyber" && asset) return t("incident.title.cyber", { asset });
  return inc.title;
}
