import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, endpoints } from "../api/client";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";
import { Dialog } from "./Dialog";
import { useNotify } from "./Notify";
import { PasswordField } from "./PasswordField";

/** Voluntary, expired and forced first-login changes all use this one dialog (PWD-038, IDN-001). */
export function ChangePasswordDialog({ open, forced, onClose }: { open: boolean; forced: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const { session, refresh } = useSession();
  const notify = useNotify();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [valid, setValid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const submit = async () => {
    setBusy(true);
    setErrors([]);
    try {
      await endpoints.changePassword(current, next);
      notify.success(t("auth.password_changed"));
      setCurrent("");
      setNext("");
      await refresh();
      onClose();
    } catch (e) {
      setErrors(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={forced ? t("auth.change_required_title") : t("auth.change_password")}
      description={forced ? t("auth.change_required_text") : undefined}
      dismissible={!forced}
      primary={{ label: t("auth.change_password_submit"), onClick: () => void submit(), busy, disabled: !valid || !current }}
    >
      {errors.length > 0 && (
        <div className="banner banner--error" role="alert">
          <ul>
            {errors.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      <PasswordField
        variant="current"
        label={t("auth.current_password")}
        value={current}
        onChange={setCurrent}
      />
      <PasswordField
        variant="new"
        label={t("auth.new_password")}
        value={next}
        onChange={setNext}
        username={session?.user?.username}
        defaultMode="custom"
        onValidChange={setValid}
      />
    </Dialog>
  );
}
