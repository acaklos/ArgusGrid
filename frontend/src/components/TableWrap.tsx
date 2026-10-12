import { ReactNode } from "react";
import { useTranslation } from "react-i18next";

/**
 * Horizontally scrollable table area. It is a focusable, labelled region so keyboard users can scroll it
 * (WCAG 2.1.1); every table of the application sits in one (rules/16: one component, no variants).
 */
export function TableWrap({ children, card = false, label }: { children: ReactNode; card?: boolean; label?: string }) {
  const { t } = useTranslation();
  return (
    <div className={`${card ? "card " : ""}table-wrap`} role="region" tabIndex={0} aria-label={label ?? t("common.table")}>
      {children}
    </div>
  );
}
