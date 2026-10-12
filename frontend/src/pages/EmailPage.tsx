import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, EmailSettings, endpoints, OutboxRow, TemplateDetail, TemplateSummary } from "../api/client";
import { CheckboxField, NumberField, SelectField, TextAreaField, TextField } from "../components/Field";
import { useNotify } from "../components/Notify";
import { PasswordField } from "../components/PasswordField";
import { Tabs } from "../components/Tabs";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";
import { fieldErrors } from "../state/useLoad";
import { TableWrap } from "../components/TableWrap";

function Problems({ messages }: { messages: string[] }) {
  const { t } = useTranslation();
  if (messages.length === 0) return null;
  return (
    <div className="banner banner--error" role="alert">
      <strong>{t("settings.inconsistent")}</strong>
      <ul>{messages.map((m) => <li key={m}>{m}</li>)}</ul>
    </div>
  );
}

// ---- Server tab ---------------------------------------------------------------------------------
function ServerTab() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("settings.email.edit");
  const [settings, setSettings] = useState<EmailSettings | null>(null);
  const [password, setPassword] = useState("");
  const [testTo, setTestTo] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [perField, setPerField] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    void endpoints.getEmail().then(setSettings).catch(() => undefined);
  }, []);
  if (!settings) return <p>{t("common.loading")}</p>;

  const set = <K extends keyof EmailSettings>(key: K, value: EmailSettings[K]) => setSettings({ ...settings, [key]: value });
  const err = (f: string) => perField[f]?.join("; ");

  const save = async () => {
    setBusy(true);
    setProblems([]);
    setPerField({});
    try {
      const { password_set: _ignored, ...rest } = settings;
      const saved = await endpoints.putEmail({ ...rest, ...(password ? { password } : {}) });
      setSettings(saved);
      setPassword("");
      notify.success(t("settings.saved"));
    } catch (e) {
      if (e instanceof ApiError) {
        setProblems(errorMessages(t, e));
        setPerField(fieldErrors(e.details, (c) => t(`errors.${c}`, { defaultValue: c })));
      }
      notify.error(t("settings.not_saved"));
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    setTestResult(null);
    try {
      const r = await endpoints.testEmail(testTo);
      setTestResult(r.status === "sent" ? t("email.test_sent") : t("email.test_failed", { error: r.error }));
    } catch (e) {
      setTestResult(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Problems messages={problems} />
      <form className="card" onSubmit={(e) => { e.preventDefault(); void save(); }}>
        <CheckboxField label={t("email.enabled")} checked={settings.enabled} disabled={!editable}
          error={err("enabled")} onChange={(e) => set("enabled", e.target.checked)} />
        <div className="grid-2">
          <TextField label={t("email.host")} value={settings.host} disabled={!editable} error={err("host")}
            onChange={(e) => set("host", e.target.value)} autoComplete="off" />
          <NumberField label={t("email.port")} value={settings.port} disabled={!editable} error={err("port")}
            onChange={(e) => set("port", Number(e.target.value))} />
          <SelectField label={t("email.tls_mode")} value={settings.tls_mode} disabled={!editable} error={err("tls_mode")}
            onChange={(e) => set("tls_mode", e.target.value as EmailSettings["tls_mode"])}
            options={[
              { value: "starttls", label: "STARTTLS" },
              { value: "ssl", label: "SSL/TLS" },
              { value: "none", label: t("email.tls_none") },
            ]} />
          <TextField label={t("email.username")} value={settings.username} disabled={!editable} error={err("username")}
            onChange={(e) => set("username", e.target.value)} autoComplete="off" />
          <PasswordField variant="secret" label={t("email.password")} value={password} onChange={setPassword}
            disabled={!editable} error={err("password")}
            placeholder={settings.password_set ? t("email.password_kept") : ""} />
          <TextField label={t("email.from_address")} value={settings.from_address} disabled={!editable}
            error={err("from_address")} onChange={(e) => set("from_address", e.target.value)} autoComplete="off" />
          <TextField label={t("email.from_name")} value={settings.from_name} disabled={!editable}
            onChange={(e) => set("from_name", e.target.value)} />
          <TextField label={t("email.login_url")} help={t("email.login_url_help")} value={settings.login_url}
            disabled={!editable} onChange={(e) => set("login_url", e.target.value)} />
        </div>
        {editable && (
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? t("common.working") : t("common.save")}
          </button>
        )}
      </form>

      {editable && (
        <section className="card" aria-label={t("email.test_title")}>
          <h2>{t("email.test_title")}</h2>
          <TextField label={t("email.test_to")} help={t("email.test_to_help")} value={testTo}
            onChange={(e) => setTestTo(e.target.value)} autoComplete="off" />
          <button type="button" className="btn" disabled={busy} onClick={() => void test()}>{t("email.test_send")}</button>
          {testResult && <p role="status" style={{ marginTop: 16 }}>{testResult}</p>}
        </section>
      )}
    </>
  );
}

// ---- Templates tab ------------------------------------------------------------------------------
function TemplatesTab() {
  const { t, i18n } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const editable = can("settings.email.templates.edit");
  const [list, setList] = useState<TemplateSummary[]>([]);
  const [key, setKey] = useState("");
  const [locale, setLocale] = useState(i18n.language.startsWith("sk") ? "sk" : "en");
  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [subject, setSubject] = useState("");
  const [text, setText] = useState("");
  const [html, setHtml] = useState("");
  const [preview, setPreview] = useState<{ subject: string; text: string; html: string } | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const loadList = useCallback(() => void endpoints.templates().then(setList).catch(() => undefined), []);
  useEffect(() => loadList(), [loadList]);
  useEffect(() => {
    if (!key && list.length > 0) setKey(list[0].key);
  }, [list, key]);

  const loadDetail = useCallback(async () => {
    if (!key) return;
    const d = await endpoints.template(key, locale);
    setDetail(d);
    setSubject(d.subject);
    setText(d.body_text);
    setHtml(d.body_html);
    setPreview(null);
    setProblems([]);
  }, [key, locale]);
  useEffect(() => {
    void loadDetail().catch(() => undefined);
  }, [loadDetail]);

  const body = { subject, body_text: text, body_html: html };
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setProblems([]);
    try {
      await action();
    } catch (e) {
      setProblems(e instanceof ApiError ? errorMessages(t, e) : [t("errors.network_error")]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid-2">
      <section className="card" aria-label={t("email.templates")}>
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {list.map((item) => (
            <li key={item.key}>
              <button type="button" className="btn btn--ghost" style={{ width: "100%", justifyContent: "space-between" }}
                aria-pressed={item.key === key} onClick={() => setKey(item.key)}>
                <span>{item.title}</span>
                <span className="field__help mono">{item.key}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="card" aria-label={t("email.template_editor")}>
        {detail && (
          <>
            <div className="toolbar">
              <SelectField label={t("email.locale")} value={locale} onChange={(e) => setLocale(e.target.value)}
                options={[{ value: "en", label: "English" }, { value: "sk", label: "Slovenčina" }]} />
              <span className={`badge ${detail.customized ? "badge--warn" : ""}`}>
                {detail.customized ? t("email.customized", { version: detail.version }) : t("email.default")}
              </span>
            </div>
            <div className="chips" aria-label={t("email.variables")}>
              {detail.variables.map((v) => (
                <span key={v} className="chip">{`{{ ${v} }}`}</span>
              ))}
            </div>
            <Problems messages={problems} />
            <TextField label={t("email.subject")} value={subject} disabled={!editable}
              onChange={(e) => setSubject(e.target.value)} />
            <TextAreaField label={t("email.body_text")} value={text} disabled={!editable}
              onChange={(e) => setText(e.target.value)} />
            <TextAreaField label={t("email.body_html")} help={t("email.body_html_help")} value={html}
              disabled={!editable} onChange={(e) => setHtml(e.target.value)} />
            <div className="row-actions">
              <button type="button" className="btn" disabled={busy}
                onClick={() => void run(async () => setPreview(await endpoints.previewTemplate(key, locale, body)))}>
                {t("email.preview")}
              </button>
              {editable && (
                <button type="button" className="btn btn--primary" disabled={busy}
                  onClick={() => void run(async () => {
                    await endpoints.saveTemplate(key, locale, body);
                    notify.success(t("settings.saved"));
                    await loadDetail();
                    loadList();
                  })}>
                  {t("common.save")}
                </button>
              )}
              {editable && detail.customized && (
                <button type="button" className="btn btn--danger" disabled={busy}
                  onClick={() => void run(async () => {
                    await endpoints.resetTemplate(key, locale);
                    notify.success(t("email.reset_done"));
                    await loadDetail();
                    loadList();
                  })}>
                  {t("email.reset")}
                </button>
              )}
            </div>
            {preview && (
              <div style={{ marginTop: 16 }}>
                <h3>{preview.subject}</h3>
                {/* sandboxed frame: the preview HTML can never run script or reach the application */}
                <iframe className="preview" title={t("email.preview")} sandbox="" srcDoc={preview.html} />
              </div>
            )}
            {detail.versions.length > 0 && (
              <details style={{ marginTop: 16 }}>
                <summary>{t("email.versions")}</summary>
                <ul>
                  {detail.versions.map((v) => (
                    <li key={v.version}>
                      v{v.version} · {new Date(v.changed_at).toLocaleString()} · {v.changed_by}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
      </section>
    </div>
  );
}

// ---- Outbox tab ---------------------------------------------------------------------------------
function OutboxTab() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<OutboxRow[]>([]);
  useEffect(() => {
    void endpoints.outbox().then(setRows).catch(() => undefined);
  }, []);
  return (
    <TableWrap card>
      <table className="table">
        <thead>
          <tr>
            <th>{t("audit.when")}</th><th>{t("email.template")}</th><th>{t("email.to")}</th>
            <th>{t("email.status")}</th><th>{t("email.attempts")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={5}>{t("common.empty")}</td></tr>}
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{new Date(r.created_at).toLocaleString()}</td>
              <td className="mono">{r.template}</td>
              <td>{r.to}</td>
              <td>
                <span className={`badge ${r.status === "sent" ? "badge--ok" : r.status === "failed" ? "badge--bad" : "badge--warn"}`}>
                  {t(`email.status.${r.status}`, { defaultValue: r.status })}
                </span>
                {r.error && <span className="field__help"> {r.error}</span>}
              </td>
              <td>{r.attempts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

export function EmailPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState("server");
  return (
    <>
      <h1>{t("nav.email")}</h1>
      <Tabs
        label={t("nav.email")}
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "server", label: t("email.tab_server"), content: <ServerTab /> },
          { id: "templates", label: t("email.tab_templates"), content: <TemplatesTab /> },
          { id: "outbox", label: t("email.tab_outbox"), content: <OutboxTab /> },
        ]}
      />
    </>
  );
}
