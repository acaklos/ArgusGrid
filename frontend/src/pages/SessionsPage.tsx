import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, endpoints } from "../api/client";
import { NumberField } from "../components/Field";
import { useNotify } from "../components/Notify";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";
import { useLoad } from "../state/useLoad";

export function SessionsPage() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("policy.session.edit");
  const { data, setData, error, loading } = useLoad(endpoints.getSessionPolicy);
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  if (loading) return <p>{t("common.loading")}</p>;
  if (error || !data) return <div className="banner banner--error">{t(`errors.${error?.code ?? "unknown"}`)}</div>;

  const save = async () => {
    setBusy(true);
    setProblems([]);
    try {
      setData(await endpoints.putSessionPolicy(data));
      notify.success(t("settings.saved"));
    } catch (e) {
      if (e instanceof ApiError) setProblems(errorMessages(t, e));
      notify.error(t("settings.not_saved"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1>{t("nav.sessions")}</h1>
      {problems.length > 0 && (
        <div className="banner banner--error" role="alert">
          <ul>
            {problems.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      <form className="card" onSubmit={(e) => { e.preventDefault(); void save(); }}>
        <div className="grid-2">
          <NumberField
            label={t("field.inactivity_minutes")}
            help={t("help.inactivity_minutes")}
            value={data.inactivity_minutes}
            disabled={!editable}
            onChange={(e) => setData({ ...data, inactivity_minutes: Number(e.target.value) })}
          />
          <NumberField
            label={t("field.absolute_hours")}
            help={t("help.absolute_hours")}
            value={data.absolute_hours}
            disabled={!editable}
            onChange={(e) => setData({ ...data, absolute_hours: Number(e.target.value) })}
          />
        </div>
        {editable && (
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? t("common.working") : t("common.save")}
          </button>
        )}
      </form>
    </>
  );
}
