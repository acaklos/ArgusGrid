"""Test infrastructure: isolated PostgreSQL test database, fake clock, running API through TestClient.

The suite needs the development database cluster (devtools/dev_db.ps1 -Action start). It uses the
database `argusgrid_test` next to the development database, and empties it before every test.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

os.environ["ARGUS_ENV"] = "test"
BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "devtools"))

from app.core.clock import FakeClock  # noqa: E402
from app.core.config import AppConfig  # noqa: E402
from app.core.db import Database  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.container import Services  # noqa: E402
from app.services.mail_service import RecordingTransport  # noqa: E402
from app.tools.prepare_database import prepare, upgrade_schema  # noqa: E402


def _test_url() -> str:
    url = os.environ.get("ARGUS_TEST_DATABASE_URL")
    if url:
        return url
    dev = (BACKEND / "data" / "database.url").read_text(encoding="utf-8").strip()
    return re.sub(r"/argusgrid$", "/argusgrid_test", dev)


@pytest.fixture(scope="session")
def test_url() -> str:
    return _test_url()


@pytest.fixture(scope="session", autouse=True)
def _schema(test_url: str, tmp_path_factory: pytest.TempPathFactory) -> None:
    cfg = _make_config(test_url, tmp_path_factory.mktemp("schema"))
    upgrade_schema(cfg)


def _make_config(url: str, base: Path) -> AppConfig:
    data = base / "data"
    config = base / "config"
    data.mkdir(parents=True, exist_ok=True)
    config.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        environment="test", data_dir=data, config_dir=config, database_url=url, secure_cookies=False,
        bind_host="127.0.0.1", dev_loginless=False, dev_loginless_role="Administrator", run_workers=False,
    )


@pytest.fixture()
def config(test_url: str, tmp_path: Path) -> AppConfig:
    return _make_config(test_url, tmp_path)


@pytest.fixture()
def clean_db(test_url: str) -> None:
    engine = create_engine(test_url, future=True)
    with engine.begin() as conn:
        names = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
        ).scalars().all()
        if names:
            conn.execute(text("TRUNCATE " + ", ".join(f'"{n}"' for n in names) + " RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


class Env:
    """Everything a test needs: config, clock, database, app, client and bootstrap result."""

    def __init__(self, config: AppConfig, clock: FakeClock, db: Database, client: TestClient,
                 admin_username: str, admin_password: str, transport: RecordingTransport) -> None:
        self.config = config
        self.transport = transport
        self.clock = clock
        self.db = db
        self.client = client
        self.admin_username = admin_username
        self.admin_password = admin_password

    def services(self) -> "ServicesScope":
        return ServicesScope(self)

    # -- helpers -----------------------------------------------------------------------------------
    def login(self, username: str, password: str, client: TestClient | None = None):  # type: ignore[no-untyped-def]
        return (client or self.client).post("/api/v1/auth/login", json={"username": username, "password": password})

    def csrf(self, client: TestClient | None = None) -> dict[str, str]:
        info = (client or self.client).get("/api/v1/auth/session").json()
        return {"X-CSRF-Token": info["csrf_token"] or ""}

    def new_client(self) -> TestClient:
        return TestClient(self.client.app, base_url="http://testserver", client=("127.0.0.1", 50000))

    def make_user(self, username: str, role_name: str, password: str = "Aa1!bcdefghijkl",
                  must_change: bool = False) -> str:
        """Create a user directly through the credential service (as a seed script would)."""
        from app.models.identity import User

        with self.services() as svc:
            role = svc.roles.by_name(role_name)
            assert role is not None
            user = User(username=username, username_key=username.lower(), email=f"{username}@example.test",
                        full_name=username, role_id=role.id, password_hash="", created_at=svc.clock.now())
            svc.credentials.apply_to_new_user(user, password, must_change=must_change)
            svc.session.add(user)
        return password

    def audit_actions(self) -> list[str]:
        from sqlalchemy import select

        from app.models.system import AuditRecord

        with self.services() as svc:
            return list(svc.session.execute(select(AuditRecord.action).order_by(AuditRecord.id)).scalars())


class ServicesScope:
    def __init__(self, env: Env) -> None:
        self._env = env

    def __enter__(self) -> Services:
        self._session = self._env.db.session()
        return Services(self._session, self._env.clock, self._env.config, self._env.transport)

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if exc_type is None:
            self._session.commit()
        else:
            self._session.rollback()
        self._session.close()


@pytest.fixture()
def env(config: AppConfig, clock: FakeClock, clean_db: None) -> Iterator[Env]:
    result = prepare(config, "standard", clock=clock)
    db = Database(config.database_url)
    transport = RecordingTransport()
    app = create_app(config, clock=clock, db=db, transport=transport)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        # The suite is about behaviour, not about throttling: raise the source limit (tests of it lower it).
        with db.transaction() as session:
            svc = Services(session, clock, config)
            settings = svc.lockout_settings.get().to_dict()
            settings["source_throttle_per_minute"] = 100000
            svc.store.put("lockout_policy", settings)
        yield Env(config, clock, db, client, result.initial_admin_username, result.initial_admin_password,
                  transport)
    db.dispose()


@pytest.fixture()
def admin_session(env: Env) -> Env:
    """Administrator logged in with the forced first change completed. Returns the env, client has cookie."""
    r = env.login(env.admin_username, env.admin_password)
    assert r.status_code == 200, r.text
    new_password = "Zq7!mK2#vR9@xLw4"
    r = env.client.post(
        "/api/v1/auth/change-password",
        json={"current_password": env.admin_password, "new_password": new_password},
        headers=env.csrf(),
    )
    assert r.status_code == 204, r.text
    env.admin_password = new_password
    # password change revokes other sessions only; the current one stays valid
    return env
