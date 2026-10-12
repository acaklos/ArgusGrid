"""Settings pages through the API: defaults on first open, validation, RBAC, audit (T-PWD-01..03, IDN-004)."""
from __future__ import annotations

from tests.conftest import Env


def test_password_page_shows_all_defaults_on_first_open(admin_session: Env):
    body = admin_session.client.get("/api/v1/settings/password-policy").json()
    p = body["policy"]
    assert (p["min_length"], p["max_length"], p["history_count"], p["min_age_hours"]) == (12, 128, 5, 48)
    assert p["expiration_enabled"] and p["expiration_months"] == 6 and p["reveal_autohide_seconds"] == 5
    assert body["limits"]["ceiling_max_length"] == 128


def test_each_setting_can_be_edited_and_changes_behaviour(admin_session: Env):
    env = admin_session
    p = env.client.get("/api/v1/settings/password-policy").json()["policy"]
    p.update(min_length=8, require_special=False, history_count=0, min_age_hours=0, reject_common=False)
    r = env.client.put("/api/v1/settings/password-policy", json=p, headers=env.csrf())
    assert r.status_code == 200
    summary = env.client.get("/api/v1/policy/password/summary").json()
    assert summary["min_length"] == 8 and summary["require_special"] is False
    # a password that failed the old policy is acceptable now, and changing again right away is allowed
    ok = env.client.post("/api/v1/auth/change-password",
                         json={"current_password": env.admin_password, "new_password": "Abcdefg1"}, headers=env.csrf())
    assert ok.status_code == 204


def test_inconsistent_password_settings_are_rejected_with_field_names(admin_session: Env):
    env = admin_session
    p = env.client.get("/api/v1/settings/password-policy").json()["policy"]
    p.update(min_length=30, max_length=20, expiration_months=1, min_age_hours=24 * 60)
    r = env.client.put("/api/v1/settings/password-policy", json=p, headers=env.csrf())
    assert r.status_code == 422 and r.json()["code"] == "policy.inconsistent"
    problems = {x["code"]: x["fields"] for x in r.json()["details"]}
    assert problems["policy.min_above_max"] == ["min_length", "max_length"]
    assert problems["policy.min_age_above_expiration"] == ["min_age_hours", "expiration_months"]


def test_wrong_types_are_rejected(admin_session: Env):
    env = admin_session
    p = env.client.get("/api/v1/settings/password-policy").json()["policy"]
    p["min_length"] = "twelve"
    r = env.client.put("/api/v1/settings/password-policy", json=p, headers=env.csrf())
    assert r.status_code == 422 and r.json()["code"] == "policy.invalid_value"


def test_policy_change_is_audited_with_old_and_new_values(admin_session: Env):
    env = admin_session
    p = env.client.get("/api/v1/settings/password-policy").json()["policy"]
    p["min_length"] = 14
    env.client.put("/api/v1/settings/password-policy", json=p, headers=env.csrf())
    from sqlalchemy import select

    from app.models.system import AuditRecord

    with env.services() as svc:
        row = svc.session.execute(
            select(AuditRecord).where(AuditRecord.action == "policy.password.update")
        ).scalar_one()
    assert row.changes == {"min_length": {"old": 12, "new": 14}}
    assert row.actor_name == env.admin_username and row.channel in ("api", "ui")


def test_capabilities_are_enforced_on_the_server(env: Env):
    env.make_user("op", "SOC Operator")
    env.make_user("mgr", "SOC Manager")
    env.make_user("aud", "Auditor")
    client = env.new_client()
    assert env.login("op", "Aa1!bcdefghijkl", client).status_code == 200
    h = env.csrf(client)
    assert client.get("/api/v1/settings/password-policy").status_code == 403
    assert client.put("/api/v1/settings/password-policy", json={}, headers=h).status_code == 403
    assert client.get("/api/v1/policy/password/summary").status_code == 200  # any authenticated user

    mgr = env.new_client()
    env.login("mgr", "Aa1!bcdefghijkl", mgr)
    assert mgr.get("/api/v1/settings/password-policy").status_code == 200  # view
    assert mgr.put("/api/v1/settings/password-policy", json={}, headers=env.csrf(mgr)).status_code == 403  # no edit

    aud = env.new_client()
    env.login("aud", "Aa1!bcdefghijkl", aud)
    assert aud.get("/api/v1/settings/lockout").status_code == 200
    assert aud.put("/api/v1/settings/lockout", json={}, headers=env.csrf(aud)).status_code == 403


def test_roles_and_capabilities_live_in_the_database(env: Env):
    with env.services() as svc:
        admin = svc.roles.by_name("Administrator")
        agent = svc.roles.by_name("Device Agent")
        assert "policy.password.edit" in admin.capabilities
        assert "sensor.ingest" not in admin.capabilities  # device-only capability
        assert agent.capabilities == {"sensor.ingest"}
        assert svc.roles.levels()["Administrator"] > svc.roles.levels()["SOC Manager"]


def test_generated_password_comes_from_the_active_policy(admin_session: Env):
    env = admin_session
    p = env.client.get("/api/v1/settings/password-policy").json()["policy"]
    p.update(min_length=20, require_special=False)
    env.client.put("/api/v1/settings/password-policy", json=p, headers=env.csrf())
    pw = env.client.post("/api/v1/policy/password/generate", headers=env.csrf()).json()["password"]
    assert len(pw) >= 20 and not any(not c.isalnum() for c in pw)
