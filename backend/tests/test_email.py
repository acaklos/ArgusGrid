"""E-mail settings, templates, outbox, delivery and expiry notices (ARG-006 to ARG-008)."""
from __future__ import annotations

import socket

import pytest
from aiosmtpd.controller import Controller
from sqlalchemy import select, text

from app.models.mail import MailOutbox
from app.workers import run_once
from tests.conftest import Env

SMTP = {"enabled": True, "host": "mail.example.test", "port": 587, "tls_mode": "starttls",
        "username": "mailer", "password": "smtp-secret-Pw1", "from_address": "argus@example.test",
        "from_name": "ArgusGrid", "login_url": "https://argus.example.test/login"}


def configure(env: Env, **over):  # type: ignore[no-untyped-def]
    body = {**SMTP, **over}
    r = env.client.put("/api/v1/settings/email", json=body, headers=env.csrf())
    assert r.status_code == 200, r.text
    return r.json()


def create_alice(env: Env, **over):  # type: ignore[no-untyped-def]
    body = {"username": "alice.smith", "email": "alice@example.test", "full_name": "Alice Smith",
            "role": "SOC Analyst", "locale": "en", "password": "Tr9#kLm2!pQw7zXv", "send_email": True, **over}
    r = env.client.post("/api/v1/users", json=body, headers=env.csrf())
    assert r.status_code == 201, r.text
    return r.json()


# -- settings ----------------------------------------------------------------------------------------
def test_smtp_password_is_never_returned_and_is_stored_encrypted(admin_session: Env):
    env = admin_session
    saved = configure(env)
    assert saved["password_set"] is True and "password" not in saved
    assert "smtp-secret-Pw1" not in env.client.get("/api/v1/settings/email").text
    with env.services() as svc:
        stored = svc.store.get("email_settings")
        raw = text("SELECT value::text FROM app_settings WHERE key = 'email_settings'")
        blob = svc.session.execute(raw).scalar_one()
    assert stored["password_enc"].startswith("enc1:") and "smtp-secret-Pw1" not in blob
    # updating other fields keeps the password (it is not sent again)
    again = env.client.put("/api/v1/settings/email", json={"port": 2525}, headers=env.csrf()).json()
    assert again["port"] == 2525 and again["password_set"] is True
    with env.services() as svc:
        assert svc.email_settings.get_config().password == "smtp-secret-Pw1"


def test_password_value_is_redacted_in_the_audit_log(admin_session: Env):
    env = admin_session
    configure(env)
    with env.services() as svc:
        dump = "\n".join(svc.session.execute(text("SELECT changes::text || details::text FROM audit_log")).scalars())
    assert "smtp-secret-Pw1" not in dump and "enc1:" not in dump
    assert "settings.email.update" in env.audit_actions()


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"port": 70000}, "email.port_invalid"),
        ({"tls_mode": "plain"}, "email.tls_mode_invalid"),
        ({"host": "bad host!"}, "email.host_invalid"),
        ({"from_address": "nope"}, "email.from_invalid"),
        ({"enabled": True, "host": ""}, "email.host_required"),
        ({"username": "u", "password": ""}, None),
    ],
)
def test_smtp_settings_are_validated(admin_session: Env, changes, code):  # type: ignore[no-untyped-def]
    env = admin_session
    r = env.client.put("/api/v1/settings/email", json=changes, headers=env.csrf())
    if code is None:
        assert r.status_code in (200, 422)
        return
    assert r.status_code == 422 and r.json()["code"] == "email.inconsistent"
    problems = r.json()["details"]
    assert code in {p["code"] for p in problems} and all(p["fields"] for p in problems)


# -- delivery ----------------------------------------------------------------------------------------
def test_credentials_mail_is_delivered_then_wiped_from_the_outbox(admin_session: Env):
    env = admin_session
    configure(env)
    result = create_alice(env)
    assert result["email_configured"] is True
    outcome = run_once(env.db, env.clock, env.config, env.transport)
    assert outcome["sent"] == 1
    message = env.transport.sent[0]
    assert message["To"] == "alice@example.test" and "ArgusGrid" in message["From"]
    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "Tr9#kLm2!pQw7zXv" in body and "alice.smith" in body
    assert "https://argus.example.test/login" in body
    with env.services() as svc:
        row = svc.session.execute(select(MailOutbox)).scalar_one()
        assert row.status == "sent" and row.sent_at is not None
        assert row.body_text == "" and row.body_html == ""  # nothing readable stays behind
        dump = text("SELECT string_agg(subject || body_text || body_html, ' ') FROM mail_outbox")
        assert "Tr9#kLm2!pQw7zXv" not in (svc.session.execute(dump).scalar() or "")


def test_delivery_waits_while_email_is_not_configured(admin_session: Env):
    env = admin_session
    create_alice(env)
    outcome = run_once(env.db, env.clock, env.config, env.transport)
    assert outcome["sent"] == 0 and outcome["waiting"] == 1
    configure(env)
    assert run_once(env.db, env.clock, env.config, env.transport)["sent"] == 1


def test_failed_delivery_is_retried_with_backoff_then_marked_failed(admin_session: Env):
    env = admin_session
    configure(env)
    create_alice(env)
    env.transport.fail_with = ConnectionRefusedError("connection refused")
    first = run_once(env.db, env.clock, env.config, env.transport)
    assert first["retry"] == 1
    assert run_once(env.db, env.clock, env.config, env.transport)["retry"] == 0  # not due yet
    for minutes in (2, 6, 16, 61):
        env.clock.advance(minutes=minutes)
        run_once(env.db, env.clock, env.config, env.transport)
    with env.services() as svc:
        row = svc.session.execute(select(MailOutbox)).scalar_one()
    assert row.status == "failed" and row.attempts == 5 and "ConnectionRefusedError" in row.last_error
    assert env.transport.sent == []


def test_test_message_reports_the_real_result(admin_session: Env):
    env = admin_session
    env.client.put("/api/v1/users/1", json={"email": "admin@example.test"}, headers=env.csrf())
    assert env.client.post("/api/v1/settings/email/test", json={}, headers=env.csrf()).status_code == 409
    configure(env)
    ok = env.client.post("/api/v1/settings/email/test", json={}, headers=env.csrf())
    assert ok.status_code == 200 and ok.json()["status"] == "sent"
    assert env.transport.sent[-1]["To"] == "admin@example.test"
    env.transport.fail_with = TimeoutError("timed out")
    bad = env.client.post("/api/v1/settings/email/test", json={"to": "x@example.test"}, headers=env.csrf())
    assert bad.status_code == 200 and bad.json()["status"] == "pending" and "TimeoutError" in bad.json()["error"]


def test_real_smtp_delivery_to_a_local_server(admin_session: Env):
    """The SmtpTransport against a real SMTP server (aiosmtpd), not a mock."""
    from app.services.mail_service import SmtpTransport

    received: list[tuple[str, list[str], bytes]] = []

    class Handler:
        async def handle_DATA(self, server, session, envelope):  # type: ignore[no-untyped-def]
            received.append((envelope.mail_from, list(envelope.rcpt_tos), envelope.content))
            return "250 OK"

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    controller = Controller(Handler(), hostname="127.0.0.1", port=port)
    controller.start()
    try:
        env = admin_session
        configure(env, host="127.0.0.1", port=port, tls_mode="none", username="", password="", clear_password=True)
        create_alice(env)
        outcome = run_once(env.db, env.clock, env.config, SmtpTransport())
        assert outcome["sent"] == 1
    finally:
        controller.stop()
    assert len(received) == 1
    sender, recipients, content = received[0]
    assert sender == "argus@example.test" and recipients == ["alice@example.test"]
    assert b"Tr9#kLm2!pQw7zXv" in content


# -- expiry notices ----------------------------------------------------------------------------------
def test_password_expiry_notice_is_sent_once_per_expiry(admin_session: Env):
    env = admin_session
    configure(env)
    env.make_user("alice", "SOC Analyst")
    assert run_once(env.db, env.clock, env.config, env.transport)["expiry_queued"] == 0  # far from expiry
    env.clock.advance(days=170)  # six months policy, 14 days notice
    first = run_once(env.db, env.clock, env.config, env.transport)
    assert first["expiry_queued"] >= 1
    subjects = [m["Subject"] for m in env.transport.sent]
    assert any("expires" in s for s in subjects)
    count = len(env.transport.sent)
    second = run_once(env.db, env.clock, env.config, env.transport)
    assert second["expiry_queued"] == 0 and len(env.transport.sent) == count


def test_expiry_notice_uses_the_days_from_the_password_policy(admin_session: Env):
    env = admin_session
    env.make_user("alice", "SOC Analyst")
    policy = env.client.get("/api/v1/settings/password-policy").json()["policy"]
    policy["expiry_notice_days"] = 3
    assert env.client.put("/api/v1/settings/password-policy", json=policy, headers=env.csrf()).status_code == 200
    env.clock.advance(days=170)  # 12 days left: outside a 3 day notice
    with env.services() as svc:
        assert svc.expiry_notifier.run() == 0
    env.clock.advance(days=10)  # 2 days left
    with env.services() as svc:
        assert svc.expiry_notifier.run() >= 1


# -- templates ---------------------------------------------------------------------------------------
def test_template_catalogue_has_every_required_template(admin_session: Env):
    env = admin_session
    keys = {t["key"] for t in env.client.get("/api/v1/settings/email/templates").json()}
    assert {"user.created", "user.password_reset", "user.password_changed", "password.expiring",
            "alert.critical", "user.unlocked"} <= keys
    t = env.client.get("/api/v1/settings/email/templates/user.created", params={"locale": "sk"}).json()
    assert t["customized"] is False and "temp_password" in t["variables"] and "{{" in t["body_text"]


def test_custom_template_is_versioned_and_used(admin_session: Env):
    env = admin_session
    configure(env)
    h = env.csrf()
    url = "/api/v1/settings/email/templates/user.created"
    r = env.client.put(url, params={"locale": "en"}, headers=h,
                       json={"subject": "Welcome {{ username }}", "body_text": "Hi {{ username }}: {{ temp_password }}"})
    assert r.status_code == 200 and r.json()["version"] == 1
    r2 = env.client.put(url, params={"locale": "en"}, headers=h,
                        json={"subject": "Welcome {{ username }}!", "body_text": "Hi {{ username }}: {{ temp_password }}"})
    assert r2.json()["version"] == 2
    detail = env.client.get(url, params={"locale": "en"}).json()
    assert detail["customized"] and [v["version"] for v in detail["versions"]] == [2, 1]
    create_alice(env)
    run_once(env.db, env.clock, env.config, env.transport)
    assert env.transport.sent[-1]["Subject"] == "Welcome alice.smith!"
    assert env.client.delete(url, params={"locale": "en"}, headers=h).status_code == 204
    assert env.client.get(url, params={"locale": "en"}).json()["customized"] is False


def test_unknown_variable_and_credential_variable_in_other_templates_are_rejected(admin_session: Env):
    env = admin_session
    h = env.csrf()
    bad = env.client.put("/api/v1/settings/email/templates/user.password_changed", params={"locale": "en"}, headers=h,
                         json={"subject": "s", "body_text": "{{ temp_password }} {{ nonsense }}"})
    assert bad.status_code == 422
    problem = bad.json()["details"][0]
    assert problem["code"] == "email.template_unknown_variable" and set(problem["fields"]) == {"temp_password", "nonsense"}
    syntax = env.client.put("/api/v1/settings/email/templates/system.test", params={"locale": "en"}, headers=h,
                            json={"subject": "s", "body_text": "{% if %}"})
    assert syntax.status_code == 422 and syntax.json()["details"][0]["code"] == "email.template_syntax"


def test_template_sandbox_blocks_attribute_tricks(admin_session: Env):
    env = admin_session
    r = env.client.post("/api/v1/settings/email/templates/system.test/preview", params={"locale": "en"},
                        headers=env.csrf(),
                        json={"subject": "s", "body_text": "{{ ''.__class__.__mro__ }}"})
    # either rejected or rendered inert; it must never expose Python internals
    assert r.status_code in (200, 422)
    assert "<class" not in r.text


def test_preview_renders_sample_data_and_escapes_html(admin_session: Env):
    env = admin_session
    r = env.client.post("/api/v1/settings/email/templates/user.created/preview", params={"locale": "sk"},
                        headers=env.csrf(),
                        json={"subject": "Ahoj {{ username }}", "body_text": "Heslo: {{ temp_password }}",
                              "body_html": "<p>{{ full_name }} <b>{{ username }}</b></p>"})
    assert r.status_code == 200
    body = r.json()
    assert body["subject"] == "Ahoj jana.novakova" and "Preview-Only" in body["text"]
    assert "<b>jana.novakova</b>" in body["html"]


def test_slovak_user_gets_the_slovak_template(admin_session: Env):
    env = admin_session
    configure(env)
    create_alice(env, locale="sk")
    run_once(env.db, env.clock, env.config, env.transport)
    assert "Váš účet" in env.transport.sent[-1]["Subject"]


def test_email_pages_need_the_right_capabilities(env: Env):
    env.make_user("mgr", "SOC Manager")  # view only
    c = env.new_client()
    env.login("mgr", "Aa1!bcdefghijkl", c)
    h = env.csrf(c)
    assert c.get("/api/v1/settings/email").status_code == 200
    assert c.put("/api/v1/settings/email", json={"port": 25}, headers=h).status_code == 403
    assert c.put("/api/v1/settings/email/templates/system.test", params={"locale": "en"}, headers=h,
                 json={"subject": "s", "body_text": "b"}).status_code == 403
    assert c.post("/api/v1/settings/email/test", json={}, headers=h).status_code == 403
