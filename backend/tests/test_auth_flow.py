"""Login, logout, forced change, sessions (T-IDN-01 to T-IDN-04, T-PWD-04 through the API)."""
from __future__ import annotations

from tests.conftest import Env


def test_health_needs_no_login(env: Env):
    assert env.client.get("/api/v1/health").json() == {"status": "ok"}


def test_unauthenticated_requests_are_rejected(env: Env):
    assert env.client.get("/api/v1/settings/password-policy").status_code == 401
    assert env.client.get("/api/v1/policy/password/summary").status_code == 401
    assert env.client.get("/api/v1/auth/session").json()["authenticated"] is False


def test_initial_admin_forced_change_blocks_everything_else(env: Env):
    """T-IDN-02: random initial password, first login forces a change, nothing else works before it."""
    assert env.admin_username == "sysadmin"
    r = env.login(env.admin_username, env.admin_password)
    assert r.status_code == 200
    body = r.json()
    assert body["must_change_password"] is True
    assert env.client.get("/api/v1/settings/password-policy").status_code == 403
    assert env.client.get("/api/v1/settings/password-policy").json()["code"] == "password_change_required"
    # the policy summary and generator stay available so the change dialog works
    assert env.client.get("/api/v1/policy/password/summary").status_code == 200
    assert env.client.post("/api/v1/policy/password/generate", headers=env.csrf()).status_code == 200


def test_initial_password_is_random_and_policy_valid(env: Env):
    from app.services.policy_service import PasswordPolicy, evaluate

    assert evaluate(PasswordPolicy(), env.admin_password, env.admin_username) == []
    assert len(env.admin_password) >= 16


def test_second_bootstrap_does_not_change_the_admin(env: Env):
    from app.tools.prepare_database import prepare

    result = prepare(env.config, "standard", clock=env.clock)
    assert result.initial_admin_created is False
    assert env.login(env.admin_username, env.admin_password).status_code == 200


def test_change_password_then_login_with_new(admin_session: Env):
    env = admin_session
    assert env.client.get("/api/v1/auth/session").json()["must_change_password"] is False
    fresh = env.new_client()
    assert env.login(env.admin_username, env.admin_password, fresh).status_code == 200
    assert fresh.get("/api/v1/settings/password-policy").status_code == 200


def test_accounts_file_no_longer_holds_the_valid_password(env: Env):
    assert env.admin_password in env.config.accounts_file.read_text(encoding="utf-8")
    old = env.admin_password
    env.login(env.admin_username, old)
    env.client.post("/api/v1/auth/change-password",
                    json={"current_password": old, "new_password": "Vb3#nM8!qWe5zXc"}, headers=env.csrf())
    assert old not in env.config.accounts_file.read_text(encoding="utf-8")


def test_logout_invalidates_the_server_session(admin_session: Env):
    env = admin_session
    token = env.client.cookies.get("argus_session")
    assert token
    assert env.client.post("/api/v1/auth/logout", headers=env.csrf()).status_code == 204
    # replay the old cookie: the server must refuse it
    replay = env.new_client()
    replay.cookies.set("argus_session", token)
    assert replay.get("/api/v1/auth/session").json()["authenticated"] is False


def test_csrf_token_is_required_for_changes(admin_session: Env):
    env = admin_session
    r = env.client.put("/api/v1/settings/session", json={"inactivity_minutes": 20, "absolute_hours": 8})
    assert r.status_code == 403 and r.json()["code"] == "csrf_failed"
    ok = env.client.put("/api/v1/settings/session", json={"inactivity_minutes": 20, "absolute_hours": 8},
                        headers=env.csrf())
    assert ok.status_code == 200


def test_session_expires_after_inactivity_and_absolute_lifetime(admin_session: Env):
    env = admin_session
    env.clock.advance(minutes=31)
    assert env.client.get("/api/v1/auth/session").json()["authenticated"] is False

    assert env.login(env.admin_username, env.admin_password).status_code == 200
    for _ in range(25):  # stay active for 12.5 hours in 30-minute steps
        env.clock.advance(minutes=29)
        s = env.client.get("/api/v1/auth/session").json()
        if not s["authenticated"]:
            break
    assert s["authenticated"] is False


def test_password_change_revokes_other_sessions(env: Env):
    env.login(env.admin_username, env.admin_password)
    other = env.new_client()
    env.login(env.admin_username, env.admin_password, other)
    assert other.get("/api/v1/auth/session").json()["authenticated"] is True
    env.client.post("/api/v1/auth/change-password",
                    json={"current_password": env.admin_password, "new_password": "Kj4$hG7!pLm2sDf"},
                    headers=env.csrf())
    assert other.get("/api/v1/auth/session").json()["authenticated"] is False
    assert env.client.get("/api/v1/auth/session").json()["authenticated"] is True


def test_change_password_enforces_policy_and_reports_all_failures(env: Env):
    env.login(env.admin_username, env.admin_password)
    r = env.client.post("/api/v1/auth/change-password",
                        json={"current_password": env.admin_password, "new_password": "short"},
                        headers=env.csrf())
    assert r.status_code == 422
    codes = r.json()["details"]
    assert {"password.too_short", "password.no_upper", "password.no_digit", "password.no_special"} <= set(codes)


def test_new_password_must_differ_and_history_is_enforced(admin_session: Env):
    env = admin_session
    same = env.client.post("/api/v1/auth/change-password",
                           json={"current_password": env.admin_password, "new_password": env.admin_password},
                           headers=env.csrf())
    assert same.status_code == 422 and "password.same_as_current" in same.json()["details"]

    # voluntary change before the minimum age (48 h) is refused
    soon = env.client.post("/api/v1/auth/change-password",
                           json={"current_password": env.admin_password, "new_password": "Wx9!tYu3#pLk8Qa"},
                           headers=env.csrf())
    assert soon.status_code == 422 and "password.too_recent" in soon.json()["details"]

    env.clock.advance(hours=49)  # the 30-minute inactivity limit also passed: log in again
    first_pw = env.admin_password
    assert env.login(env.admin_username, first_pw).status_code == 200
    ok = env.client.post("/api/v1/auth/change-password",
                         json={"current_password": first_pw, "new_password": "Wx9!tYu3#pLk8Qa"},
                         headers=env.csrf())
    assert ok.status_code == 204
    env.admin_password = "Wx9!tYu3#pLk8Qa"
    env.clock.advance(hours=49)
    assert env.login(env.admin_username, env.admin_password).status_code == 200
    back = env.client.post("/api/v1/auth/change-password",
                           json={"current_password": env.admin_password, "new_password": first_pw},
                           headers=env.csrf())
    assert back.status_code == 422 and "password.reused" in back.json()["details"]


def test_expired_password_forces_a_change_at_login(admin_session: Env):
    env = admin_session
    env.clock.advance(days=200)  # six months policy
    r = env.login(env.admin_username, env.admin_password, env.new_client())
    assert r.json()["must_change_password"] is True


def test_wrong_current_password_is_rejected(admin_session: Env):
    env = admin_session
    r = env.client.post("/api/v1/auth/change-password",
                        json={"current_password": "not-the-password", "new_password": "Pw7!zXcV9bNm2Lk"},
                        headers=env.csrf())
    assert r.status_code == 422 and r.json()["code"] == "password.current_invalid"


def test_password_never_reaches_the_audit_log(admin_session: Env):
    env = admin_session
    from sqlalchemy import text

    with env.services() as svc:
        dump = svc.session.execute(text("SELECT details::text || changes::text || reason FROM audit_log")).scalars()
        blob = "\n".join(dump)
    assert "Zq7!mK2#vR9@xLw4" not in blob
    assert env.admin_password not in blob


def test_validation_errors_do_not_echo_submitted_values(env: Env):
    r = env.client.post("/api/v1/auth/login", json={"username": "x", "password": "SecretValue!", "extra": 1})
    assert r.status_code == 422
    assert "SecretValue!" not in r.text


def test_audit_chain_is_intact_and_append_only(admin_session: Env):
    env = admin_session
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    with env.services() as svc:
        assert svc.audit.verify_chain() is True
    with pytest.raises(DBAPIError):
        with env.services() as svc:
            svc.session.execute(text("UPDATE audit_log SET reason = 'x' WHERE id = 1"))
    with pytest.raises(DBAPIError):
        with env.services() as svc:
            svc.session.execute(text("DELETE FROM audit_log"))
    assert "auth.login" in env.audit_actions()
