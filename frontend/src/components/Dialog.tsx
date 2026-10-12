import * as RadixDialog from "@radix-ui/react-dialog";
import { ReactNode } from "react";
import { useTranslation } from "react-i18next";

// One dialog layout: title, body, footer (primary right, cancel left), focus trap, Escape closes.
export interface DialogAction {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  danger?: boolean;
}

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  primary?: DialogAction;
  /** When absent, the dialog cannot be dismissed (forced password change). */
  dismissible?: boolean;
}

export function Dialog({ open, onOpenChange, title, description, children, primary, dismissible = true }: DialogProps) {
  const { t } = useTranslation();
  return (
    <RadixDialog.Root open={open} onOpenChange={(next) => (dismissible || next) && onOpenChange(next)}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="dialog__overlay" />
        <RadixDialog.Content
          className="dialog__content"
          onEscapeKeyDown={(e) => !dismissible && e.preventDefault()}
          onPointerDownOutside={(e) => !dismissible && e.preventDefault()}
          onInteractOutside={(e) => !dismissible && e.preventDefault()}
        >
          <RadixDialog.Title asChild>
            <h2>{title}</h2>
          </RadixDialog.Title>
          {description ? (
            <RadixDialog.Description>{description}</RadixDialog.Description>
          ) : (
            <RadixDialog.Description className="sr-only">{title}</RadixDialog.Description>
          )}
          {children}
          <div className={`dialog__footer${dismissible ? "" : " dialog__footer--end"}`}>
            {dismissible && (
              <button type="button" className="btn" onClick={() => onOpenChange(false)}>
                {t("common.cancel")}
              </button>
            )}
            {primary && (
              <button
                type="button"
                className={`btn ${primary.danger ? "btn--danger" : "btn--primary"}`}
                onClick={primary.onClick}
                disabled={primary.disabled || primary.busy}
              >
                {primary.busy ? t("common.working") : primary.label}
              </button>
            )}
          </div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
