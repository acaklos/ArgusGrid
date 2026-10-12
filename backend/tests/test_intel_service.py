"""Vulnerability intelligence through the service and the API (ARG-016)."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.demo.intel_demo import demo_records
from app.intel import bundle
from app.models.intel import Finding, IntelSource
from app.models.mail import MailOutbox
from app.services.demo_service import DemoService
from app.services.intel_service import FetchError
from tests.conftest import Env

GOOD = "Aa1!bcdefghijkl"


@pytest.fixture()
def site(admin_session: Env):  # type: ignore[no-untyped-def]
    env = admin_session
    env.make_user("mgr", "SOC Manager")  # holds intel.ack and has an address for alerts
    with env.services() as svc:
        from app.models.identity import User

        mgr = svc.session.execute(select(User).where(User.username_key == "mgr")).scalar_one()
        mgr.email = "mgr@example.test"
        DemoService(svc.session, env.clock, svc.box, svc.audit, svc.intel).create()
    return env


def findings_by_vuln(env: Env) -> dict[str, list[str]]:
    data = env.client.get("/api/v1/intel/findings", params={"page_size": 200}).json()
    out: dict[str, list[str]] = {}
    for f in data["items"]:
        out.setdefault(f["vulnerability"]["vuln_id"], []).append(f["asset"]["code"])
    return {k: sorted(v) for k, v in out.items()}


def classification(env: Env, vuln_id: str) -> str:
    return env.client.get(f"/api/v1/intel/vulnerabilities/{vuln_id}").json()["classification"]


def test_demo_intelligence_is_matched_to_the_inventory(site: Env):
    got = findings_by_vuln(site)
    assert got["DEMO-2026-0001"] == ["SCADA-SRV-01", "SCADA-SRV-02"]
    assert got["DEMO-2026-0002"] == ["HIST-01", "HIST-DMZ"]
    assert got["DEMO-2026-0003"] == ["ARGUS-DB"]
    assert got["DEMO-2026-0004"] == ["PLC-GT1", "PLC-GT2"]  # matched on firmware
    assert "DEMO-2026-0005" not in got  # not in the inventory
    assert len(got["DEMO-2026-0006"]) >= 8  # Windows Server 2019 on many assets
    firmware = [f for f in site.client.get("/api/v1/intel/findings", params={"page_size": 200}).json()["items"]
                if f["vulnerability"]["vuln_id"] == "DEMO-2026-0004"]
    assert {f["match_basis"] for f in firmware} == {"firmware"}


def test_classification_of_the_demo_records(site: Env):
    assert classification(site, "DEMO-2026-0001") == "zero_day"  # no fix, exploited (also within 72 h)
    assert classification(site, "DEMO-2026-0002") == "zero_day"  # no fix, EPSS 0.82
    assert classification(site, "DEMO-2026-0003") == "ordinary"
    assert classification(site, "DEMO-2026-0006") == "ordinary"  # exploited but fixed and older than 72 h
    detail = site.client.get("/api/v1/intel/vulnerabilities/DEMO-2026-0001").json()
    assert detail["is_zero_day"] and detail["is_zero_hour"]
    assert len(detail["findings"]) == 2 and detail["affected"][0]["versions"] == {"lt": "4.3.0"}


def test_zero_hour_decays_but_zero_day_stays(site: Env):
    site.clock.advance(days=4)
    assert site.login(site.admin_username, site.admin_password).status_code == 200  # the session timed out too
    d = site.client.get("/api/v1/intel/vulnerabilities/DEMO-2026-0001").json()
    assert d["is_zero_day"] is True and d["is_zero_hour"] is False and d["classification"] == "zero_day"


def test_policy_changes_the_classification_and_is_validated(site: Env):
    h = site.csrf()
    policy = site.client.get("/api/v1/intel/policy").json()
    assert policy == {"zero_hour_hours": 72, "epss_threshold": 0.5, "notify_min_severity": "high",
                      "notify": True, "offline_only": False}
    policy["epss_threshold"] = 0.9  # 0.82 no longer counts as exploited
    assert site.client.put("/api/v1/intel/policy", json=policy, headers=h).status_code == 200
    assert classification(site, "DEMO-2026-0002") == "ordinary"
    bad = site.client.put("/api/v1/intel/policy", json={**policy, "zero_hour_hours": 0, "epss_threshold": 2,
                                                       "notify_min_severity": "extreme"}, headers=h)
    assert bad.status_code == 422
    assert {p["code"] for p in bad.json()["details"]} == {"intel.zero_hour_range", "intel.epss_range",
                                                          "intel.severity_invalid"}
    assert "intel.policy.update" in site.audit_actions()


def test_alerts_go_once_to_users_who_can_acknowledge(site: Env):
    with site.services() as svc:
        rows = list(svc.session.execute(
            select(MailOutbox).where(MailOutbox.template_key == "alert.critical")).scalars())
    recipients = {r.to_address for r in rows}
    assert recipients == {"mgr@example.test"}  # the administrator has no address; operators lack intel.ack
    subjects = " ".join(r.subject for r in rows)
    assert "DEMO-2026-0001" in subjects and "DEMO-2026-0002" in subjects  # zero-day, high or critical
    assert "DEMO-2026-0006" not in subjects and "DEMO-2026-0003" not in subjects
    count = len(rows)
    # importing the same data again neither duplicates findings nor alerts
    report = site.client.post("/api/v1/intel/import", headers=site.csrf(),
                              json={"format": "records", "payload": demo_records(site.clock.now())}).json()
    assert report["created"] == 0 and report["new_findings"] == 0 and report["notified"] == 0
    with site.services() as svc:
        again = svc.session.execute(select(MailOutbox).where(MailOutbox.template_key == "alert.critical")).scalars().all()
    assert len(again) == count


def test_merge_never_erases_known_exploitation_or_fix_state(site: Env):
    h = site.csrf()
    kev = {"vulnerabilities": [{"cveID": "CVE-2026-6001", "vendorProject": "Voltek", "product": "Historian",
                                "vulnerabilityName": "Historian flaw", "dateAdded": "2026-10-12",
                                "shortDescription": "y", "requiredAction": "Apply updates per vendor instructions."}]}
    site.client.post("/api/v1/intel/import", headers=h, json={"format": "kev", "payload": kev})
    d = site.client.get("/api/v1/intel/vulnerabilities/CVE-2026-6001").json()
    assert d["kev"] is True and d["fix_status"] == "available"
    # EPSS adds a score; it must not clear the exploitation flag or the fix state
    site.client.post("/api/v1/intel/import", headers=h, json={"format": "epss", "payload": {
        "data": [{"cve": "CVE-2026-6001", "epss": 0.3}]}})
    d = site.client.get("/api/v1/intel/vulnerabilities/CVE-2026-6001").json()
    assert d["epss"] == 0.3 and d["kev"] is True and d["fix_status"] == "available"
    # a later feed that says "unknown" does not overwrite a known fix state
    again = {"vulnerabilities": [{"cveID": "CVE-2026-6001", "vendorProject": "Voltek", "product": "Historian",
                                  "vulnerabilityName": "Historian flaw", "dateAdded": "2026-10-12",
                                  "shortDescription": "y", "requiredAction": "See vendor."}]}
    site.client.post("/api/v1/intel/import", headers=h, json={"format": "kev", "payload": again})
    assert site.client.get("/api/v1/intel/vulnerabilities/CVE-2026-6001").json()["fix_status"] == "available"
    # EPSS for an identifier the feed does not own (a non-CVE) is ignored, not stored
    ignored = site.client.post("/api/v1/intel/import", headers=h, json={"format": "epss", "payload": {
        "data": [{"cve": "DEMO-2026-0001", "epss": 0.1}]}})
    assert ignored.status_code == 200 and ignored.json()["created"] == 0


def test_acknowledging_a_finding_is_audited_and_needs_the_capability(site: Env):
    h = site.csrf()
    item = site.client.get("/api/v1/intel/findings", params={"classification": "zero_day"}).json()["items"][0]
    r = site.client.put(f"/api/v1/intel/findings/{item['id']}", headers=h,
                        json={"status": "acknowledged", "note": "isolating the console"})
    assert r.status_code == 200 and r.json()["status"] == "acknowledged" and r.json()["acknowledged_by"] == "sysadmin"
    assert site.client.put(f"/api/v1/intel/findings/{item['id']}", headers=h,
                           json={"status": "nonsense"}).status_code == 422
    assert "intel.finding.update" in site.audit_actions()
    open_ones = site.client.get("/api/v1/intel/findings", params={"status": "open"}).json()["total"]
    assert open_ones == site.client.get("/api/v1/intel/findings").json()["total"] - 1

    site.make_user("op", "SOC Operator")  # view only
    c = site.new_client()
    site.login("op", GOOD, c)
    oh = site.csrf(c)
    assert c.get("/api/v1/intel/findings").status_code == 200
    assert c.put(f"/api/v1/intel/findings/{item['id']}", headers=oh, json={"status": "open"}).status_code == 403
    assert c.post("/api/v1/intel/import", headers=oh, json={"format": "records", "payload": []}).status_code == 403
    assert c.put("/api/v1/intel/policy", headers=oh, json={
        "zero_hour_hours": 72, "epss_threshold": 0.5, "notify_min_severity": "high", "notify": True,
        "offline_only": False}).status_code == 403
    assert c.get("/api/v1/intel/trusted-keys").status_code == 403


def test_changing_the_software_inventory_triggers_matching(site: Env):
    h = site.csrf()
    asset = site.client.get("/api/v1/assets", params={"search": "FILE-01"}).json()["items"][0]
    before = findings_by_vuln(site).get("DEMO-2026-0005", [])
    assert before == []
    r = site.client.put(f"/api/v1/assets/{asset['id']}/software", headers=h, json={"items": [
        {"name": "Orion PrintServer", "vendor": "Orion", "version": "9.0"}]})
    assert r.status_code == 200
    assert findings_by_vuln(site)["DEMO-2026-0005"] == ["FILE-01"]


def test_feed_documents_can_be_imported_and_garbage_is_rejected(site: Env):
    h = site.csrf()
    nvd = {"vulnerabilities": [{"cve": {"id": "CVE-2026-7777", "published": "2026-10-12T07:00:00.000",
                                        "descriptions": [{"lang": "en", "value": "Overflow in Voltek Historian"}],
                                        "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 7.4}}]},
                                        "configurations": [{"nodes": [{"cpeMatch": [{
                                            "vulnerable": True, "criteria": "cpe:2.3:a:voltek:historian:*:*:*:*:*:*:*:*",
                                            "versionEndExcluding": "3.9.5"}]}]}]}}]}
    r = site.client.post("/api/v1/intel/import", headers=h, json={"format": "nvd", "payload": nvd})
    assert r.status_code == 200 and r.json()["created"] == 1 and r.json()["new_findings"] == 2
    assert findings_by_vuln(site)["CVE-2026-7777"] == ["HIST-01", "HIST-DMZ"]
    assert site.client.post("/api/v1/intel/import", headers=h,
                            json={"format": "nvd", "payload": "not json"}).status_code == 422
    assert site.client.post("/api/v1/intel/import", headers=h,
                            json={"format": "xml", "payload": {}}).status_code == 422


def test_signed_bundle_needs_a_trusted_key(site: Env):
    h = site.csrf()
    private, public = bundle.generate_keypair()
    doc = bundle.sign_bundle([{"vuln_id": "DEMO-2026-0101", "title": "Bundle item", "severity": "low",
                               "affected": [], "kev": False}], private, "ops-2026", site.clock.now().isoformat())
    rejected = site.client.post("/api/v1/intel/import", headers=h, json={"format": "bundle", "payload": doc})
    assert rejected.status_code == 422 and rejected.json()["details"][0]["code"] == "bundle.unknown_key"
    saved = site.client.put("/api/v1/intel/trusted-keys", headers=h,
                            json={"keys": [{"key_id": "ops-2026", "public_key": public, "label": "Operations"}]})
    assert saved.status_code == 200
    ok = site.client.post("/api/v1/intel/import", headers=h, json={"format": "bundle", "payload": doc})
    assert ok.status_code == 200 and ok.json()["created"] == 1
    doc["records"][0]["severity"] = "critical"
    tampered = site.client.post("/api/v1/intel/import", headers=h, json={"format": "bundle", "payload": doc})
    assert tampered.status_code == 422 and tampered.json()["details"][0]["code"] == "bundle.signature_invalid"
    bad_key = site.client.put("/api/v1/intel/trusted-keys", headers=h,
                              json={"keys": [{"key_id": "x", "public_key": "AAAA"}]})
    assert bad_key.status_code == 422


class FakeFetcher:
    def __init__(self, content: bytes | Exception) -> None:
        self.content = content
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, url: str, params: dict[str, str] | None = None) -> bytes:
        self.calls.append((url, params))
        if isinstance(self.content, Exception):
            raise self.content
        return self.content


def test_source_run_reports_success_and_failure_without_raising(site: Env):
    h = site.csrf()
    kev = {"vulnerabilities": [{"cveID": "CVE-2026-8888", "vendorProject": "Voltek", "product": "Historian",
                                "vulnerabilityName": "Historian flaw", "dateAdded": "2026-10-12",
                                "shortDescription": "d", "requiredAction": "Apply updates per vendor instructions."}]}
    fetcher = FakeFetcher(json.dumps(kev).encode())
    site.client.app.state.fetcher = fetcher
    sources = {s["key"]: s for s in site.client.get("/api/v1/intel/sources").json()}
    assert {"kev", "epss", "nvd", "csaf", "bundle"} <= set(sources) and sources["kev"]["enabled"] is False
    assert site.client.put("/api/v1/intel/sources/kev", headers=h, json={"enabled": True}).status_code == 200
    ran = site.client.post("/api/v1/intel/sources/kev/run", headers=h).json()
    assert ran["last_status"] == "ok" and ran["report"]["created"] == 1 and fetcher.calls[0][0].startswith("https://")
    assert findings_by_vuln(site)["CVE-2026-8888"] == ["HIST-01", "HIST-DMZ"]

    site.client.app.state.fetcher = FakeFetcher(FetchError("HTTP 503"))
    failed = site.client.post("/api/v1/intel/sources/kev/run", headers=h).json()
    assert failed["last_status"] == "error" and "503" in failed["last_error"] and failed["report"] is None
    assert site.client.post("/api/v1/intel/sources/bundle/run", headers=h).status_code == 409  # not fetchable


def test_offline_only_profile_never_contacts_sources_and_urls_are_checked(site: Env):
    h = site.csrf()
    bad = site.client.put("/api/v1/intel/sources/csaf", headers=h, json={"url": "http://feeds.example.org/a.json"})
    assert bad.status_code == 422 and bad.json()["details"][0]["code"] == "intel.url_invalid"
    userinfo = site.client.put("/api/v1/intel/sources/csaf", headers=h, json={"url": "https://u:p@example.org/a"})
    assert userinfo.status_code == 422
    assert site.client.put("/api/v1/intel/sources/csaf", headers=h,
                           json={"url": "https://feeds.example.org/a.json"}).status_code == 200
    policy = site.client.get("/api/v1/intel/policy").json()
    policy["offline_only"] = True
    site.client.put("/api/v1/intel/policy", json=policy, headers=h)
    fetcher = FakeFetcher(b"{}")
    site.client.app.state.fetcher = fetcher
    refused = site.client.post("/api/v1/intel/sources/kev/run", headers=h)
    assert refused.status_code == 409 and refused.json()["code"] == "intel.offline_only" and fetcher.calls == []
    enable = site.client.put("/api/v1/intel/sources/kev", headers=h, json={"enabled": True})
    assert enable.status_code == 422 and enable.json()["details"][0]["code"] == "intel.offline_only"


def test_worker_runs_due_sources_only_when_enabled_and_due(site: Env):
    from app.workers import run_once

    h = site.csrf()
    fetcher = FakeFetcher(json.dumps({"vulnerabilities": []}).encode())
    assert run_once(site.db, site.clock, site.config, site.transport, fetcher)["intel_sources_run"] == 0
    site.client.put("/api/v1/intel/sources/kev", headers=h, json={"enabled": True})
    assert run_once(site.db, site.clock, site.config, site.transport, fetcher)["intel_sources_run"] == 1
    assert run_once(site.db, site.clock, site.config, site.transport, fetcher)["intel_sources_run"] == 0  # not due
    site.clock.advance(hours=7)
    assert run_once(site.db, site.clock, site.config, site.transport, fetcher)["intel_sources_run"] == 1
    with site.services() as svc:
        s = svc.session.execute(select(IntelSource).where(IntelSource.key == "kev")).scalar_one()
        assert s.last_status == "ok"


def test_overview_and_deleting_demo_data_removes_intelligence(site: Env):
    ov = site.client.get("/api/v1/intel/overview").json()
    assert ov["open_findings"]["zero_day"] >= 4 and ov["vulnerabilities"] == 6
    with site.services() as svc:
        DemoService(svc.session, site.clock, svc.box, svc.audit, svc.intel).delete()
        assert svc.session.execute(select(Finding)).first() is None
    assert site.client.get("/api/v1/intel/vulnerabilities").json()["total"] == 0
