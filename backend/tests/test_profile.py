"""Dual-use profiles (ARG-021, AG-D-60): configuration, not code."""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config import ConfigError, load_config
from app.services.profile import build_profile
from tests.conftest import Env


def test_profiles_differ_only_in_configuration():
    civil, defense = build_profile("civil"), build_profile("defense")
    assert (civil.marking, civil.offline_only, civil.telemetry_retention_days) == ("", False, 30)
    assert (defense.marking, defense.offline_only, defense.telemetry_retention_days) == ("RESTRICTED", True, 90)
    assert build_profile("defense", "NATO-X ").marking == "NATO-X"
    assert build_profile("civil", "x" * 200).marking == "x" * 64
    with pytest.raises(ValueError):
        build_profile("military")


def test_the_profile_comes_from_the_environment_and_rejects_unknown_values(monkeypatch):
    monkeypatch.setenv("ARGUS_DATABASE_URL", "postgresql+psycopg://u:p@localhost/x")
    monkeypatch.delenv("ARGUS_PROFILE", raising=False)
    assert load_config().profile == "civil"
    monkeypatch.setenv("ARGUS_PROFILE", "Defense")
    assert load_config().profile == "defense"
    monkeypatch.setenv("ARGUS_PROFILE", "war")
    with pytest.raises(ConfigError):
        load_config()


def test_session_tells_the_client_the_profile_before_login(admin_session: Env):
    env = admin_session
    info = env.new_client().get("/api/v1/auth/session").json()
    assert info["profile"] == {"name": "civil", "marking": ""}


def test_defense_profile_forces_offline_only_and_marks_exports(admin_session: Env):
    from fastapi.testclient import TestClient

    from app.main import create_app

    env = admin_session
    defense = replace(env.config, profile="defense", marking=None)
    app = create_app(defense, clock=env.clock, db=env.db, transport=env.transport)
    with TestClient(app, client=("127.0.0.1", 50001)) as client:
        assert client.get("/api/v1/auth/session").json()["profile"] == {"name": "defense", "marking": "RESTRICTED"}
        assert env.login(env.admin_username, env.admin_password, client).status_code == 200
        headers = env.csrf(client)

        policy = client.get("/api/v1/intel/policy").json()
        assert policy["offline_only"] is True  # forced although never stored

        body = {**{k: policy[k] for k in ("zero_hour_hours", "epss_threshold", "notify_min_severity", "notify")},
                "offline_only": False}
        r = client.put("/api/v1/intel/policy", json=body, headers=headers)
        assert r.status_code == 422, r.text
        assert "intel.profile_offline_forced" in r.text

        export = client.get("/api/v1/audit/export")
        assert export.status_code == 200
        assert export.text.startswith("# RESTRICTED" + chr(10))


def test_civil_export_has_no_marking_line(admin_session: Env):
    env = admin_session
    export = env.client.get("/api/v1/audit/export")
    assert export.status_code == 200 and export.text.startswith("id,")


def test_defense_retention_default_is_longer_but_an_explicit_setting_wins(admin_session: Env):
    from app.services.container import Services

    env = admin_session
    defense = replace(env.config, profile="defense")
    with env.db.transaction() as session:
        services = Services(session, env.clock, defense)
        assert services.telemetry.retention_days() == 90
        services.store.put("telemetry_retention_days", {"days": 14})
    with env.db.transaction() as session:
        assert Services(session, env.clock, defense).telemetry.retention_days() == 14
