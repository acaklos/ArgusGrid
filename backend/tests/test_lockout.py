"""Lockout and recovery module (T-LCK-01 to T-LCK-12, rules/18)."""
from __future__ import annotations

import copy

import pytest
from sqlalchemy import select

from app.core.context import Actor, RequestContext
from app.models.identity import User
from tests.conftest import Env

WRONG = "definitely-wrong-password"


def fail(env: Env, username: str, times: int = 1) -> None:
    for _ in range(times):
        r = env.login(username, WRONG)
        assert r.status_code == 401


def state(env: Env, username: str) -> dict:
    with env.services() as svc:
        u = svc.session.execute(select(User).where(User.username_key == username.lower())).scalar_one()
        return {"until": u.locked_until, "permanent": u.lock_permanent, "cycles": u.lock_cycles,
                "must_change": u.must_change_password, "id": u.id, "manual": u.lock_manual}


def set_lockout(env: Env, mutate) -> None:  # type: ignore[no-untyped-def]
    with env.services() as svc:
        data = copy.deepcopy(svc.lockout_settings.get().to_dict())
        mutate(data)
        svc.store.put("lockout_policy", data)


def admin_ctx(env: Env, name: str = "boss", role: str = "Administrator") -> RequestContext:
    with env.services() as svc:
        u = svc.session.execute(select(User).where(User.username_key == name)).scalar_one()
        return RequestContext(actor=Actor(kind="user", name=u.username, role=role, user_id=u.id), channel="api")


def unlock(env: Env, target: str, ctx: RequestContext):  # type: ignore[no-untyped-def]
    with env.services() as svc:
        user = svc.session.execute(select(User).where(User.username_key == target)).scalar_one()
        return svc.lockout.unlock(user, ctx)


def test_attempts_outside_the_counting_window_do_not_count(env: Env):
    env.make_user("alice", "SOC Analyst")
    fail(env, "alice", 4)
    env.clock.advance(minutes=16)
    fail(env, "alice", 1)  # only one attempt is inside the window now
    assert state(env, "alice")["until"] is None
    assert env.login("alice", "Aa1!bcdefghijkl").status_code == 200


def test_correct_password_does_not_bypass_an_active_lock(env: Env):
    env.make_user("alice", "SOC Analyst")
    fail(env, "alice", 5)
    assert state(env, "alice")["until"] is not None
    r = env.login("alice", "Aa1!bcdefghijkl")
    assert r.status_code == 401 and r.json() == {"code": "invalid_credentials"}


def test_auto_unlock_releases_after_the_time_and_resets_counter(env: Env):
    env.make_user("alice", "SOC Analyst")
    fail(env, "alice", 5)
    env.clock.advance(minutes=14)
    assert env.login("alice", "Aa1!bcdefghijkl").status_code == 401
    env.clock.advance(minutes=2)
    assert env.login("alice", "Aa1!bcdefghijkl").status_code == 200
    assert state(env, "alice")["cycles"] == 0  # successful login resets the cycle counter
    fail(env, "alice", 4)  # the window counter restarted: four failures do not lock
    assert state(env, "alice")["until"] is None


def test_ordinary_user_becomes_permanent_after_three_cycles(env: Env):
    env.make_user("alice", "SOC Analyst")
    for cycle in range(3):
        fail(env, "alice", 5)
        s = state(env, "alice")
        assert s["permanent"] is False and s["cycles"] == cycle + 1
        env.clock.advance(minutes=16)
    fail(env, "alice", 5)
    assert state(env, "alice")["permanent"] is True
    env.clock.advance(days=30)
    assert env.login("alice", "Aa1!bcdefghijkl").status_code == 401


def test_administrator_delays_escalate_and_reset_on_success(env: Env):
    env.make_user("boss", "Administrator")
    expected = [1, 2, 5, 10, 15, 15]
    for minutes in expected:
        fail(env, "boss", 5)
        s = state(env, "boss")
        delta = (s["until"] - env.clock.now()).total_seconds() / 60
        assert delta == pytest.approx(minutes, abs=0.01)
        env.clock.advance(minutes=minutes, seconds=1)
    assert state(env, "boss")["permanent"] is False  # administrators never become permanent by default
    assert env.login("boss", "Aa1!bcdefghijkl").status_code == 200
    assert state(env, "boss")["cycles"] == 0


def test_permanent_mode_stays_locked_until_unlocked(env: Env):
    env.make_user("alice", "SOC Analyst")
    set_lockout(env, lambda d: d["default"].update(mode="permanent", cycles_before_permanent=None))
    fail(env, "alice", 5)
    assert state(env, "alice")["permanent"] is True
    env.clock.advance(days=3)
    assert env.login("alice", "Aa1!bcdefghijkl").status_code == 401


def test_another_administrator_unlocks_immediately_and_the_action_runs(env: Env):
    env.make_user("boss", "Administrator")
    env.make_user("worker", "Administrator")
    fail(env, "worker", 5)
    assert state(env, "worker")["until"] is not None
    outcome = unlock(env, "worker", admin_ctx(env, "boss"))
    assert outcome.after_unlock == "require_password_change"
    s = state(env, "worker")
    assert s["until"] is None and s["must_change"] is True
    r = env.login("worker", "Aa1!bcdefghijkl")
    assert r.status_code == 200 and r.json()["must_change_password"] is True


def test_self_unlock_and_non_unlockers_are_refused(env: Env):
    env.make_user("alice", "SOC Analyst")
    env.make_user("bob", "SOC Operator")
    fail(env, "alice", 5)
    with pytest.raises(PermissionError):
        unlock(env, "alice", admin_ctx(env, "alice", role="SOC Analyst"))  # self
    with pytest.raises(PermissionError):
        unlock(env, "alice", admin_ctx(env, "bob", role="SOC Operator"))  # not in unlockers
    assert state(env, "alice")["until"] is not None


def test_reset_password_after_unlock_issues_a_temporary_password(env: Env):
    env.make_user("boss", "Administrator")
    env.make_user("alice", "SOC Analyst")
    set_lockout(env, lambda d: d["default"].update(after_unlock="reset_password"))
    fail(env, "alice", 5)
    outcome = unlock(env, "alice", admin_ctx(env, "boss"))
    assert outcome.temporary_password
    assert env.login("alice", "Aa1!bcdefghijkl").status_code == 401  # old password no longer valid
    r = env.login("alice", outcome.temporary_password)
    assert r.status_code == 200 and r.json()["must_change_password"] is True


def test_last_administrator_option_both_variants(env: Env):
    # variant off (default): the only administrator can be locked
    fail(env, env.admin_username, 5)
    assert state(env, env.admin_username)["until"] is not None
    # variant on: failures are counted and audited, the account is not locked
    with env.services() as svc:
        u = svc.session.execute(select(User).where(User.username_key == env.admin_username)).scalar_one()
        u.locked_until = None
        u.lock_cycles = 0
    set_lockout(env, lambda d: d.update(exempt_last_administrator=True, source_throttle_per_minute=100000))
    fail(env, env.admin_username, 6)
    assert state(env, env.admin_username)["until"] is None
    assert "auth.lock_suppressed" in env.audit_actions()
    # with a second usable administrator the exemption no longer applies
    env.make_user("boss", "Administrator")
    fail(env, env.admin_username, 5)
    assert state(env, env.admin_username)["until"] is not None


def test_lock_state_survives_a_restart(env: Env):
    env.make_user("alice", "SOC Analyst")
    fail(env, "alice", 5)
    from app.core.db import Database
    from app.main import create_app
    from fastapi.testclient import TestClient

    db2 = Database(env.config.database_url)
    with TestClient(create_app(env.config, clock=env.clock, db=db2)) as restarted:
        r = restarted.post("/api/v1/auth/login", json={"username": "alice", "password": "Aa1!bcdefghijkl"})
        assert r.status_code == 401
    db2.dispose()


def test_unknown_user_wrong_password_and_locked_look_the_same(env: Env):
    env.make_user("alice", "SOC Analyst")
    env.make_user("carol", "SOC Analyst")
    unknown = env.login("nobody-here", WRONG)
    wrong = env.login("alice", WRONG)
    fail(env, "carol", 5)
    locked = env.login("carol", "Aa1!bcdefghijkl")
    for r in (unknown, wrong, locked):
        assert r.status_code == 401 and r.json() == {"code": "invalid_credentials"}
        assert "set-cookie" not in r.headers


def test_lock_ends_the_active_session_on_the_next_request(env: Env):
    env.make_user("boss", "Administrator")
    env.make_user("alice", "SOC Analyst")
    assert env.login("alice", "Aa1!bcdefghijkl").status_code == 200
    assert env.client.get("/api/v1/auth/session").json()["authenticated"] is True
    with env.services() as svc:
        user = svc.session.execute(select(User).where(User.username_key == "alice")).scalar_one()
        svc.lockout.lock_manually(user, admin_ctx(env, "boss"), "test")
    assert env.client.get("/api/v1/auth/session").json()["authenticated"] is False
    assert state(env, "alice")["manual"] is True


def test_source_throttle_limits_login_requests(env: Env):
    set_lockout(env, lambda d: d.update(source_throttle_per_minute=3))
    codes = [env.login("someone", WRONG).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


def test_lock_and_unlock_are_audited_without_secrets(env: Env):
    env.make_user("boss", "Administrator")
    env.make_user("alice", "SOC Analyst")
    fail(env, "alice", 5)
    unlock(env, "alice", admin_ctx(env, "boss"))
    actions = env.audit_actions()
    assert "user.locked" in actions and "user.unlock" in actions and "auth.login_failed" in actions
    with env.services() as svc:
        assert svc.audit.verify_chain()


BAD_CONFIGS = {
    "lockout.no_unlocker": lambda d: d["default"].update(unlockers=[]),
    "lockout.threshold_or_window_invalid": lambda d: d["default"].update(threshold=0),
    "lockout.sequence_not_increasing": lambda d: d["roles"]["Administrator"].update(durations_minutes=[5, 5, 1]),
    "lockout.duration_invalid": lambda d: d["default"].update(durations_minutes=[0]),
    "lockout.permanent_without_unlock_path": lambda d: d["roles"]["Administrator"].update(
        mode="permanent", unlockers=["SOC Manager"]),
    "lockout.unlocker_below_target": lambda d: d["default"].update(unlockers=["Auditor"]),
    "lockout.exempt_without_throttle": lambda d: d.update(exempt_last_administrator=True,
                                                          source_throttle_per_minute=0),
    "lockout.mode_invalid": lambda d: d["default"].update(mode="sometimes"),
    "lockout.cycles_invalid": lambda d: d["default"].update(cycles_before_permanent=0),
}


@pytest.mark.parametrize("code", sorted(BAD_CONFIGS))
def test_inconsistent_lockout_configuration_is_rejected_with_names(admin_session: Env, code: str):
    env = admin_session
    current = env.client.get("/api/v1/settings/lockout").json()["settings"]
    BAD_CONFIGS[code](current)
    r = env.client.put("/api/v1/settings/lockout", json=current, headers=env.csrf())
    assert r.status_code == 422 and r.json()["code"] == "lockout.inconsistent"
    problems = r.json()["details"]
    assert code in {p["code"] for p in problems}
    assert all(p["fields"] for p in problems)


def test_valid_lockout_configuration_is_saved_and_audited(admin_session: Env):
    env = admin_session
    current = env.client.get("/api/v1/settings/lockout").json()["settings"]
    current["default"]["threshold"] = 3
    r = env.client.put("/api/v1/settings/lockout", json=current, headers=env.csrf())
    assert r.status_code == 200 and r.json()["settings"]["default"]["threshold"] == 3
    assert "policy.lockout.update" in env.audit_actions()
