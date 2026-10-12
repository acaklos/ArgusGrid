import { Dialog } from "./Dialog";

// Application-styled confirmation for delete and security-sensitive changes. Browser alerts are forbidden.
interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ open, title, message, confirmLabel, danger, busy, onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && onCancel()}
      title={title}
      description={message}
      primary={{ label: confirmLabel, onClick: onConfirm, busy, danger }}
    />
  );
}
