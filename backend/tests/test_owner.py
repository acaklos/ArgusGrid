"""Emergency Owner support: hidden, bypasses RBAC, fails closed (T-OWN-01..05 at API level)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select, text

from app.models.system import AuditRecord, OwnerLogRecord
from tests.conftest import Env

import owner_tool  # devtools/owner_tool.py, development only


@pytest.fixture()
def owner(env: Env):  # type: ignore[no-untyped-def]
    with env.services() as svc:
        installation_id = svc.store.get("installation")["id"]
    identifier, secret = owner_tool.write_sealed(env.config.owner_file, installation_id)
    return identifier, secret


def test_owner_logs_in_and_has_every_capability(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, secret = owner
    r = env.login(identifier, secret)
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True and body["capabilities"] == ["*"]
    assert env.client.get("/api/v1/settings/password-policy").status_code == 200
    assert env.client.get("/api/v1/settings/lockout").status_code == 200
    put = env.client.put("/api/v1/settings/session", json={"inactivity_minutes": 25, "absolute_hours": 10},
                         headers=env.csrf())
    assert put.status_code == 200


def test_owner_is_logged_separately_and_shown_as_system(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, secret = owner
    env.login(identifier, secret)
    env.client.put("/api/v1/settings/session", json={"inactivity_minutes": 25, "absolute_hours": 10},
                   headers=env.csrf())
    with env.services() as svc:
        owner_actions = list(svc.session.execute(select(OwnerLogRecord.action)).scalars())
        normal = svc.session.execute(select(AuditRecord).where(AuditRecord.action == "policy.session.update")
                                     ).scalar_one()
        everything = " ".join(
            svc.session.execute(text("SELECT coalesce(string_agg(actor_name || action || details::text, ' '), '') "
                                     "FROM audit_log")).scalars()
        )
    assert "owner.login" in owner_actions and "policy.session.update" in owner_actions
    assert normal.actor_name == "System"
    assert identifier not in everything and "owner" not in everything.lower()
    assert "owner.login" not in env.audit_actions()  # OWN-009: no normal audit entry for the owner login


def test_wrong_owner_secret_is_indistinguishable_from_an_ordinary_failure(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, _ = owner
    bad_owner = env.login(identifier, "not-the-secret")
    bad_user = env.login("nobody", "not-the-secret")
    assert bad_owner.status_code == bad_user.status_code == 401
    assert bad_owner.json() == bad_user.json() == {"code": "invalid_credentials"}
    assert "set-cookie" not in bad_owner.headers


def test_owner_path_has_its_own_rate_limit(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, secret = owner
    for _ in range(5):
        assert env.login(identifier, "wrong").status_code == 401
    blocked = env.login(identifier, secret)  # correct secret, but the owner path is cooling down
    assert blocked.status_code == 401 and blocked.json() == {"code": "invalid_credentials"}
    env.clock.advance(minutes=16)
    assert env.login(identifier, secret).status_code == 200


def test_owner_failures_do_not_lock_ordinary_users(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, _ = owner
    env.make_user("alice", "SOC Analyst")
    for _ in range(6):
        env.login(identifier, "wrong")
    assert env.login("alice", "Aa1!bcdefghijkl").status_code == 200


def test_missing_modified_or_foreign_file_disables_the_owner_path(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, secret = owner
    path = env.config.owner_file
    original = path.read_text(encoding="utf-8")

    path.unlink()
    assert env.login(identifier, secret).status_code == 401  # missing: no fallback

    data = json.loads(original)
    data["verifier"] = data["verifier"][:-2] + ("AA" if not data["verifier"].endswith("AA") else "BB")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert env.login(identifier, secret).status_code == 401  # modified: checksum fails

    path.write_text("{ not json", encoding="utf-8")
    assert env.login(identifier, secret).status_code == 401  # unreadable

    other_identifier, other_secret = owner_tool.write_sealed(path, "00000000-0000-0000-0000-000000000000")
    assert env.login(other_identifier, other_secret).status_code == 401  # belongs to another installation

    path.write_text(original, encoding="utf-8")
    assert env.login(identifier, secret).status_code == 200  # restored file works again
    with env.services() as svc:
        assert svc.owner.is_available()


def test_no_owner_user_is_ever_created(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, secret = owner
    env.login(identifier, secret)
    with env.services() as svc:
        names = list(svc.session.execute(text("SELECT username FROM users")).scalars())
    assert names == ["sysadmin"]


def test_sealed_file_has_no_plaintext_secret(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, secret = owner
    content = env.config.owner_file.read_text(encoding="utf-8")
    assert secret not in content and identifier not in content
    assert json.loads(content)["verifier"].startswith("$argon2id$")


def test_owner_cannot_change_a_password(env: Env, owner):  # type: ignore[no-untyped-def]
    identifier, secret = owner
    env.login(identifier, secret)
    r = env.client.post("/api/v1/auth/change-password",
                        json={"current_password": secret, "new_password": "Xx1!yyyyyyyyyy"}, headers=env.csrf())
    assert r.status_code == 403
