"""Code-structure guards: single policy path (PWD-021), development helpers contained (DEV-001..007)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import ConfigError, load_config
from app.core.db import Database
from app.main import create_app
from tests.conftest import Env

APP = Path(__file__).resolve().parents[1] / "app"
ALLOWED_WRITERS = {"credential_service.py", "identity.py"}  # service and the model definition


def _source_files() -> list[Path]:
    return [p for p in APP.rglob("*.py")]


def test_only_the_credential_service_writes_password_hashes():
    """PWD-021: fails when another module assigns password_hash (the empty placeholder is allowed)."""
    assignment = re.compile(r"\.password_hash\s*=(?!=)")
    keyword = re.compile(r"password_hash\s*=\s*(?!\"\"|'')[^\s,)]")
    offenders: list[str] = []
    for path in _source_files():
        if path.name in ALLOWED_WRITERS:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if assignment.search(line) or keyword.search(line):
                offenders.append(f"{path.relative_to(APP)}:{number}: {line.strip()}")
    assert offenders == []


def test_every_hash_call_site_goes_through_the_credential_service():
    users_of_hasher = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bhash_password\(", text) and path.name not in {"security.py", "credential_service.py"}:
            users_of_hasher.append(path.name)
    assert users_of_hasher == []


def test_no_default_credentials_in_source():
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        assert "admin/admin" not in text.replace(" ", "")
        assert not re.search(r"password\s*=\s*[\"']admin[\"']", text, re.IGNORECASE)


def test_loginless_defaults_to_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for name in ("ARGUS_ENV", "ARGUS_DEV_LOGINLESS", "ARGUS_BIND_HOST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ARGUS_DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/x")
    assert load_config().dev_loginless is False


def test_loginless_flag_is_ignored_outside_development(monkeypatch: pytest.MonkeyPatch):
    """DEV-007."""
    monkeypatch.setenv("ARGUS_DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/x")
    monkeypatch.setenv("ARGUS_DEV_LOGINLESS", "1")
    monkeypatch.setenv("ARGUS_ENV", "production")
    assert load_config().dev_loginless is False
    monkeypatch.setenv("ARGUS_ENV", "development")
    assert load_config().dev_loginless is True


def test_loginless_refuses_a_non_loopback_bind(monkeypatch: pytest.MonkeyPatch):
    """DEV-002."""
    monkeypatch.setenv("ARGUS_DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/x")
    monkeypatch.setenv("ARGUS_ENV", "development")
    monkeypatch.setenv("ARGUS_DEV_LOGINLESS", "1")
    monkeypatch.setenv("ARGUS_BIND_HOST", "0.0.0.0")
    with pytest.raises(ConfigError):
        load_config()


def test_production_start_with_the_flag_requires_login_and_has_no_banner(env: Env):
    """DEV-007 through the running application."""
    assert env.config.dev_loginless is False
    assert env.client.get("/api/v1/settings/password-policy").status_code == 401
    assert "x-argus-dev-mode" not in env.client.get("/api/v1/health").headers


def test_loginless_mode_acts_as_an_ordinary_role_and_shows_the_banner(env: Env):
    """DEV-003, DEV-004: fixed development user, RBAC still enforced, banner header on every response."""
    from dataclasses import replace

    env.make_user("devrole", "SOC Operator")
    dev_config = replace(env.config, environment="development", dev_loginless=True, dev_loginless_role="SOC Operator")
    db = Database(dev_config.database_url)
    try:
        with TestClient(create_app(dev_config, clock=env.clock, db=db)) as client:
            health = client.get("/api/v1/health")
            assert health.headers["x-argus-dev-mode"] == "LOGINLESS DEV MODE"
            info = client.get("/api/v1/auth/session").json()
            assert info["authenticated"] is True and info["dev_loginless"] is True
            assert info["user"]["role"] == "SOC Operator"
            assert client.get("/api/v1/settings/password-policy").status_code == 403  # RBAC still applies
            assert client.get("/api/v1/policy/password/summary").status_code == 200
    finally:
        db.dispose()


def test_deep_links_to_application_pages_serve_the_client(env: Env):
    """Regression: the built files once lived under /assets, which is also a page of the application."""
    from app.main import FRONTEND_DIST

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip("the client is not built")
    for path in ("/assets", "/assets/12", "/users", "/settings/email", "/audit"):
        r = env.client.get(path, headers={"accept": "text/html"})
        assert r.status_code == 200 and "<div id=\"root\">" in r.text, path
