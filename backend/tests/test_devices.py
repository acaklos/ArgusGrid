"""Device credentials and signed requests (ARG-013, IDN-014)."""
from __future__ import annotations

import json

from sqlalchemy import text

from app.core.signing import sign, signed_headers
from tests.conftest import Env

PATH = "/api/v1/ingest/heartbeat"


def make_sensor(env: Env, code: str = "RF-T1", typ: str = "sensor") -> int:
    r = env.client.post("/api/v1/assets", headers=env.csrf(), json={
        "code": code, "name": code, "asset_type": typ, "purdue_level": "0", "criticality": "medium",
        "ip_address": "10.20.50.10"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def make_credential(env: Env, asset_id: int, **over):  # type: ignore[no-untyped-def]
    body = {"scopes": ["ingest:rf"], "allowed_networks": ["127.0.0.0/8", "testclient/32"][:1], "valid_days": 30}
    body.update(over)
    r = env.client.post(f"/api/v1/assets/{asset_id}/credentials", json=body, headers=env.csrf())
    assert r.status_code == 201, r.text
    return r.json()


def beat(env: Env, key: str, secret: str, *, ts: int | None = None, body: dict | None = None, path: str = PATH,
         client=None, sig_override: str | None = None):  # type: ignore[no-untyped-def]
    payload = json.dumps(body if body is not None else {"status": "ok"}).encode()
    stamp = int(env.clock.now().timestamp()) if ts is None else ts
    headers = signed_headers(key, secret, "POST", path, stamp, payload)
    if sig_override:
        headers["X-Device-Signature"] = sig_override
    headers["Content-Type"] = "application/json"
    return (client or env.client).post(path, content=payload, headers=headers)


def device_client(env: Env):  # type: ignore[no-untyped-def]
    """A client without the administrator's cookie: devices never use sessions."""
    return env.new_client()


def test_secret_is_shown_once_and_stored_encrypted(admin_session: Env):
    env = admin_session
    asset_id = make_sensor(env)
    created = make_credential(env, asset_id)
    assert created["secret"].startswith("ds_") and created["key_id"].startswith("dk_")
    assert "ingest:heartbeat" in created["scopes"]
    listing = env.client.get(f"/api/v1/assets/{asset_id}/credentials")
    assert created["secret"] not in listing.text and "secret" not in listing.json()[0]
    with env.services() as svc:
        stored = svc.session.execute(text("SELECT secret_enc FROM device_credentials")).scalar_one()
        audit = "\n".join(svc.session.execute(text("SELECT details::text FROM audit_log")).scalars())
    assert stored.startswith("enc1:") and created["secret"] not in stored
    assert created["secret"] not in audit


def test_signed_heartbeat_works_and_marks_the_asset_seen(admin_session: Env):
    env = admin_session
    asset_id = make_sensor(env)
    cred = make_credential(env, asset_id)
    r = beat(env, cred["key_id"], cred["secret"], client=device_client(env))
    assert r.status_code == 200 and r.json()["asset"] == "RF-T1"
    seen = env.client.get(f"/api/v1/assets/{asset_id}").json()["last_seen_at"]
    assert seen is not None
    listing = env.client.get(f"/api/v1/assets/{asset_id}/credentials").json()[0]
    assert listing["last_used_at"] is not None and listing["state"] == "active"


def test_every_failure_looks_the_same_and_is_audited(admin_session: Env):
    env = admin_session
    asset_id = make_sensor(env)
    cred = make_credential(env, asset_id)
    c = device_client(env)
    now = int(env.clock.now().timestamp())
    cases = {
        "unknown_key": beat(env, "dk_0000000000000000", cred["secret"], client=c),
        "bad_signature": beat(env, cred["key_id"], "ds_wrong-secret", client=c),
        "stale": beat(env, cred["key_id"], cred["secret"], ts=now - 600, client=c),
        "future": beat(env, cred["key_id"], cred["secret"], ts=now + 600, client=c),
        "missing": c.post(PATH, json={"status": "ok"}),
    }
    for name, r in cases.items():
        assert r.status_code == 401 and r.json() == {"code": "device_auth_failed"}, name
    with env.services() as svc:
        reasons = set(svc.session.execute(text("SELECT reason FROM audit_log WHERE action = 'device.auth_failed'")).scalars())
    assert {"unknown_key", "bad_signature", "timestamp_out_of_window"} <= reasons


def test_replay_of_a_captured_request_is_refused(admin_session: Env):
    env = admin_session
    cred = make_credential(env, make_sensor(env))
    c = device_client(env)
    stamp = int(env.clock.now().timestamp())
    first = beat(env, cred["key_id"], cred["secret"], ts=stamp, client=c)
    again = beat(env, cred["key_id"], cred["secret"], ts=stamp, client=c)
    assert first.status_code == 200 and again.status_code == 401


def test_a_signature_is_bound_to_path_method_and_body(admin_session: Env):
    env = admin_session
    cred = make_credential(env, make_sensor(env))
    c = device_client(env)
    stamp = int(env.clock.now().timestamp())
    good = sign(cred["secret"], "POST", PATH, stamp, json.dumps({"status": "ok"}).encode())
    # same signature, different body
    tampered = beat(env, cred["key_id"], cred["secret"], ts=stamp, body={"status": "evil"}, client=c,
                    sig_override=good)
    assert tampered.status_code == 401
    # same signature on another path
    other = c.post(PATH + "?x=1", content=json.dumps({"status": "ok"}).encode(),
                   headers={**signed_headers(cred["key_id"], cred["secret"], "POST", PATH, stamp,
                                             json.dumps({"status": "ok"}).encode()),
                            "Content-Type": "application/json"})
    assert other.status_code == 401


def test_source_network_and_expiry_are_enforced(admin_session: Env):
    env = admin_session
    c = device_client(env)
    outside = make_credential(env, make_sensor(env, "RF-T2"), allowed_networks=["192.0.2.0/24"])
    assert beat(env, outside["key_id"], outside["secret"], client=c).status_code == 401  # source not allowed
    inside = make_credential(env, make_sensor(env, "RF-T4"), valid_days=1)
    assert beat(env, inside["key_id"], inside["secret"], client=c).status_code == 200
    env.clock.advance(days=2)
    assert beat(env, inside["key_id"], inside["secret"], client=c).status_code == 401  # expired


def test_scope_is_enforced_by_the_authenticator(admin_session: Env):
    env = admin_session
    cred = make_credential(env, make_sensor(env, "RF-T3"), scopes=["ingest:rf"])
    stamp = int(env.clock.now().timestamp())
    signature = sign(cred["secret"], "POST", "/api/v1/ingest/rf", stamp, b"{}")
    with env.services() as svc:
        ok = svc.devices.authenticate(key_id=cred["key_id"], timestamp=str(stamp), signature=signature,
                                      method="POST", target="/api/v1/ingest/rf", body=b"{}",
                                      source_ip="127.0.0.1", required_scope="ingest:rf")
        assert ok.asset_code == "RF-T3" and "ingest:rf" in ok.scopes
    signature2 = sign(cred["secret"], "POST", "/api/v1/ingest/radar", stamp, b"{}")
    import pytest

    from app.core.errors import ApiError

    with pytest.raises(ApiError) as caught:
        with env.services() as svc:
            svc.devices.authenticate(key_id=cred["key_id"], timestamp=str(stamp), signature=signature2,
                                     method="POST", target="/api/v1/ingest/radar", body=b"{}",
                                     source_ip="127.0.0.1", required_scope="ingest:radar")
    assert caught.value.code == "device_auth_failed"


def test_rotation_ends_the_old_key_immediately_or_after_grace(admin_session: Env):
    env = admin_session
    c = device_client(env)
    asset_id = make_sensor(env)
    cred = make_credential(env, asset_id)
    h = env.csrf()
    new = env.client.post(f"/api/v1/credentials/{cred['key_id']}/rotate", json={"grace_minutes": 0}, headers=h).json()
    assert new["key_id"] != cred["key_id"] and new["secret"] != cred["secret"]
    assert beat(env, cred["key_id"], cred["secret"], client=c).status_code == 401
    assert beat(env, new["key_id"], new["secret"], client=c).status_code == 200

    graced = env.client.post(f"/api/v1/credentials/{new['key_id']}/rotate", json={"grace_minutes": 10}, headers=h).json()
    env.clock.advance(seconds=1)  # an identical request in the same second would be refused as a replay
    assert beat(env, new["key_id"], new["secret"], client=c).status_code == 200  # still inside the grace period
    states = {x["key_id"]: x["state"] for x in env.client.get(f"/api/v1/assets/{asset_id}/credentials").json()}
    assert states[new["key_id"]] == "retiring" and states[graced["key_id"]] == "active"
    env.clock.advance(minutes=11)
    assert beat(env, new["key_id"], new["secret"], client=c).status_code == 401
    assert beat(env, graced["key_id"], graced["secret"], client=c).status_code == 200


def test_revoke_and_decommission_end_access(admin_session: Env):
    env = admin_session
    c = device_client(env)
    asset_id = make_sensor(env)
    cred = make_credential(env, asset_id)
    assert env.client.post(f"/api/v1/credentials/{cred['key_id']}/revoke", headers=env.csrf()).status_code == 200
    assert beat(env, cred["key_id"], cred["secret"], client=c).status_code == 401

    second = make_credential(env, asset_id)
    assert beat(env, second["key_id"], second["secret"], client=c).status_code == 200
    env.client.put(f"/api/v1/assets/{asset_id}", json={"status": "decommissioned"}, headers=env.csrf())
    assert beat(env, second["key_id"], second["secret"], client=c).status_code == 401


def test_only_sensors_and_gateways_get_credentials_with_valid_input(admin_session: Env):
    env = admin_session
    plc = env.client.post("/api/v1/assets", headers=env.csrf(), json={
        "code": "PLC-T9", "name": "PLC", "asset_type": "plc"}).json()["id"]
    r = env.client.post(f"/api/v1/assets/{plc}/credentials", headers=env.csrf(),
                        json={"scopes": ["ingest:rf"], "allowed_networks": ["10.0.0.0/8"]})
    assert r.status_code == 422 and r.json()["details"][0]["code"] == "device.type_not_allowed"
    sensor = make_sensor(env)
    for body, code in (
        ({"scopes": [], "allowed_networks": ["10.0.0.0/8"]}, "device.scopes_invalid"),
        ({"scopes": ["ingest:rf"], "allowed_networks": []}, "device.networks_required"),
        ({"scopes": ["ingest:rf"], "allowed_networks": ["not-a-net"]}, "device.networks_invalid"),
        ({"scopes": ["ingest:rf"], "allowed_networks": ["10.0.0.0/8"], "valid_days": 4000}, "device.validity_invalid"),
        ({"scopes": ["root"], "allowed_networks": ["10.0.0.0/8"]}, "device.scopes_invalid"),
    ):
        r = env.client.post(f"/api/v1/assets/{sensor}/credentials", json=body, headers=env.csrf())
        assert r.status_code == 422 and code in {p["code"] for p in r.json()["details"]}, body


def test_device_keys_do_not_open_user_endpoints_and_sessions_do_not_open_device_endpoints(admin_session: Env):
    env = admin_session
    cred = make_credential(env, make_sensor(env))
    c = device_client(env)
    stamp = int(env.clock.now().timestamp())
    headers = signed_headers(cred["key_id"], cred["secret"], "GET", "/api/v1/assets", stamp)
    assert c.get("/api/v1/assets", headers=headers).status_code == 401  # needs a user session
    # an administrator's session is not a device identity
    assert env.client.post(PATH, json={"status": "ok"}, headers=env.csrf()).status_code == 401
