"""Telemetry ingestion, classification, partitions, state, live stream, simulator (ARG-014, ARG-015, ARG-025)."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.signing import signed_headers
from app.services import airspace as air
from app.services.demo_service import DemoService
from app.simulator.runner import DeviceKey, run
from tests.conftest import Env

PATH = "/api/v1/ingest/events"
GOOD = "Aa1!bcdefghijkl"


@pytest.fixture()
def site(admin_session: Env):  # type: ignore[no-untyped-def]
    """The demo site with device keys: returns (env, {asset code: DeviceKey})."""
    env = admin_session
    with env.services() as svc:
        report = DemoService(svc.session, env.clock, svc.box, svc.audit).create()
    keys = {code: DeviceKey(k, s) for code, (k, s) in report.secrets.items()}
    return env, keys


def post_events(env: Env, key: DeviceKey, events: list[dict], *, client=None, offset: int = 0):  # type: ignore[no-untyped-def]
    body = json.dumps({"events": events}, separators=(",", ":")).encode()
    stamp = int(env.clock.now().timestamp()) + offset
    headers = signed_headers(key.key_id, key.secret, "POST", PATH, stamp, body)
    headers["Content-Type"] = "application/json"
    return (client or env.new_client()).post(PATH, content=body, headers=headers)


def radar(x: float, y: float, **over):  # type: ignore[no-untyped-def]
    ev = {"kind": "radar", "type": "track", "track_id": "UAV-001", "x": x, "y": y, "altitude": 30,
          "speed": 5, "heading": 90, "confidence": 0.9}
    ev.update(over)
    return ev


# -- pure classification -----------------------------------------------------------------------------
def test_ring_and_zone_classification():
    cfg = air.AirspaceConfig()
    zones = [
        air.ZoneShape("Z0", "low", ((0, 0), (1000, 0), (1000, 700), (0, 700))),
        air.ZoneShape("Z2", "critical", ((300, 220), (620, 220), (620, 460), (300, 460))),
        air.ZoneShape("Z6", "high", ((660, 420), (1000, 420), (1000, 700), (660, 700))),
    ]
    centre = air.classify(500, 350, 30, cfg, zones)
    assert (centre["ring"], centre["zone"], centre["severity"]) == ("critical", "Z2", "critical")
    mast = air.classify(940, 660, 30, cfg, zones)  # about 540 m from the centre: inside the warning ring
    assert (mast["zone"], mast["ring"]) == ("Z6", "warning") and mast["severity"] == "warning"
    gate = air.classify(30, 30, 30, cfg, zones)  # about 590 m away, still inside the warning ring
    assert gate["ring"] == "warning" and gate["zone"] == "Z0"
    outer = air.classify(1300, 800, 30, cfg, zones)
    assert outer["ring"] == "alert" and outer["severity"] == "info"
    near = air.classify(1042, 607, 80, cfg, zones)  # about 600 m from the centre, outside every sector but Z0
    assert near["ring"] in ("warning", "alert") and near["zone"] is None
    far = air.classify(2300, 350, 30, cfg, zones)
    assert far["ring"] == "outside" and far["severity"] == "info"
    assert air.classify(500, 350, 400, cfg, zones)["above_ceiling"] is True


def test_smallest_zone_wins_and_edges_count_as_inside():
    big = air.ZoneShape("A", "low", ((0, 0), (100, 0), (100, 100), (0, 100)))
    small = air.ZoneShape("B", "high", ((10, 10), (20, 10), (20, 20), (10, 20)))
    assert air.zone_at(15, 15, [big, small]).code == "B"
    assert air.zone_at(50, 50, [big, small]).code == "A"
    assert air.zone_at(10, 15, [big, small]).code == "B"  # on the edge
    assert air.zone_at(500, 500, [big, small]) is None


# -- partitions and storage --------------------------------------------------------------------------
def test_events_land_in_the_daily_partition_and_old_ones_in_default(site):  # type: ignore[no-untyped-def]
    env, keys = site
    r = post_events(env, keys["RAD-01"], [radar(470, 322)])
    assert r.status_code == 200 and r.json() == {"accepted": 1, "rejected": []}
    old_ts = (env.clock.now() - timedelta(minutes=30)).isoformat()
    assert post_events(env, keys["RAD-01"], [radar(480, 330, ts=old_ts)], client=env.new_client(), offset=1) \
        .json()["accepted"] == 1
    with env.services() as svc:
        today = env.clock.now().date()
        name = svc.telemetry.partition_name(today)
        rows = svc.session.execute(text(
            "SELECT tableoid::regclass::text, count(*) FROM telemetry_events GROUP BY 1")).all()
        counts = {n: c for n, c in rows}
        assert counts.get(name, 0) >= 1
        parts = [d for _n, d in svc.telemetry.list_partitions()]
        assert today in parts and today + timedelta(days=2) in parts


def test_event_is_stored_against_the_authenticated_device_with_zone_and_severity(site):  # type: ignore[no-untyped-def]
    env, keys = site
    assert post_events(env, keys["RAD-01"], [radar(470, 322)]).status_code == 200
    with env.services() as svc:
        row = svc.session.execute(text(
            "SELECT a.code, t.zone_code, t.severity, t.kind, t.track_id FROM telemetry_events t "
            "JOIN assets a ON a.id = t.asset_id")).one()
    assert tuple(row) == ("RAD-01", "Z2", "critical", "radar", "UAV-001")


def test_a_device_cannot_name_another_asset(site):  # type: ignore[no-untyped-def]
    env, keys = site
    r = post_events(env, keys["RAD-01"], [radar(470, 322) | {"asset": "RF-02"}])
    assert r.status_code == 422  # unknown field: the asset always comes from the key


@pytest.mark.parametrize(
    "event,code",
    [
        ({"kind": "laser", "type": "track", "x": 1, "y": 1}, "event.kind_invalid"),
        ({"kind": "radar", "type": "teleport", "x": 1, "y": 1}, "event.type_invalid"),
        ({"kind": "radar", "type": "track", "x": 99999, "y": 1}, "event.position_out_of_range"),
        ({"kind": "radar", "type": "track", "x": 1}, "event.position_incomplete"),
        ({"kind": "radar", "type": "track"}, "event.position_required"),
        ({"kind": "radar", "type": "track", "x": 1, "y": 1, "confidence": 2}, "event.confidence_invalid"),
        ({"kind": "radar", "type": "track", "x": 1, "y": 1, "heading": 400}, "event.heading_invalid"),
        ({"kind": "radar", "type": "track", "x": 1, "y": 1, "track_id": "bad id!"}, "event.track_id_invalid"),
        ({"kind": "radar", "type": "track", "x": 1, "y": 1, "ts": "2001-01-01T00:00:00+00:00"},
         "event.timestamp_invalid"),
        ({"kind": "radar", "type": "track", "x": 1, "y": 1, "data": {"blob": "x" * 5000}}, "event.data_invalid"),
    ],
)
def test_invalid_events_are_rejected_with_codes_and_valid_ones_still_accepted(site, event, code):  # type: ignore[no-untyped-def]
    env, keys = site
    r = post_events(env, keys["RAD-01"], [radar(470, 322), event])
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 1 and body["rejected"][0]["index"] == 1 and code in body["rejected"][0]["codes"]


def test_a_device_may_only_report_what_its_scopes_allow(site):  # type: ignore[no-untyped-def]
    env, keys = site
    r = post_events(env, keys["RF-02"], [radar(470, 322)])  # an RF detector sending radar data
    assert r.status_code == 200 and r.json()["accepted"] == 0
    assert "event.scope_missing" in r.json()["rejected"][0]["codes"]
    assert "device.scope_violation" in env.audit_actions()


def test_batch_limit_and_signature_requirements(site):  # type: ignore[no-untyped-def]
    env, keys = site
    too_many = post_events(env, keys["RAD-01"], [radar(470, 322)] * 101)
    assert too_many.status_code == 422
    unsigned = env.new_client().post(PATH, json={"events": [radar(470, 322)]})
    assert unsigned.status_code == 401
    # an administrator session is not a device
    assert env.client.post(PATH, json={"events": [radar(470, 322)]}, headers=env.csrf()).status_code == 401


# -- reading ------------------------------------------------------------------------------------------
def test_state_reports_tracks_threatened_zone_sensors_and_alarms(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post_events(env, keys["RAD-01"], [radar(470, 322), radar(1042, 607, track_id="UAV-002")])
    post_events(env, keys["SENS-GW-01"], [{"kind": "cyber", "type": "alarm", "severity": "warning",
                                           "data": {"asset": "SCADA-SRV-01"}}], offset=1)
    state = env.client.get("/api/v1/telemetry/state").json()
    tracks = {t["track_id"]: t for t in state["tracks"]}
    assert tracks["UAV-001"]["zone"] == "Z2" and tracks["UAV-001"]["severity"] == "critical"
    assert tracks["UAV-001"]["active"] is True and tracks["UAV-001"]["asset"] == "RAD-01"
    assert {"zone": "Z2", "severity": "critical"} in state["threatened_zones"]
    radar_sensor = next(s for s in state["sensors"] if s["code"] == "RAD-01")
    assert radar_sensor["online"] is True
    assert any(s["online"] is False for s in state["sensors"])
    assert any(a["kind"] == "cyber" for a in state["alarms"])
    assert state["airspace"]["alert_m"] == 1500


def test_tracks_age_out_of_the_active_set_and_history_is_ordered(site):  # type: ignore[no-untyped-def]
    env, keys = site
    for i, x in enumerate((900, 800, 700)):
        env.clock.advance(seconds=2)
        post_events(env, keys["RAD-01"], [radar(x, 500)], offset=i)
    history = env.client.get("/api/v1/telemetry/tracks/UAV-001").json()
    assert [p["x"] for p in history] == [900, 800, 700]
    env.clock.advance(minutes=3)
    tracks = env.client.get("/api/v1/telemetry/state").json()["tracks"]
    assert tracks and tracks[0]["active"] is False
    assert env.client.get("/api/v1/telemetry/state").json()["threatened_zones"] == []


def test_event_listing_filters(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post_events(env, keys["RAD-01"], [radar(470, 322), radar(1400, 700, track_id="UAV-009")])
    allr = env.client.get("/api/v1/telemetry/events").json()
    assert allr["total"] == 2
    crit = env.client.get("/api/v1/telemetry/events", params={"severity": "critical"}).json()
    assert crit["total"] == 1 and crit["items"][0]["track_id"] == "UAV-001"
    one = env.client.get("/api/v1/telemetry/events", params={"track_id": "UAV-009"}).json()
    assert one["total"] == 1


def test_site_endpoint_and_airspace_settings(site):  # type: ignore[no-untyped-def]
    env, _ = site
    data = env.client.get("/api/v1/site").json()
    assert data["name"] == "Kestrel Ridge Energy Complex" and len(data["buildings"]) > 10
    assert {z["code"] for z in data["zones"]} >= {"Z1", "Z2", "Z4"}
    cfg = data["airspace"]
    cfg["warning_m"] = 700
    assert env.client.put("/api/v1/settings/airspace", json=cfg, headers=env.csrf()).status_code == 200
    cfg["critical_m"] = 800  # above the warning ring
    bad = env.client.put("/api/v1/settings/airspace", json=cfg, headers=env.csrf())
    assert bad.status_code == 422 and bad.json()["details"][0]["code"] == "airspace.rings_order"


def test_telemetry_reading_needs_the_asset_view_capability(site):  # type: ignore[no-untyped-def]
    env, keys = site
    env.make_user("op", "SOC Operator")
    c = env.new_client()
    env.login("op", GOOD, c)
    assert c.get("/api/v1/telemetry/state").status_code == 200
    from app.models.identity import Role, RolePermission

    with env.services() as svc:
        role = Role(name="Blind", description="", security_level=5, is_system=False)
        role.permissions = [RolePermission(permission="user.view")]
        svc.session.add(role)
    env.make_user("blind", "Blind")
    b = env.new_client()
    env.login("blind", GOOD, b)
    assert b.get("/api/v1/telemetry/state").status_code == 403
    # a device key cannot read telemetry
    device = env.new_client()
    stamp = int(env.clock.now().timestamp())
    headers = signed_headers(keys["RAD-01"].key_id, keys["RAD-01"].secret, "GET", "/api/v1/telemetry/state", stamp)
    assert device.get("/api/v1/telemetry/state", headers=headers).status_code == 401


# -- live stream ------------------------------------------------------------------------------------
def test_stream_pushes_ingested_events_to_an_authenticated_client(site):  # type: ignore[no-untyped-def]
    env, keys = site
    with env.client.websocket_connect("/api/v1/stream") as ws:
        assert ws.receive_json() == {"type": "hello"}
        r = post_events(env, keys["RAD-01"], [radar(470, 322)])
        assert r.status_code == 200
        message = ws.receive_json()
    assert message["type"] == "telemetry"
    event = message["events"][0]
    assert event["asset"] == "RAD-01" and event["zone"] == "Z2" and event["severity"] == "critical"


def test_stream_refuses_anonymous_and_foreign_origin(site):  # type: ignore[no-untyped-def]
    from starlette.websockets import WebSocketDisconnect

    env, _ = site
    anonymous = env.new_client()
    with pytest.raises(WebSocketDisconnect):
        with anonymous.websocket_connect("/api/v1/stream"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with env.client.websocket_connect("/api/v1/stream", headers={"origin": "http://evil.example"}):
            pass


# -- retention ---------------------------------------------------------------------------------------
def test_retention_drops_whole_old_partitions(site):  # type: ignore[no-untyped-def]
    env, _ = site
    with env.services() as svc:
        old_day = (env.clock.now() - timedelta(days=45)).date()
        svc.telemetry.ensure_partitions(old_day, old_day)
        svc.session.execute(text(
            "INSERT INTO telemetry_events (ts, received_at, asset_id, kind, event_type, severity) "
            "SELECT :ts, :ts, id, 'weather', 'status', 'info' FROM assets LIMIT 1"),
            {"ts": env.clock.now() - timedelta(days=45)})
        svc.telemetry.ensure_current()
        before = [d for _n, d in svc.telemetry.list_partitions()]
        assert old_day in before
        result = svc.telemetry.purge(retention_days=30)
        after = [d for _n, d in svc.telemetry.list_partitions()]
    assert result["partitions_dropped"] >= 1 and old_day not in after
    assert env.clock.now().date() in after


# -- simulator end to end ----------------------------------------------------------------------------
def test_simulator_drives_the_real_api_and_flags_the_control_building(site, monkeypatch):  # type: ignore[no-untyped-def]
    import app.api.deps as deps

    env, keys = site
    monkeypatch.setattr(deps, "DEVICE_LIMIT_PER_KEY_PER_MINUTE", 1_000_000)
    monkeypatch.setattr(deps, "DEVICE_LIMIT_PER_IP_PER_MINUTE", 1_000_000)
    client = env.new_client()

    failures: list[tuple[int, str]] = []

    def poster(path: str, content: bytes, headers: dict[str, str]) -> int:
        r = client.post(path, content=content, headers=headers)
        if r.status_code != 200:
            failures.append((r.status_code, r.text[:120]))
        return r.status_code

    # the fake clock follows simulated time, as real time does: identical requests never share a second
    stats = run(keys, poster, speed=1.0, tick_s=2.0, until=300, sleep=lambda _s: None,
                now=lambda: env.clock.now().timestamp(), on_progress=lambda t, n: env.clock.advance(seconds=2))
    assert stats.failed_requests == 0 and not stats.unknown_devices, failures[:3]
    assert stats.sent_events > 300
    state = env.client.get("/api/v1/telemetry/state").json()
    uav = next(t for t in state["tracks"] if t["track_id"] == "UAV-001")
    assert uav["zone"] == "Z2" and uav["severity"] == "critical" and 20 <= uav["altitude"] <= 40
    assert {"zone": "Z2", "severity": "critical"} in state["threatened_zones"]
    assert any(a["kind"] == "cyber" for a in state["alarms"])
    kinds = {e["kind"] for e in env.client.get("/api/v1/telemetry/events", params={"page_size": 200}).json()["items"]}
    assert {"radar", "rf", "eoir"} <= kinds
