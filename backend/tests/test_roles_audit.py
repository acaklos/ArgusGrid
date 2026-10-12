"""Role administration and audit viewing/export (IDN-004, IDN-006, ARG-009, IDN-031 for audit views)."""
from __future__ import annotations

import csv
import io

from tests.conftest import Env

GOOD = "Aa1!bcdefghijkl"


def client_for(env: Env, username: str):  # type: ignore[no-untyped-def]
    c = env.new_client()
    assert env.login(username, GOOD, c).status_code == 200
    return c, env.csrf(c)


# -- roles -------------------------------------------------------------------------------------------
def test_role_list_shows_capabilities_and_counts(admin_session: Env):
    env = admin_session
    data = env.client.get("/api/v1/roles").json()
    names = {r["name"]: r for r in data["roles"]}
    assert {"Administrator", "SOC Manager", "Device Agent"} <= set(names)
    assert names["Administrator"]["locked"] is True and names["Administrator"]["user_count"] == 1
    assert "user.create" in names["SOC Manager"]["capabilities"]
    assert "sensor.ingest" in data["capabilities"]


def test_capabilities_edit_at_runtime_takes_effect_and_ends_sessions(admin_session: Env):
    env = admin_session
    env.make_user("op", "SOC Operator")
    op, _ = client_for(env, "op")
    assert op.get("/api/v1/auth/session").json()["authenticated"] is True
    role = next(r for r in env.client.get("/api/v1/roles").json()["roles"] if r["name"] == "SOC Operator")
    caps = [c for c in role["capabilities"] if c != "incident.triage"]
    r = env.client.put(f"/api/v1/roles/{role['id']}", json={"capabilities": caps}, headers=env.csrf())
    assert r.status_code == 200 and "incident.triage" not in r.json()["capabilities"]
    assert op.get("/api/v1/auth/session").json()["authenticated"] is False  # reduction ends the sessions
    c, _ = client_for(env, "op")
    assert "incident.triage" not in c.get("/api/v1/auth/session").json()["capabilities"]
    with env.services() as svc:
        from sqlalchemy import select

        from app.models.system import AuditRecord

        row = svc.session.execute(select(AuditRecord).where(AuditRecord.action == "role.update")).scalar_one()
    assert row.changes["capabilities"]["old"] != row.changes["capabilities"]["new"]


def test_administrator_role_is_fixed_and_device_capability_is_restricted(admin_session: Env):
    env = admin_session
    roles = {r["name"]: r for r in env.client.get("/api/v1/roles").json()["roles"]}
    h = env.csrf()
    fixed = env.client.put(f"/api/v1/roles/{roles['Administrator']['id']}", json={"capabilities": []}, headers=h)
    assert fixed.status_code == 409 and fixed.json()["code"] == "role.administrator_fixed"
    device = env.client.put(f"/api/v1/roles/{roles['Auditor']['id']}",
                            json={"capabilities": ["audit.view", "sensor.ingest"]}, headers=h)
    assert device.status_code == 422 and device.json()["details"][0]["code"] == "role.device_capability"
    unknown = env.client.put(f"/api/v1/roles/{roles['Auditor']['id']}", json={"capabilities": ["made.up"]}, headers=h)
    assert unknown.status_code == 422


def test_a_role_manager_cannot_hand_out_capabilities_they_lack(admin_session: Env):
    env = admin_session
    # a custom role that may manage roles but lacks audit.export
    r = env.client.post("/api/v1/roles", headers=env.csrf(),
                        json={"name": "Role Keeper", "description": "", "security_level": 70,
                              "capabilities": ["role.view", "role.manage", "user.view"]})
    assert r.status_code == 201
    env.make_user("keeper", "Role Keeper")
    keeper, h = client_for(env, "keeper")
    roles = {x["name"]: x for x in keeper.get("/api/v1/roles").json()["roles"]}
    assert "Administrator" not in roles  # hidden from lower roles
    esc = keeper.put(f"/api/v1/roles/{roles['SOC Operator']['id']}", headers=h,
                     json={"capabilities": ["incident.view", "audit.export"]})
    assert esc.status_code == 422 and esc.json()["details"][0]["code"] == "role.escalation"
    ok = keeper.put(f"/api/v1/roles/{roles['SOC Operator']['id']}", headers=h,
                    json={"capabilities": ["incident.view", "user.view"]})
    assert ok.status_code == 200


def test_role_create_delete_and_in_use(admin_session: Env):
    env = admin_session
    h = env.csrf()
    created = env.client.post("/api/v1/roles", headers=h, json={
        "name": "Shift Lead", "description": "demo", "security_level": 50, "capabilities": ["incident.view"]})
    assert created.status_code == 201
    rid = created.json()["id"]
    dup = env.client.post("/api/v1/roles", headers=h, json={
        "name": "shift lead", "description": "", "security_level": 50, "capabilities": []})
    assert dup.status_code == 409
    env.make_user("lead", "Shift Lead")
    assert env.client.delete(f"/api/v1/roles/{rid}", headers=h).json()["code"] == "role.in_use"
    uid = env.client.get("/api/v1/users", params={"search": "lead"}).json()["items"][0]["id"]
    env.client.delete(f"/api/v1/users/{uid}", headers=h)
    assert env.client.delete(f"/api/v1/roles/{rid}", headers=h).status_code == 204
    system = next(r for r in env.client.get("/api/v1/roles").json()["roles"] if r["name"] == "Auditor")
    assert env.client.delete(f"/api/v1/roles/{system['id']}", headers=h).json()["code"] == "role.system_role"


# -- audit -------------------------------------------------------------------------------------------
def test_audit_lists_with_filters_and_paging(admin_session: Env):
    env = admin_session
    env.make_user("op", "SOC Operator")
    env.login("op", GOOD, env.new_client())
    env.login("op", "wrong-password-xyz", env.new_client())
    page = env.client.get("/api/v1/audit", params={"page_size": 5}).json()
    assert page["total"] >= 5 and len(page["items"]) == 5
    assert page["items"][0]["id"] > page["items"][-1]["id"]  # newest first
    failed = env.client.get("/api/v1/audit", params={"result": "failure"}).json()
    assert failed["total"] >= 1 and all(i["result"] == "failure" for i in failed["items"])
    by_action = env.client.get("/api/v1/audit", params={"action": "auth.login"}).json()
    assert by_action["items"] and all(i["action"].startswith("auth.login") for i in by_action["items"])
    row = by_action["items"][0]
    assert {"ts", "actor", "channel", "source_ip", "action", "object_type", "result", "changes"} <= set(row)


def test_audit_never_contains_secrets_anywhere_in_the_api(admin_session: Env):
    env = admin_session
    created = env.client.post("/api/v1/users", headers=env.csrf(), json={
        "username": "carol.k", "email": "carol@example.test", "full_name": "Carol", "role": "SOC Analyst",
        "locale": "en", "password": "Kx8#mQ2!vLp5ZtWn", "send_email": True})
    assert created.status_code == 201
    env.client.post(f"/api/v1/users/{created.json()['id']}/reset-password", headers=env.csrf(),
                    json={"password": "Pq4!sRt7#uVw9XyZ"})
    everything = env.client.get("/api/v1/audit", params={"page_size": 200}).text + \
        env.client.get("/api/v1/audit/export").text
    assert "Kx8#mQ2!vLp5ZtWn" not in everything and "Pq4!sRt7#uVw9XyZ" not in everything
    assert env.admin_password not in everything


def test_audit_view_hides_administrator_accounts_and_names_for_lower_roles(admin_session: Env):
    env = admin_session
    env.make_user("aud", "Auditor")
    env.make_user("mgr", "SOC Manager")
    env.make_user("alice", "SOC Analyst")
    aid = env.client.get("/api/v1/users", params={"search": "alice"}).json()["items"][0]["id"]
    env.client.put(f"/api/v1/users/{aid}", json={"full_name": "Alice A."}, headers=env.csrf())

    aud, _ = client_for(env, "aud")
    items = aud.get("/api/v1/audit", params={"page_size": 200}).json()["items"]
    assert items
    assert all(i["actor"] != env.admin_username for i in items)  # actor shown as "System"
    assert not any(i["object_type"] == "user" and i["object_id"] == "1" for i in items)  # rows about the admin
    assert any(i["actor"] == "System" and i["action"] == "user.update" for i in items)
    assert env.admin_username not in aud.get("/api/v1/audit", params={"page_size": 200}).text
    # filtering by the administrator's name must not reveal anything
    by_name = aud.get("/api/v1/audit", params={"actor": env.admin_username}).json()
    assert by_name["items"] == []


def test_export_needs_its_own_capability_and_neutralises_formulas(admin_session: Env):
    env = admin_session
    env.make_user("aud", "Auditor")  # audit.export
    env.make_user("mgr", "SOC Manager")  # audit.view only
    env.client.post("/api/v1/users", headers=env.csrf(), json={
        "username": "dave.f", "email": "dave@example.test", "full_name": "=HYPERLINK(\"http://x\")",
        "role": "SOC Analyst", "locale": "en", "password": "Ab7!cDe4#fGh2Jkl", "send_email": False})
    mgr, _ = client_for(env, "mgr")
    assert mgr.get("/api/v1/audit/export").status_code == 403
    aud, _ = client_for(env, "aud")
    export = aud.get("/api/v1/audit/export")
    assert export.status_code == 200 and export.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(export.text)))
    assert rows[0][:3] == ["id", "timestamp_utc", "actor"]
    for row in rows[1:]:
        for cell in row:
            assert not cell.startswith(("=", "+", "@")), cell
    assert "audit.export" in env.audit_actions()


def test_audit_verify_endpoint(admin_session: Env):
    env = admin_session
    assert env.client.get("/api/v1/audit/verify").json() == {"intact": True}


def test_the_service_role_is_not_offered_or_accepted_for_people(admin_session):  # type: ignore[no-untyped-def]
    env = admin_session
    roles = env.client.get("/api/v1/users/roles")
    assert roles.status_code == 200, roles.text
    assert "Device Agent" not in [r["name"] for r in roles.json()]
    body = {"username": "not.a.device", "email": "nd@example.test", "full_name": "", "role": "Device Agent",
            "locale": "sk", "password": "Aa1!bcdefghijkl", "send_email": False}
    r = env.client.post("/api/v1/users", json=body, headers=env.csrf())
    assert r.status_code == 422 and "role_invalid" in r.text
