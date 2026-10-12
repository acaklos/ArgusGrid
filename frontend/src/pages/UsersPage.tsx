import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, endpoints, Page, UserDto } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Column, DataTable } from "../components/DataTable";
import { useNotify } from "../components/Notify";
import { SearchFilter } from "../components/SearchFilter";
import { CreateUserDialog, EditUserDialog, ResetPasswordDialog } from "../components/UserDialogs";
import { errorMessages } from "../i18n/errors";
import { useSession } from "../state/session";

type Pending = { kind: "delete" | "lock" | "unlock"; user: UserDto } | null;

function LockBadge({ user }: { user: UserDto }) {
  const { t } = useTranslation();
  if (!user.is_active) return <span className="badge badge--warn">{t("users.inactive")}</span>;
  if (user.lock.state === "locked_permanent") {
    return (
      <span className="badge badge--bad">
        {user.lock.manual ? t("users.locked_manual") : t("users.locked_permanent")}
      </span>
    );
  }
  if (user.lock.state === "locked_temporary" && user.lock.until) {
    return (
      <span className="badge badge--warn">
        {t("users.locked_until", { time: new Date(user.lock.until).toLocaleTimeString() })}
      </span>
    );
  }
  return <span className="badge badge--ok">{t("users.active_state")}</span>;
}

export function UsersPage() {
  const { t } = useTranslation();
  const notify = useNotify();
  const { can } = useSession();
  const [data, setData] = useState<Page<UserDto> | null>(null);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<UserDto | null>(null);
  const [resetting, setResetting] = useState<UserDto | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await endpoints.listUsers({ search, role, page, page_size: pageSize }));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    }
  }, [search, role, page, pageSize, t]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    void endpoints.assignableRoles().then((r) => setRoles(r.map((x) => x.name))).catch(() => undefined);
  }, []);

  const runPending = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      if (pending.kind === "delete") await endpoints.deleteUser(pending.user.id);
      if (pending.kind === "lock") await endpoints.lockUser(pending.user.id, "");
      if (pending.kind === "unlock") {
        const r = await endpoints.unlockUser(pending.user.id);
        if (r.temporary_password) notify.warning(t("users.temp_password_handover", { password: r.temporary_password }));
      }
      notify.success(t(`users.${pending.kind}_done`, { username: pending.user.username }));
      setPending(null);
      await load();
    } catch (e) {
      notify.error(e instanceof ApiError ? errorMessages(t, e)[0] : t("errors.network_error"));
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<UserDto>[] = [
    { key: "username", header: t("auth.username"), render: (u) => <span className="mono">{u.username}</span> },
    {
      key: "person", header: t("users.person"),
      render: (u) => (
        <>
          {u.full_name || "—"}
          <br />
          <span className="field__help">{u.email}</span>
        </>
      ),
    },
    { key: "role", header: t("users.role"), render: (u) => u.role },
    { key: "state", header: t("users.state"), render: (u) => <LockBadge user={u} /> },
    {
      key: "last", header: t("users.last_login"),
      render: (u) => (u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"),
    },
    {
      key: "actions", header: t("users.actions"),
      render: (u) => {
        const locked = u.lock.state !== "active";
        return (
          <div className="row-actions">
            {can("user.edit") && (
              <button type="button" className="btn btn--small" onClick={() => setEditing(u)}>{t("users.edit_short")}</button>
            )}
            {can("user.reset_password") && (
              <button type="button" className="btn btn--small" onClick={() => setResetting(u)}>{t("users.reset_short")}</button>
            )}
            {locked && can("user.unlock") && (
              <button type="button" className="btn btn--small" onClick={() => setPending({ kind: "unlock", user: u })}>
                {t("users.unlock")}
              </button>
            )}
            {!locked && can("user.lock") && (
              <button type="button" className="btn btn--small" onClick={() => setPending({ kind: "lock", user: u })}>
                {t("users.lock")}
              </button>
            )}
            {can("user.delete") && (
              <button type="button" className="btn btn--small btn--danger"
                onClick={() => setPending({ kind: "delete", user: u })}>
                {t("users.delete")}
              </button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <>
      <h1>{t("nav.users")}</h1>
      {error && <div className="banner banner--error" role="alert">{error}</div>}
      <div className="toolbar">
        <SearchFilter value={search} onChange={(v) => { setSearch(v); setPage(1); }} label={t("users.search")} />
        <label>
          <span className="sr-only">{t("users.role")}</span>
          <select className="select" value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
            <option value="">{t("users.all_roles")}</option>
            {roles.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </label>
        {can("user.create") && (
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>{t("users.create")}</button>
        )}
      </div>
      <div className="card">
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(u) => u.id}
          rowClassName={(u) => (u.is_active ? undefined : "row--muted")}
          paging={{ page, pageSize, total: data?.total ?? 0, onChange: (p, s) => { setPage(p); setPageSize(s); } }}
        />
      </div>

      <CreateUserDialog open={creating} onClose={() => setCreating(false)} onDone={() => void load()} />
      <EditUserDialog user={editing} onClose={() => setEditing(null)} onDone={() => void load()}
        canAssignRole={can("user.role.assign")} />
      <ResetPasswordDialog user={resetting} onClose={() => setResetting(null)} onDone={() => void load()} />
      <ConfirmDialog
        open={!!pending}
        title={pending ? t(`users.${pending.kind}_title`, { username: pending.user.username }) : ""}
        message={pending ? t(`users.${pending.kind}_text`, { username: pending.user.username }) : ""}
        confirmLabel={pending ? t(`users.${pending.kind}`) : ""}
        danger={pending?.kind === "delete"}
        busy={busy}
        onConfirm={() => void runPending()}
        onCancel={() => setPending(null)}
      />
    </>
  );
}
