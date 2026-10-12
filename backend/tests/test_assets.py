"""Asset registry (ARG-012): CRUD, validation, lifecycle, software, relations, topology, RBAC, audit."""
from __future__ import annotations

import pytest

from tests.conftest import Env

GOOD = "Aa1!bcdefghijkl"


def client_for(env: Env, username: str):  # type: ignore[no-untyped-def]
    c = env.new_client()
    assert env.login(username, GOOD, c).status_code == 200
    return c, env.csrf(c)


def asset_body(**over):  # type: ignore[no-untyped-def]
    body = {"code": "PLC-T1", "name": "Test controller", "asset_type": "plc", "purdue_level": "1",
            "criticality": "high", "ip_address": "10.20.40.99", "exposure": ["physical_access"],
            "protocols": ["Modbus/TCP"], "vendor": "Voltek", "firmware_version": "1.0"}
    body.update(over)
    return body


def make_zone(env: Env, code: str = "ZT") -> None:
    from app.models.assets import Zone

    with env.services() as svc:
        svc.session.add(Zone(code=code, name="Test zone", criticality="medium",
                             polygon=[[0, 0], [10, 0], [10, 10], [0, 10]]))


def test_create_read_update_with_audit_diff(admin_session: Env):
    env = admin_session
    make_zone(env)
    h = env.csrf()
    r = env.client.post("/api/v1/assets", json=asset_body(zone="ZT"), headers=h)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["category"] == "device" and created["zone"] == "ZT" and created["status"] == "active"
    got = env.client.get(f"/api/v1/assets/{created['id']}").json()
    assert got["code"] == "PLC-T1" and got["relations"] == {"outgoing": [], "incoming": []}
    upd = env.client.put(f"/api/v1/assets/{created['id']}", json={"firmware_version": "1.1", "criticality": "critical"},
                         headers=h)
    assert upd.status_code == 200 and upd.json()["firmware_version"] == "1.1"
    from sqlalchemy import select

    from app.models.system import AuditRecord

    with env.services() as svc:
        row = svc.session.execute(select(AuditRecord).where(AuditRecord.action == "asset.update")).scalar_one()
    assert row.changes == {"criticality": {"old": "high", "new": "critical"},
                           "firmware_version": {"old": "1.0", "new": "1.1"}}


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"code": "bad code!"}, "asset.code_invalid"),
        ({"asset_type": "toaster"}, "asset.type_invalid"),
        ({"ip_address": "10.20.300.1"}, "asset.ip_invalid"),
        ({"mac_address": "zz:zz"}, "asset.mac_invalid"),
        ({"criticality": "extreme"}, "asset.criticality_invalid"),
        ({"exposure": ["telepathy"]}, "asset.exposure_invalid"),
        ({"purdue_level": "9"}, "asset.level_invalid"),
        ({"x": "left"}, "asset.coordinate_invalid"),
        ({"zone": "NOPE"}, "asset.zone_unknown"),
    ],
)
def test_validation_names_the_field(admin_session: Env, changes, code):  # type: ignore[no-untyped-def]
    env = admin_session
    r = env.client.post("/api/v1/assets", json=asset_body(**changes), headers=env.csrf())
    assert r.status_code == 422, r.text
    problems = r.json()["details"]
    assert code in {p["code"] for p in problems} and all(p["fields"] for p in problems)


def test_duplicate_code_unknown_fields_and_stable_code(admin_session: Env):
    env = admin_session
    h = env.csrf()
    first = env.client.post("/api/v1/assets", json=asset_body(), headers=h).json()
    assert env.client.post("/api/v1/assets", json=asset_body(code="plc-t1"), headers=h).status_code == 409
    assert env.client.post("/api/v1/assets", json=asset_body(code="X-2", is_demo=True), headers=h).status_code == 422
    # the identifier cannot be changed
    assert env.client.put(f"/api/v1/assets/{first['id']}", json={"code": "OTHER"}, headers=h).status_code == 422


def test_lifecycle_transitions_and_delete_rules(admin_session: Env):
    env = admin_session
    h = env.csrf()
    a = env.client.post("/api/v1/assets", json=asset_body(), headers=h).json()
    url = f"/api/v1/assets/{a['id']}"
    assert env.client.delete(url, headers=h).json()["code"] == "asset.delete_requires_decommission"
    assert env.client.put(url, json={"status": "maintenance"}, headers=h).status_code == 200
    assert env.client.put(url, json={"status": "planned"}, headers=h).status_code == 422  # not a valid step
    assert env.client.put(url, json={"status": "decommissioned"}, headers=h).status_code == 200
    assert env.client.put(url, json={"status": "active"}, headers=h).status_code == 422  # final state
    assert env.client.delete(url, headers=h).status_code == 204
    assert env.client.get(url).status_code == 404


def test_software_inventory_replace_and_validation(admin_session: Env):
    env = admin_session
    h = env.csrf()
    a = env.client.post("/api/v1/assets", json=asset_body(code="SRV-T1", asset_type="server"), headers=h).json()
    url = f"/api/v1/assets/{a['id']}/software"
    ok = env.client.put(url, json={"items": [
        {"name": "Voltek SCADA Server", "vendor": "Voltek", "version": "4.2.1", "cpe": "cpe:2.3:a:voltek:x:4.2.1"},
        {"name": "Windows Server 2019", "vendor": "Microsoft", "version": "10.0.17763"}]}, headers=h)
    assert ok.status_code == 200 and [s["name"] for s in ok.json()["software"]] == \
        ["Voltek SCADA Server", "Windows Server 2019"]
    dup = env.client.put(url, json={"items": [{"name": "A", "version": "1"}, {"name": "a", "version": "1"}]}, headers=h)
    assert dup.status_code == 422
    replaced = env.client.put(url, json={"items": [{"name": "Only", "version": "2"}]}, headers=h).json()
    assert [s["name"] for s in replaced["software"]] == ["Only"]


def test_relations_topology_and_rules(admin_session: Env):
    env = admin_session
    h = env.csrf()
    a = env.client.post("/api/v1/assets", json=asset_body(code="SRV-T1", asset_type="server"), headers=h).json()
    b = env.client.post("/api/v1/assets", json=asset_body(code="PLC-T1"), headers=h).json()
    url = f"/api/v1/assets/{a['id']}/relations"
    ok = env.client.post(url, json={"target": "PLC-T1", "relation": "control", "protocol": "Modbus/TCP"}, headers=h)
    assert ok.status_code == 201 and ok.json()["outgoing"][0]["target"] == "PLC-T1"
    assert env.client.post(url, json={"target": "PLC-T1", "relation": "control"}, headers=h).status_code == 409
    assert env.client.post(url, json={"target": "SRV-T1", "relation": "control"}, headers=h).status_code == 422
    assert env.client.post(url, json={"target": "NOPE", "relation": "control"}, headers=h).status_code == 422
    assert env.client.post(url, json={"target": "PLC-T1", "relation": "magic"}, headers=h).status_code == 422
    detail = env.client.get(f"/api/v1/assets/{b['id']}").json()
    assert detail["relations"]["incoming"][0]["source"] == "SRV-T1"
    topo = env.client.get("/api/v1/assets/topology").json()
    assert {n["code"] for n in topo["nodes"]} == {"SRV-T1", "PLC-T1"} and len(topo["edges"]) == 1
    rid = ok.json()["outgoing"][0]["id"]
    assert env.client.delete(f"{url}/{rid}", headers=h).json()["outgoing"] == []
    # deleting an asset removes its relations
    assert env.client.post(url, json={"target": "PLC-T1", "relation": "control"}, headers=h).status_code == 201
    env.client.put(f"/api/v1/assets/{b['id']}", json={"status": "decommissioned"}, headers=h)
    assert env.client.delete(f"/api/v1/assets/{b['id']}", headers=h).status_code == 204
    assert env.client.get(f"/api/v1/assets/{a['id']}").json()["relations"]["outgoing"] == []


def test_filters_search_paging(admin_session: Env):
    env = admin_session
    make_zone(env)
    h = env.csrf()
    for i in range(5):
        env.client.post("/api/v1/assets", json=asset_body(code=f"PLC-F{i}", zone="ZT" if i < 3 else None), headers=h)
    env.client.post("/api/v1/assets", json=asset_body(code="SW-F1", asset_type="switch", purdue_level="2"), headers=h)
    q = lambda **p: env.client.get("/api/v1/assets", params=p).json()  # noqa: E731
    assert q()["total"] == 6
    assert q(asset_type="switch")["total"] == 1 and q(category="device")["total"] == 5
    assert q(zone="ZT")["total"] == 3 and q(search="f1")["total"] == 2
    assert q(page=2, page_size=4)["items"][0]["code"] == "SW-F1" or len(q(page=2, page_size=4)["items"]) == 2


def test_capabilities_for_assets(env: Env):
    env.make_user("eng", "OT Asset Engineer")
    env.make_user("op", "SOC Operator")
    env.make_user("aud", "Auditor")
    eng, he = client_for(env, "eng")
    assert eng.post("/api/v1/assets", json=asset_body(), headers=he).status_code == 201
    op, ho = client_for(env, "op")
    assert op.get("/api/v1/assets").status_code == 200
    assert op.post("/api/v1/assets", json=asset_body(code="PLC-OP"), headers=ho).status_code == 403
    assert op.put("/api/v1/assets/1", json={"name": "x"}, headers=ho).status_code == 403
    assert op.delete("/api/v1/assets/1", headers=ho).status_code == 403
    assert op.post("/api/v1/assets/1/credentials", json={"scopes": ["ingest:rf"], "allowed_networks": ["10.0.0.0/8"]},
                   headers=ho).status_code == 403
    aud, _ = client_for(env, "aud")
    assert aud.get("/api/v1/assets/topology").status_code == 200


def test_vocabulary_and_zones_endpoints(admin_session: Env):
    env = admin_session
    make_zone(env)
    vocab = env.client.get("/api/v1/assets/vocabulary").json()
    assert vocab["types"]["plc"] == "device" and "3.5" in vocab["levels"] and "ingest:rf" in vocab["scopes"]
    assert [z["code"] for z in env.client.get("/api/v1/zones").json()] == ["ZT"]
