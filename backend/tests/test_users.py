"""User management through the API (ARG-005, ARG-006, ARG-011; T-IDN-10 to T-IDN-12)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.mail import MailOutbox
from tests.conftest import Env

GOOD = "Aa1!bcdefghijkl"


def client_for(env: Env, username: str, password: str = GOOD):  # type: ignore[no-untyped-def]
    c = env.new_client()
    r = env.login(username, password, c)
    assert r.status_code == 200, r.text
    return c, env.csrf(c)


def new_user_body(**over):  # type: ignore[no-untyped-def]
    body = {"username": "alice.smith", "email": "alice@example.test", "full_name": "Alice Smith",
            "role": "SOC Analyst", "locale": "en", "password": "Tr9#kLm2!pQw7zXv", "send_email": True}
    body.update(over)
    return body


def make_custom_role(env: Env, name: str, level: int, caps: list[str]) -> None:
    from app.models.identity import Role, RolePermission

    with env.services() as svc:
        role = Role(name=name, description="", security_level=level, is_system=False)
        role.permissions = [RolePermission(permission=c) for c in caps]
        svc.session.add(role)


# -- create ------------------------------------------------------------------------------------------
def test_admin_creates_a_user_and_the_credentials_mail_is_queued_encrypted(admin_session: Env):
    env = admin_session
    r = env.client.post("/api/v1/users", json=new_user_body(), headers=env.csrf())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "alice.smith" and body["must_change_password"] is True
    assert body["email_queued"] is True and body["email_configured"] is False
    assert "password" not in body and "password_hash" not in body
    with env.services() as svc:
        row = svc.session.execute(select(MailOutbox)).scalar_one()
        assert row.template_key == "user.created" and row.to_address == "alice@example.test"
        assert row.sensitive and row.body_text.startswith("enc1:")
        assert "Tr9#kLm2!pQw7zXv" not in row.body_text + row.body_html + row.subject
        assert svc.audit.verify_chain()
    # the new user signs in and is forced to change the temporary password
    c = env.new_client()
    login = env.login("alice.smith", "Tr9#kLm2!pQw7zXv", c)
    assert login.json()["must_change_password"] is True


def test_create_validates_fields_policy_and_uniqueness(admin_session: Env):
    env = admin_session
    h = env.csrf()
    r = env.client.post("/api/v1/users", json=new_user_body(username="x", email="nope"), headers=h)
    assert r.status_code == 422
    codes = {p["code"] for p in r.json()["details"]}
    assert {"user.username_invalid", "user.email_invalid"} <= codes
    weak = env.client.post("/api/v1/users", json=new_user_body(password="short"), headers=h)
    assert weak.status_code == 422 and weak.json()["code"] == "password.rejected"
    assert env.client.post("/api/v1/users", json=new_user_body(), headers=h).status_code == 201
    dup = env.client.post("/api/v1/users", json=new_user_body(email="other@example.test"), headers=h)
    assert dup.status_code == 409 and dup.json()["code"] == "user.username_taken"
    bad_role = env.client.post("/api/v1/users", json=new_user_body(username="bob.jones", role="Nope"), headers=h)
    assert bad_role.status_code == 422


def test_unknown_fields_are_rejected_on_update_no_mass_assignment(admin_session: Env):
    env = admin_session
    created = env.client.post("/api/v1/users", json=new_user_body(), headers=env.csrf()).json()
    r = env.client.put(f"/api/v1/users/{created['id']}", json={"password_hash": "x", "is_service": True},
                       headers=env.csrf())
    assert r.status_code == 422 and r.json()["code"] == "user.invalid"


def test_update_records_old_and_new_values_and_role_change_ends_sessions(admin_session: Env):
    env = admin_session
    created = env.client.post("/api/v1/users", json=new_user_body(), headers=env.csrf()).json()
    alice, _ = client_for(env, "alice.smith", "Tr9#kLm2!pQw7zXv")
    assert alice.get("/api/v1/auth/session").json()["authenticated"] is True
    r = env.client.put(f"/api/v1/users/{created['id']}",
                       json={"role": "SOC Operator", "full_name": "Alice S."}, headers=env.csrf())
    assert r.status_code == 200 and r.json()["role"] == "SOC Operator"
    assert alice.get("/api/v1/auth/session").json()["authenticated"] is False
    with env.services() as svc:
        from app.models.system import AuditRecord

        row = svc.session.execute(select(AuditRecord).where(AuditRecord.action == "user.update")).scalar_one()
    assert row.changes["role"] == {"old": "SOC Analyst", "new": "SOC Operator"}
    assert row.changes["full_name"] == {"old": "Alice Smith", "new": "Alice S."}


# -- hidden administrators (T-IDN-10 to T-IDN-12) ------------------------------------------------------
def test_lower_roles_never_see_administrator_accounts(admin_session: Env):
    env = admin_session
    env.make_user("mgr", "SOC Manager")
    admin_id = env.client.get("/api/v1/users", params={"search": "sysadmin"}).json()["items"][0]["id"]
    total_admin_view = env.client.get("/api/v1/users").json()["total"]

    mgr, h = client_for(env, "mgr")
    listing = mgr.get("/api/v1/users").json()
    names = [u["username"] for u in listing["items"]]
    assert "sysadmin" not in names and "mgr" in names
    assert listing["total"] == total_admin_view - 1  # IDN-033: totals exclude hidden accounts
    assert mgr.get("/api/v1/users", params={"search": "sysadmin"}).json()["items"] == []
    assert mgr.get("/api/v1/users", params={"role": "Administrator"}).json()["items"] == []
    assert mgr.get(f"/api/v1/users/{admin_id}").status_code == 404
    # every operation answers for an administrator exactly as it does for an id that does not exist
    missing_id = 999999
    for call in (
        lambda uid: mgr.put(f"/api/v1/users/{uid}", json={"full_name": "x"}, headers=h),
        lambda uid: mgr.post(f"/api/v1/users/{uid}/lock", json={}, headers=h),
        lambda uid: mgr.post(f"/api/v1/users/{uid}/unlock", headers=h),
        lambda uid: mgr.post(f"/api/v1/users/{uid}/reset-password", json={"password": "Ww3!xYz9#abcDef"}, headers=h),
        lambda uid: mgr.delete(f"/api/v1/users/{uid}", headers=h),
    ):
        hidden, missing = call(admin_id), call(missing_id)
        assert hidden.status_code == missing.status_code, (hidden.status_code, missing.status_code)
        assert hidden.content == missing.content
    # the operations the manager may perform answer "not found", never "forbidden"
    assert mgr.put(f"/api/v1/users/{admin_id}", json={"full_name": "x"}, headers=h).status_code == 404
    assert mgr.post(f"/api/v1/users/{admin_id}/unlock", headers=h).status_code == 404
    roles = [r["name"] for r in mgr.get("/api/v1/users/roles").json()]
    assert "Administrator" not in roles
    made = mgr.post("/api/v1/users", json=new_user_body(role="Administrator"), headers=h)
    assert made.status_code == 422 and "administrator" not in made.text.lower()


def test_404_for_hidden_and_for_missing_look_the_same(admin_session: Env):
    env = admin_session
    env.make_user("mgr", "SOC Manager")
    admin_id = env.client.get("/api/v1/users", params={"search": "sysadmin"}).json()["items"][0]["id"]
    mgr, _ = client_for(env, "mgr")
    hidden = mgr.get(f"/api/v1/users/{admin_id}")
    missing = mgr.get("/api/v1/users/999999")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()


def test_edit_does_not_imply_lock_or_reset(admin_session: Env):
    env = admin_session
    make_custom_role(env, "Editor", 50, ["user.view", "user.edit"])
    env.make_user("ed", "Editor")
    env.make_user("victim", "SOC Operator")
    vid = env.client.get("/api/v1/users", params={"search": "victim"}).json()["items"][0]["id"]
    ed, h = client_for(env, "ed")
    assert ed.put(f"/api/v1/users/{vid}", json={"full_name": "Edited"}, headers=h).status_code == 200
    assert ed.post(f"/api/v1/users/{vid}/lock", json={}, headers=h).status_code == 403
    assert ed.post(f"/api/v1/users/{vid}/reset-password", json={"password": "Ww3!xYz9#abcDef"},
                   headers=h).status_code == 403
    assert ed.delete(f"/api/v1/users/{vid}", headers=h).status_code == 403


def test_a_lower_level_role_cannot_manage_a_higher_level_user(admin_session: Env):
    env = admin_session
    make_custom_role(env, "Junior", 30, ["user.view", "user.edit"])
    env.make_user("jr", "Junior")
    env.make_user("senior", "SOC Analyst")  # level 60 > 30
    sid = env.client.get("/api/v1/users", params={"search": "senior"}).json()["items"][0]["id"]
    jr, h = client_for(env, "jr")
    assert jr.put(f"/api/v1/users/{sid}", json={"full_name": "x"}, headers=h).status_code == 404


# -- protections ---------------------------------------------------------------------------------------
def test_last_administrator_and_self_protection(admin_session: Env):
    env = admin_session
    me = env.client.get("/api/v1/users", params={"search": env.admin_username}).json()["items"][0]["id"]
    h = env.csrf()
    assert env.client.delete(f"/api/v1/users/{me}", headers=h).status_code == 403  # self
    assert env.client.post(f"/api/v1/users/{me}/lock", json={}, headers=h).status_code == 403  # LCK-017
    assert env.client.put(f"/api/v1/users/{me}", json={"is_active": False}, headers=h).status_code == 403
    assert env.client.put(f"/api/v1/users/{me}", json={"role": "SOC Manager"}, headers=h).status_code == 403
    assert env.client.post(f"/api/v1/users/{me}/reset-password", json={"password": "Ww3!xYz9#abcDef"},
                           headers=h).status_code == 403
    # a second administrator exists, then the first one is "not the last", but the remaining one is
    env.make_user("boss", "Administrator")
    boss_id = env.client.get("/api/v1/users", params={"search": "boss"}).json()["items"][0]["id"]
    boss, bh = client_for(env, "boss")
    assert boss.put(f"/api/v1/users/{me}", json={"is_active": False}, headers=bh).status_code == 200
    # now boss is the last active administrator
    assert boss.put(f"/api/v1/users/{boss_id}", json={"role": "SOC Manager"}, headers=bh).status_code in (403, 409)


# -- lock, unlock, reset -------------------------------------------------------------------------------
def test_manual_lock_unlock_and_policy_unlockers(admin_session: Env):
    env = admin_session
    env.make_user("mgr", "SOC Manager")
    env.make_user("alice", "SOC Analyst")
    aid = env.client.get("/api/v1/users", params={"search": "alice"}).json()["items"][0]["id"]
    h = env.csrf()
    locked = env.client.post(f"/api/v1/users/{aid}/lock", json={"reason": "investigation"}, headers=h)
    assert locked.status_code == 200
    assert locked.json()["lock"] == {"state": "locked_permanent", "manual": True, "until": None}
    assert env.login("alice", GOOD, env.new_client()).status_code == 401

    mgr, mh = client_for(env, "mgr")  # holds user.unlock but is not in the policy's unlockers
    assert mgr.post(f"/api/v1/users/{aid}/unlock", headers=mh).status_code == 403
    ok = env.client.post(f"/api/v1/users/{aid}/unlock", headers=h)
    assert ok.status_code == 200 and ok.json()["lock"]["state"] == "active"
    assert env.login("alice", GOOD, env.new_client()).status_code == 200


def test_unlock_with_reset_sends_a_new_password_by_mail(admin_session: Env):
    env = admin_session
    env.make_user("alice", "SOC Analyst")
    aid = env.client.get("/api/v1/users", params={"search": "alice"}).json()["items"][0]["id"]
    h = env.csrf()
    policy = env.client.get("/api/v1/settings/lockout").json()["settings"]
    policy["default"]["after_unlock"] = "reset_password"
    assert env.client.put("/api/v1/settings/lockout", json=policy, headers=h).status_code == 200
    env.client.post(f"/api/v1/users/{aid}/lock", json={}, headers=h)
    r = env.client.post(f"/api/v1/users/{aid}/unlock", headers=h)
    body = r.json()
    assert r.status_code == 200 and body["after_unlock"] == "reset_password" and body["email_queued"] is True
    assert "temporary_password" not in body  # the user has an address: only the mail carries it
    with env.services() as svc:
        row = svc.session.execute(
            select(MailOutbox).where(MailOutbox.template_key == "user.unlocked")
        ).scalar_one()
        assert row.sensitive and row.body_text.startswith("enc1:")
    assert env.login("alice", GOOD, env.new_client()).status_code == 401  # old password replaced


def test_reset_password_revokes_sessions_and_forces_a_change(admin_session: Env):
    env = admin_session
    env.make_user("alice", "SOC Analyst")
    alice, _ = client_for(env, "alice")
    aid = env.client.get("/api/v1/users", params={"search": "alice"}).json()["items"][0]["id"]
    r = env.client.post(f"/api/v1/users/{aid}/reset-password", json={"password": "Ww3!xYz9#abcDef"},
                        headers=env.csrf())
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    assert alice.get("/api/v1/auth/session").json()["authenticated"] is False
    c = env.new_client()
    assert env.login("alice", "Ww3!xYz9#abcDef", c).json()["must_change_password"] is True
    weak = env.client.post(f"/api/v1/users/{aid}/reset-password", json={"password": "weak"}, headers=env.csrf())
    assert weak.status_code == 422 and weak.json()["code"] == "password.rejected"


def test_account_lock_notifies_the_user_and_other_administrators(admin_session: Env):
    env = admin_session
    env.make_user("alice", "SOC Analyst")
    for _ in range(5):
        env.login("alice", "wrong-password-xyz", env.new_client())
    with env.services() as svc:
        keys = list(svc.session.execute(select(MailOutbox.template_key)).scalars())
    assert "user.locked" in keys


def test_delete_user(admin_session: Env):
    env = admin_session
    env.make_user("alice", "SOC Analyst")
    aid = env.client.get("/api/v1/users", params={"search": "alice"}).json()["items"][0]["id"]
    assert env.client.delete(f"/api/v1/users/{aid}", headers=env.csrf()).status_code == 204
    assert env.client.get(f"/api/v1/users/{aid}").status_code == 404
    assert "user.delete" in env.audit_actions()


def test_pagination_and_search(admin_session: Env):
    env = admin_session
    for i in range(7):
        env.make_user(f"user{i:02d}", "SOC Operator")
    page = env.client.get("/api/v1/users", params={"page": 1, "page_size": 5}).json()
    assert len(page["items"]) == 5 and page["total"] == 8
    page2 = env.client.get("/api/v1/users", params={"page": 2, "page_size": 5}).json()
    assert len(page2["items"]) == 3
    assert [u["username"] for u in env.client.get("/api/v1/users", params={"search": "user03"}).json()["items"]] \
        == ["user03"]


@pytest.mark.parametrize("path", ["/api/v1/users", "/api/v1/roles", "/api/v1/audit", "/api/v1/settings/email"])
def test_endpoints_require_a_session(env: Env, path: str):
    assert env.client.get(path).status_code == 401


def test_roles_without_capability_are_forbidden(env: Env):
    env.make_user("op", "SOC Operator")
    c, h = client_for(env, "op")
    for path in ("/api/v1/users", "/api/v1/roles", "/api/v1/audit", "/api/v1/settings/email"):
        assert c.get(path).status_code == 403, path
    assert c.post("/api/v1/users", json=new_user_body(), headers=h).status_code == 403
