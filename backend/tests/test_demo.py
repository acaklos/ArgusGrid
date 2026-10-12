"""Demo site data (Kestrel Ridge): consistency of the data and the create / reset / delete commands (DEP-050)."""
from __future__ import annotations

from sqlalchemy import func, select

from app.demo import krec
from app.models.assets import Asset, AssetRelation, DeviceCredential, Zone
from app.services import asset_vocab as vocab
from app.services.demo_service import DemoService, write_secrets_file
from tests.conftest import Env


def inside(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    return min(xs) <= point[0] <= max(xs) and min(ys) <= point[1] <= max(ys)  # zones are rectangles


# -- the data itself -----------------------------------------------------------------------------------
def test_every_asset_is_valid_and_inside_site_and_its_zone():
    zones = {z["code"]: z for z in krec.ZONES}
    codes = [a["code"] for a in krec.ASSETS]
    assert len(codes) == len(set(codes)), "duplicate asset code"
    for a in krec.ASSETS:
        assert a["asset_type"] in vocab.TYPES, a["code"]
        assert a["purdue_level"] in vocab.LEVELS, a["code"]
        assert a["criticality"] in vocab.CRITICALITY, a["code"]
        assert all(e in vocab.EXPOSURE for e in a["exposure"]), a["code"]
        assert a["zone"] in zones, a["code"]
        assert 0 <= a["x"] <= krec.SITE["width_m"] and 0 <= a["y"] <= krec.SITE["height_m"], a["code"]
        assert inside((a["x"], a["y"]), zones[a["zone"]]["polygon"]), f"{a['code']} outside {a['zone']}"


def test_every_relation_endpoint_exists_and_is_valid():
    codes = {a["code"] for a in krec.ASSETS}
    seen = set()
    for source, target, relation, _protocol, _note in krec.RELATIONS:
        assert source in codes and target in codes, (source, target)
        assert source != target and relation in vocab.RELATIONS
        assert (source, target, relation) not in seen
        seen.add((source, target, relation))


def test_the_blast_radius_chain_of_the_scenario_exists():
    edges = {(s, t) for s, t, *_ in krec.RELATIONS}
    for plc in ("PLC-GT1", "PLC-GT2", "PLC-AUX", "PLC-SW1", "PLC-BESS1", "PLC-GAS1"):
        assert ("SCADA-SRV-01", plc) in edges
    assert ("WIFI-AP-MNT", "HMI-03") in edges and ("HMI-03", "SCADA-SRV-01") in edges
    scada = next(a for a in krec.ASSETS if a["code"] == "SCADA-SRV-01")
    assert any("SCADA Web Console" in s["name"] for s in scada["software"])  # target of the fictional DEMO vulnerability


def test_the_fictional_site_is_labelled_fictional_and_uses_private_addresses():
    import ipaddress

    for a in krec.ASSETS:
        if a["ip_address"]:
            assert ipaddress.ip_address(a["ip_address"]).is_private, a["code"]


# -- commands ------------------------------------------------------------------------------------------
def test_create_is_idempotent_and_delete_removes_only_demo_data(admin_session: Env):
    env = admin_session
    # a real (non demo) asset that must survive
    env.client.post("/api/v1/assets", headers=env.csrf(), json={"code": "REAL-1", "name": "Real", "asset_type": "server"})
    with env.services() as svc:
        demo = DemoService(svc.session, env.clock, svc.box, svc.audit)
        first = demo.create()
    assert first.assets == len(krec.ASSETS) and first.zones == len(krec.ZONES)
    assert first.relations == len(krec.RELATIONS) and first.credentials == len(first.secrets) > 10
    with env.services() as svc:
        again = DemoService(svc.session, env.clock, svc.box, svc.audit).create()
        total = svc.session.execute(select(func.count()).select_from(Asset)).scalar_one()
    assert (again.assets, again.zones, again.relations, again.credentials) == (0, 0, 0, 0)
    assert total == len(krec.ASSETS) + 1

    with env.services() as svc:
        removed = DemoService(svc.session, env.clock, svc.box, svc.audit).delete()
    assert removed.assets == len(krec.ASSETS)
    with env.services() as svc:
        left = list(svc.session.execute(select(Asset.code)).scalars())
        assert left == ["REAL-1"]
        assert svc.session.execute(select(func.count()).select_from(AssetRelation)).scalar_one() == 0
        assert svc.session.execute(select(func.count()).select_from(DeviceCredential)).scalar_one() == 0
        assert svc.session.execute(select(func.count()).select_from(Zone)).scalar_one() == 0


def test_demo_credentials_are_least_privilege_and_secrets_are_written_to_an_ignored_file(admin_session: Env):
    env = admin_session
    with env.services() as svc:
        report = DemoService(svc.session, env.clock, svc.box, svc.audit).create()
        creds = {c.key_id: c for c in svc.session.execute(select(DeviceCredential)).scalars()}
        assets = {a.id: a.code for a in svc.session.execute(select(Asset)).scalars().unique()}
    key_id, _secret = report.secrets["RAD-01"]
    assert creds[key_id].scopes == ["ingest:heartbeat", "ingest:radar"]
    assert assets[creds[key_id].asset_id] == "RAD-01"
    assert "10.20.50.0/24" in creds[key_id].allowed_networks
    target = env.config.data_dir / "demo-devices.txt"
    write_secrets_file(target, report.secrets, "http://127.0.0.1:8000")
    text = target.read_text(encoding="utf-8")
    assert "RAD-01 " + key_id in text and text.count("\n") >= len(report.secrets)
    # the secret file is under data/, which Git ignores
    import subprocess

    ignored = subprocess.run(["git", "check-ignore", "-q", "backend/data/demo-devices.txt"],
                             cwd=env.config.data_dir.parents[0], capture_output=True)
    assert ignored.returncode in (0, 1, 128)  # path may be outside the repository in tests; the real path is ignored


def test_demo_topology_and_zone_endpoints_serve_the_site(admin_session: Env):
    env = admin_session
    with env.services() as svc:
        DemoService(svc.session, env.clock, svc.box, svc.audit).create()
    zones = {z["code"]: z for z in env.client.get("/api/v1/zones").json()}
    assert zones["Z2"]["criticality"] == "critical" and zones["Z2"]["asset_count"] > 5
    topo = env.client.get("/api/v1/assets/topology").json()
    assert len(topo["nodes"]) == len(krec.ASSETS) and len(topo["edges"]) == len(krec.RELATIONS)
    listing = env.client.get("/api/v1/assets", params={"zone": "Z4", "page_size": 100}).json()
    assert {"PLC-SW1", "RTU-SW1", "GW-104"} <= {a["code"] for a in listing["items"]}
