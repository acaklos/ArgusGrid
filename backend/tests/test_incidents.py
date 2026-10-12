"""Correlation of physical tracks and cyber signals into hybrid incidents (ARG-017, ARG-018, ARG-019)."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.signing import signed_headers
from app.correlation import engine as eng
from app.models.mail import MailOutbox
from app.services.demo_service import DemoService
from app.simulator.runner import DeviceKey, run
from tests.conftest import Env

PATH = "/api/v1/ingest/events"
GOOD = "Aa1!bcdefghijkl"


# -- the pure engine -----------------------------------------------------------------------------------
def node(i, code, typ="server", crit="medium", zone="Z2", x=None, y=None, exposure=(), level="3"):
    return eng.Node(i, code, code, typ, level, zone, crit, x, y, tuple(exposure))


GRAPH_NODES = {n.id: n for n in [
    node(1, "AP", "wireless_ap", x=100, y=100, exposure=("wireless",)),
    node(2, "HMI", "hmi"),
    node(3, "SCADA", "server", crit="critical", x=110, y=105),
    node(4, "PLC1", "plc", crit="critical", level="1"),
    node(5, "PLC2", "plc", crit="high", level="1"),
    node(6, "PLC3", "plc", crit="high", level="1"),
    node(7, "HIST", "server", crit="high"),
    node(8, "APP", "server", crit="high"),
]}
GRAPH_EDGES = [
    eng.Edge(1, 2, "wireless_link"), eng.Edge(2, 3, "operator_session"), eng.Edge(3, 4, "control"),
    eng.Edge(3, 5, "control"), eng.Edge(5, 6, "control"), eng.Edge(3, 7, "data_flow"), eng.Edge(7, 8, "data_flow"),
]


def test_blast_radius_hops_impact_and_data_flow_limit():
    radius = {r["asset"]: r for r in eng.blast_radius(3, GRAPH_NODES, GRAPH_EDGES)}
    assert radius["PLC1"]["hop"] == 1 and radius["PLC1"]["impact"] == "control" and radius["PLC1"]["via"] == ["SCADA", "PLC1"]
    assert radius["PLC3"]["hop"] == 2 and radius["PLC3"]["via"] == ["SCADA", "PLC2", "PLC3"]
    assert radius["HIST"]["impact"] == "data" and "APP" not in radius  # data flows do not chain
    ordered = [r["asset"] for r in eng.blast_radius(3, GRAPH_NODES, GRAPH_EDGES)]
    assert ordered.index("PLC1") < ordered.index("PLC3")  # critical and near first


def test_paths_to_finds_the_assets_that_can_reach_the_target():
    paths = eng.paths_to(3, GRAPH_NODES, GRAPH_EDGES)
    assert paths[1] == (1, 2, 3) and paths[2] == (2, 3) and 4 not in paths


def test_physical_link_by_exposure_by_zone_and_not_at_all():
    target = GRAPH_NODES[3]
    near = eng.Track("U1", 105, 100, 30, "Z2", "critical", "critical", "t")
    link = eng.physical_link(near, target, GRAPH_NODES, GRAPH_EDGES, set())
    assert link and link.kind == "proximity" and link.exposure == "wireless" and link.path == (1, 2, 3)
    assert link.distance_m == pytest.approx(5.0, abs=0.1)
    far_same_zone = eng.Track("U1", 900, 900, 30, "Z2", "warning", "warning", "t")
    zone_link = eng.physical_link(far_same_zone, target, GRAPH_NODES, GRAPH_EDGES, set())
    assert zone_link and zone_link.kind == "zone" and zone_link.strength == 0.4
    assert eng.physical_link(far_same_zone, target, GRAPH_NODES, GRAPH_EDGES, {"Z2"}) is None  # background zone
    elsewhere = eng.Track("U1", 900, 900, 30, "Z9", "alert", "info", "t")
    assert eng.physical_link(elsewhere, target, GRAPH_NODES, GRAPH_EDGES, set()) is None


def test_scoring_orders_cases_sensibly():
    target = GRAPH_NODES[3]
    track = eng.Track("U1", 105, 100, 30, "Z2", "critical", "critical", "t")
    link = eng.physical_link(track, target, GRAPH_NODES, GRAPH_EDGES, set())
    zero_day = [eng.Signal(3, "finding", "f", "x", 1.0, {"fix_status": "none"})]
    alarm_and_finding = zero_day + [eng.Signal(3, "alarm", "a", "y", 0.6)]
    weak = [eng.Signal(3, "alarm", "a", "y", 0.4)]
    strong = eng.score_hybrid(link, alarm_and_finding, target)
    mid = eng.score_hybrid(link, zero_day, target)
    low = eng.score_hybrid(link, weak, target)
    assert strong > mid > low and strong <= 100
    assert eng.severity_from_score(strong) == "critical"
    assert eng.severity_from_score(35) == "low" and eng.severity_from_score(65) == "high"
    assert eng.score_physical(track, "critical") <= 85 and eng.score_cyber(zero_day, target) <= 75


def test_recommendations_depend_on_the_evidence():
    target = GRAPH_NODES[3]
    track = eng.Track("U1", 105, 100, 30, "Z2", "critical", "critical", "t")
    link = eng.physical_link(track, target, GRAPH_NODES, GRAPH_EDGES, set())
    sigs = [eng.Signal(3, "finding", "f", "x", 1.0, {"fix_status": "none"})]
    radius = eng.blast_radius(3, GRAPH_NODES, GRAPH_EDGES)
    recs = eng.recommendations(incident_type="hybrid", severity="critical", zone="Z2", target=target, link=link,
                               link_node=GRAPH_NODES[1], signals=sigs, radius=radius, remote_access_sources=["JUMP"])
    codes = [r["code"] for r in recs]
    assert {"dispatch_security", "disable_wireless", "isolate_asset", "request_vendor_mitigation",
            "restrict_remote_access", "verify_controller_integrity", "notify_dispatcher"} <= set(codes)
    assert next(r for r in recs if r["code"] == "disable_wireless")["asset"] == "AP"


# -- with the demo site --------------------------------------------------------------------------------
@pytest.fixture()
def site(admin_session: Env):  # type: ignore[no-untyped-def]
    env = admin_session
    env.make_user("mgr", "SOC Manager")
    env.make_user("ana", "SOC Analyst")
    env.make_user("op", "SOC Operator")
    with env.services() as svc:
        from app.models.identity import User

        for name in ("mgr", "ana"):  # the operator keeps the default address of the test helper
            u = svc.session.execute(select(User).where(User.username_key == name)).scalar_one()
            u.email = f"{name}@example.test"
        report = DemoService(svc.session, env.clock, svc.box, svc.audit, svc.intel).create()
    keys = {code: DeviceKey(k, s) for code, (k, s) in report.secrets.items()}
    return env, keys


def post(env: Env, key: DeviceKey, events: list[dict], offset: int = 0):  # type: ignore[no-untyped-def]
    body = json.dumps({"events": events}, separators=(",", ":")).encode()
    stamp = int(env.clock.now().timestamp()) + offset
    headers = signed_headers(key.key_id, key.secret, "POST", PATH, stamp, body)
    headers["Content-Type"] = "application/json"
    r = env.new_client().post(PATH, content=body, headers=headers)
    assert r.status_code == 200, r.text
    return r


def drone(x: float, y: float, **over):  # type: ignore[no-untyped-def]
    ev = {"kind": "radar", "type": "track", "track_id": "UAV-001", "x": x, "y": y, "altitude": 30, "speed": 1,
          "heading": 90, "confidence": 0.9}
    ev.update(over)
    return ev


def run_correlation(env: Env) -> dict:
    """Force a run. The ingestion call already correlated, so report every open incident as `created`
    that did not exist before this helper was last used (the helper is called once per scenario step)."""
    before = {i["id"] for i in env.client.get("/api/v1/incidents", params={"page_size": 200}).json()["items"]}
    result = env.client.post("/api/v1/incidents/run", headers=env.csrf()).json()
    after = env.client.get("/api/v1/incidents", params={"page_size": 200}).json()["items"]
    known = getattr(env, "_seen_incidents", set())
    new_ids = [i["id"] for i in after if i["id"] not in known]
    env._seen_incidents = known | {i["id"] for i in after}  # type: ignore[attr-defined]
    assert before <= {i["id"] for i in after}
    return {"created": new_ids, "updated": result["updated"]}


def incidents(env: Env, **params) -> list[dict]:  # type: ignore[no-untyped-def]
    return env.client.get("/api/v1/incidents", params=params).json()["items"]


def test_a_drone_at_the_wireless_access_point_and_a_zero_day_raise_a_critical_hybrid_incident(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(470, 322)])
    created = run_correlation(env)["created"]
    assert len(created) == 1
    inc = env.client.get(f"/api/v1/incidents/{created[0]}").json()
    assert inc["type"] == "hybrid" and inc["code"].startswith("HYB-") and inc["status"] == "new"
    assert inc["severity"] == "critical" and inc["zone"] == "Z2" and inc["primary_asset"] == "SCADA-SRV-01"
    link = inc["evidence"]["physical"]["link"]
    # the maintenance access point and the maintenance tablet are both wireless and both within reach
    assert link["exposure"] == "wireless" and link["exposed_asset"] in ("WIFI-AP-MNT", "HMI-03")
    assert {c["asset"] for c in link["candidates"]} >= {"WIFI-AP-MNT", "HMI-03"} and link["distance_m"] < 40
    assert link["path"][-1] == "SCADA-SRV-01"
    findings = inc["evidence"]["cyber"]["findings"]
    assert any(f["vuln_id"] == "DEMO-2026-0001" and f["classification"] == "zero_day" for f in findings)
    radius = {r["asset"]: r for r in inc["blast_radius"]}
    assert radius["PLC-SW1"]["hop"] == 1 and radius["PLC-SW1"]["impact"] == "control"
    assert radius["PLC-GT1"]["hop"] == 1 and radius["SCADA-SRV-02"]["hop"] == 1
    codes = [r["code"] for r in inc["recommendations"]]
    assert {"dispatch_security", "disable_wireless", "isolate_asset", "request_vendor_mitigation",
            "verify_controller_integrity", "notify_dispatcher"} <= set(codes)
    wireless = {r["asset"] for r in inc["recommendations"] if r["code"] == "disable_wireless"}
    assert wireless == {"WIFI-AP-MNT", "HMI-03"}
    assert [e["kind"] for e in inc["timeline"]][:1] == ["created"]


def test_the_cyber_alarm_raises_the_score_and_both_sources_are_in_the_evidence(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(470, 322)])
    first = env.client.get(f"/api/v1/incidents/{run_correlation(env)['created'][0]}").json()
    post(env, keys["SENS-GW-01"], [{"kind": "cyber", "type": "alarm", "severity": "warning",
                                    "data": {"asset": "SCADA-SRV-01", "source": "WIFI-AP-MNT",
                                             "summary": "unusual connection"}}], offset=1)
    run_correlation(env)
    again = env.client.get(f"/api/v1/incidents/{first['id']}").json()
    assert len(incidents(env)) == 1  # the same incident, not a second one
    assert again["score"] >= first["score"]
    alarms = again["evidence"]["cyber"]["alarms"]
    assert alarms and alarms[0]["source"] == "WIFI-AP-MNT"


def test_no_incident_without_a_link_far_drone_or_quiet_site(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(1400, 800)])  # in the alert ring, far from every exposed asset
    assert run_correlation(env) == {"created": [], "updated": []}
    assert incidents(env) == []


def test_zone_link_is_weaker_than_a_proximity_link(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(330, 440)])  # inside Z2 but more than 150 m from the access point
    created = run_correlation(env)["created"]
    inc = env.client.get(f"/api/v1/incidents/{created[0]}").json()
    assert inc["type"] == "hybrid" and inc["evidence"]["physical"]["link"]["kind"] == "zone"
    assert inc["score"] < 90


def test_cyber_alarm_alone_is_a_cyber_incident_and_a_drone_alone_a_physical_one(site):  # type: ignore[no-untyped-def]
    env, keys = site
    # remove the exploited finding so only the alarm remains
    with env.services() as svc:
        from app.models.intel import Finding

        svc.session.query(Finding).delete()
    post(env, keys["SENS-GW-01"], [{"kind": "cyber", "type": "alarm", "severity": "critical",
                                    "data": {"asset": "HIST-01", "summary": "odd traffic"}}])
    created = run_correlation(env)["created"]
    cyber = env.client.get(f"/api/v1/incidents/{created[0]}").json()
    assert cyber["type"] == "cyber" and cyber["code"].startswith("CYB-") and cyber["score"] <= 75

    post(env, keys["RAD-01"], [drone(700, 150, track_id="UAV-002")], offset=1)  # over the switchyard (critical zone)
    physical = [i for i in incidents(env) if i["type"] == "physical"]
    run_correlation(env)
    physical = [i for i in incidents(env) if i["type"] == "physical"]
    assert len(physical) == 1 and physical[0]["code"].startswith("PHY-") and physical[0]["zone"] == "Z4"


def test_a_hybrid_incident_replaces_the_physical_one_of_the_same_track(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(470, 322)])
    run_correlation(env)
    types = {i["type"] for i in incidents(env)}
    assert types == {"hybrid"}


def test_alert_mail_goes_to_people_who_can_triage_and_has_the_incident_in_it(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(470, 322)])
    run_correlation(env)
    with env.services() as svc:
        rows = list(svc.session.execute(select(MailOutbox).where(MailOutbox.template_key == "incident.hybrid")).scalars())
    assert {r.to_address for r in rows} == {"mgr@example.test", "ana@example.test", "op@example.test"}
    assert all("HYB-" in r.subject for r in rows)
    run_correlation(env)  # a second run does not send again
    with env.services() as svc:
        again = svc.session.execute(select(MailOutbox).where(MailOutbox.template_key == "incident.hybrid")).scalars().all()
    assert len(again) == len(rows)


def test_workflow_transitions_capabilities_notes_and_audit(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(470, 322)])
    iid = run_correlation(env)["created"][0]
    op = env.new_client()
    env.login("op", GOOD, op)
    oh = env.csrf(op)
    url = f"/api/v1/incidents/{iid}"
    assert op.post(f"{url}/status", json={"status": "triaged", "note": "looking"}, headers=oh).status_code == 200
    assert op.post(f"{url}/status", json={"status": "closed"}, headers=oh).status_code == 403  # needs incident.close
    assert op.post(f"{url}/escalate", json={"text": "x"}, headers=oh).status_code == 403
    assert op.post(f"{url}/status", json={"status": "new"}, headers=oh).status_code == 409  # not a valid step
    assert op.post(f"{url}/notes", json={"text": "Guard dispatched"}, headers=oh).status_code == 200
    detail = op.get(url).json()
    assert detail["status"] == "triaged" and detail["assigned_to"] == "op"
    assert [e["kind"] for e in detail["timeline"]][-2:] == ["status", "note"]

    mgr = env.new_client()
    env.login("mgr", GOOD, mgr)
    mh = env.csrf(mgr)
    escalated = mgr.post(f"{url}/status", json={"status": "investigating"}, headers=mh)
    assert escalated.status_code == 200
    closed = mgr.post(f"{url}/status", json={"status": "closed", "note": "false alarm, tablet of the engineer"}, headers=mh)
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    assert mgr.post(f"{url}/status", json={"status": "investigating"}, headers=mh).status_code == 409  # final
    assert "incident.status" in env.audit_actions() and "incident.note" in env.audit_actions()


def test_escalation_raises_severity_and_alerts_managers(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(330, 440)])  # a lower-scored zone link
    iid = run_correlation(env)["created"][0]
    before = env.client.get(f"/api/v1/incidents/{iid}").json()["severity"]
    ana = env.new_client()
    env.login("ana", GOOD, ana)
    r = ana.post(f"/api/v1/incidents/{iid}/escalate", json={"text": "needs the manager"}, headers=env.csrf(ana))
    assert r.status_code == 200 and r.json()["escalated"] is True
    order = ["low", "medium", "high", "critical"]
    assert order.index(r.json()["severity"]) == min(3, order.index(before) + 1)
    with env.services() as svc:
        subjects = [m.subject for m in svc.session.execute(select(MailOutbox).where(
            MailOutbox.template_key == "incident.hybrid", MailOutbox.to_address == "mgr@example.test")).scalars()]
    assert any("ESCALATED" in s or "HYB-" in s for s in subjects)


def test_closed_incidents_do_not_flap_but_a_new_one_follows_later(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(470, 322)])
    first = run_correlation(env)["created"][0]
    env.client.post(f"/api/v1/incidents/{first}/status", json={"status": "closed", "note": "done"}, headers=env.csrf())
    post(env, keys["RAD-01"], [drone(471, 322)], offset=1)
    assert run_correlation(env)["created"] == []  # inside the guard time
    env.clock.advance(minutes=31)
    assert env.login(env.admin_username, env.admin_password).status_code == 200
    post(env, keys["RAD-01"], [drone(472, 322)])
    assert len(run_correlation(env)["created"]) == 1


def test_graph_for_the_cyber_pane(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(470, 322)])
    iid = run_correlation(env)["created"][0]
    g = env.client.get(f"/api/v1/incidents/{iid}/graph").json()
    roles = {n["code"]: n["role"] for n in g["nodes"]}
    assert roles["UAV-001"] == "physical_event" and roles["WIFI-AP-MNT"] == "entry" and roles["HMI-03"] == "entry"
    assert roles["SCADA-SRV-01"] == "compromised" and roles["PLC-SW1"] == "at_risk" and roles["PLC-GT1"] == "at_risk"
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])
    hybrid = [e for e in g["edges"] if e["kind"] == "hybrid"]
    assert len(hybrid) >= 2 and all(e["source"] == "event" for e in hybrid)
    scada = next(n for n in g["nodes"] if n["code"] == "SCADA-SRV-01")["id"]
    assert any(e["kind"] == "relation" and e["source"] == scada and e["relation"] == "control" for e in g["edges"])


def test_incidents_are_published_on_the_stream(site):  # type: ignore[no-untyped-def]
    env, keys = site
    with env.client.websocket_connect("/api/v1/stream") as ws:
        assert ws.receive_json() == {"type": "hello"}
        post(env, keys["RAD-01"], [drone(470, 322)])
        seen = []
        for _ in range(4):
            seen.append(ws.receive_json())
            if any(m.get("type") == "incident" for m in seen):
                break
    incident = next(m for m in seen if m["type"] == "incident")
    assert incident["created"] is True and incident["incident"]["severity"] == "critical"


def test_incident_views_need_the_capability(site):  # type: ignore[no-untyped-def]
    env, _keys = site
    from app.models.identity import Role, RolePermission

    with env.services() as svc:
        role = Role(name="Blind", description="", security_level=5, is_system=False)
        role.permissions = [RolePermission(permission="user.view")]
        svc.session.add(role)
    env.make_user("blind", "Blind")
    c = env.new_client()
    env.login("blind", GOOD, c)
    assert c.get("/api/v1/incidents").status_code == 403
    assert c.get("/api/v1/incidents/overview").status_code == 403
    assert env.new_client().get("/api/v1/incidents").status_code == 401


def test_simulated_attack_produces_the_expected_incident_end_to_end(site, monkeypatch):  # type: ignore[no-untyped-def]
    import app.api.deps as deps

    env, keys = site
    monkeypatch.setattr(deps, "DEVICE_LIMIT_PER_KEY_PER_MINUTE", 1_000_000)
    monkeypatch.setattr(deps, "DEVICE_LIMIT_PER_IP_PER_MINUTE", 1_000_000)
    client = env.new_client()

    def poster(path: str, content: bytes, headers: dict[str, str]) -> int:
        return client.post(path, content=content, headers=headers).status_code

    stats = run(keys, poster, tick_s=5.0, until=330, sleep=lambda _s: None,
                now=lambda: env.clock.now().timestamp(), on_progress=lambda t, n: env.clock.advance(seconds=5))
    assert stats.failed_requests == 0
    run_correlation(env)
    hybrid = [i for i in incidents(env) if i["type"] == "hybrid"]
    assert len(hybrid) == 1
    detail = env.client.get(f"/api/v1/incidents/{hybrid[0]['id']}").json()
    assert detail["severity"] == "critical" and detail["evidence"]["cyber"]["alarms"]


def test_a_moving_track_does_not_flood_the_timeline(site):  # type: ignore[no-untyped-def]
    env, keys = site
    post(env, keys["RAD-01"], [drone(470, 322)])
    created = run_correlation(env)["created"]
    for step in range(1, 8):
        env.clock.advance(seconds=1)
        post(env, keys["RAD-01"], [drone(470 + step, 322)])
        env.client.post("/api/v1/incidents/run", headers=env.csrf())  # forced: the ingestion run is rate limited
    detail = env.client.get(f"/api/v1/incidents/{created[0]}").json()
    updates = [e for e in detail["timeline"] if e["kind"] == "update"]
    assert len(updates) <= 1
    # the stored position is still refreshed once the interval has passed
    env.clock.advance(seconds=30)
    post(env, keys["RAD-01"], [drone(500, 322)])
    env.client.post("/api/v1/incidents/run", headers=env.csrf())
    detail = env.client.get(f"/api/v1/incidents/{created[0]}").json()
    assert detail["evidence"]["physical"]["track"]["x"] == 500
