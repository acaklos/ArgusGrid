"""Vulnerability intelligence: versions, feed parsers, matching, classification, signed bundles (no database)."""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.intel import bundle
from app.intel import matcher as m
from app.intel import parsers as p
from app.intel.versions import compare, in_range

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)


# -- versions -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("a,b,expected", [
    ("4.2.1", "4.2.1", 0), ("4.2.9", "4.2.10", -1), ("4.10", "4.9", 1), ("4.2", "4.2.0", 0),
    ("v2.0", "2.0", 0), ("16.13", "16.14", -1), ("1.0a", "1.0", 1), ("2.4.0", "2.5.0", -1),
])
def test_compare(a, b, expected):
    assert compare(a, b) == expected


@pytest.mark.parametrize("version,spec,expected", [
    ("4.2.1", {"lt": "4.3.0"}, True), ("4.3.0", {"lt": "4.3.0"}, False), ("4.3.0", {"lte": "4.3.0"}, True),
    ("16.5", {"gte": "16.0", "lt": "16.14"}, True), ("15.9", {"gte": "16.0", "lt": "16.14"}, False),
    ("3.8.0", {"eq": ["3.8.0", "3.7.0"]}, True), ("3.9.0", {"eq": ["3.8.0"]}, False),
    ("1.0", {}, True), ("", {"lt": "2"}, False), ("2.0", {"gt": "2.0"}, False),
])
def test_in_range(version, spec, expected):
    assert in_range(version, spec) is expected


# -- parsers ------------------------------------------------------------------------------------------
KEV = {"title": "x", "vulnerabilities": [
    {"cveID": "CVE-2026-1111", "vendorProject": "Acme", "product": "Gateway", "vulnerabilityName": "Acme gateway RCE",
     "dateAdded": "2026-10-11", "shortDescription": "RCE", "requiredAction": "Apply updates per vendor instructions."},
    {"cveID": "CVE-2026-2222", "vendorProject": "Old", "product": "Box", "vulnerabilityName": "Old box",
     "dateAdded": "2026-09-01", "shortDescription": "x",
     "requiredAction": "The product is unsupported: discontinue use."},
    {"cveID": "CVE-2026-3000", "vendorProject": "Gen", "product": "Eric", "vulnerabilityName": "g",
     "dateAdded": "2026-10-01", "shortDescription": "x",
     "requiredAction": "Apply mitigations per vendor instructions or discontinue use of the product "
                       "if mitigations are unavailable."},
    {"cveID": "not a cve", "vendorProject": "X"},
]}


def test_kev_parser():
    recs = p.parse_kev(KEV)
    assert [r["vuln_id"] for r in recs] == ["CVE-2026-1111", "CVE-2026-2222", "CVE-2026-3000"]
    assert recs[0]["kev"] is True and recs[0]["fix_status"] == "available"
    assert recs[1]["fix_status"] == "none"
    # the generic "discontinue use if mitigations are unavailable" sentence must not mean "no fix exists"
    assert recs[2]["fix_status"] == "workaround"
    assert recs[0]["published_at"].startswith("2026-10-11T00:00:00")
    assert recs[0]["affected"][0] == {"vendor": "Acme", "product": "Gateway", "cpe": "", "versions": {}}
    assert len(p.parse_kev(json.dumps(KEV))) == 3
    assert len(p.parse_kev(gzip.compress(json.dumps(KEV).encode()))) == 3
    with pytest.raises(p.FeedError):
        p.parse_kev({"nothing": []})
    with pytest.raises(p.FeedError):
        p.parse_kev("not json")


NVD = {"vulnerabilities": [
    {"cve": {"id": "CVE-2026-3333", "published": "2026-10-10T10:00:00.000", "vulnStatus": "Analyzed",
             "descriptions": [{"lang": "en", "value": "Buffer overflow in Acme Gateway before 2.5."}],
             "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.1}}]},
             "references": [{"url": "https://example.invalid/a"}],
             "configurations": [{"nodes": [{"operator": "OR", "cpeMatch": [
                 {"vulnerable": True, "criteria": "cpe:2.3:a:acme:gateway:*:*:*:*:*:*:*:*",
                  "versionStartIncluding": "2.0", "versionEndExcluding": "2.5"},
                 {"vulnerable": True, "criteria": "cpe:2.3:a:acme:gateway:3.1:*:*:*:*:*:*:*"},
                 {"vulnerable": False, "criteria": "cpe:2.3:o:other:os:1:*:*:*:*:*:*:*"}]}]}]}},
    {"cve": {"id": "CVE-2026-4444", "vulnStatus": "Rejected", "descriptions": []}},
]}


def test_nvd_parser_reads_ranges_score_and_skips_rejected():
    recs = p.parse_nvd(NVD)
    assert len(recs) == 1
    r = recs[0]
    assert r["vuln_id"] == "CVE-2026-3333" and r["cvss"] == 9.1 and r["severity"] == "critical"
    assert r["affected"][0]["versions"] == {"gte": "2.0", "lt": "2.5"}
    assert r["affected"][1]["versions"] == {"eq": ["3.1"]}
    assert len(r["affected"]) == 2  # the non-vulnerable configuration is ignored
    assert r["references"] == ["https://example.invalid/a"]


def test_epss_parser_json_csv_and_gzip():
    api = {"data": [{"cve": "CVE-2026-1111", "epss": "0.91", "percentile": "0.99"}, {"cve": "bad", "epss": "1"}]}
    assert p.parse_epss(api) == [{"vuln_id": "CVE-2026-1111", "epss": 0.91}]
    csv_text = "#model_version:v2025.01.14,score_date:2026-10-12\ncve,epss,percentile\nCVE-2026-3333,0.42,0.9\n"
    assert p.parse_epss(csv_text) == [{"vuln_id": "CVE-2026-3333", "epss": 0.42}]
    assert p.parse_epss(gzip.compress(csv_text.encode()))[0]["vuln_id"] == "CVE-2026-3333"


CSAF = {
    "document": {"tracking": {"id": "ACME-SA-2026-01", "initial_release_date": "2026-10-11T08:00:00Z"}},
    "product_tree": {"branches": [{"category": "vendor", "name": "Acme", "branches": [
        {"category": "product_name", "name": "Gateway", "branches": [
            {"category": "product_version", "name": "2.4.0", "product": {
                "product_id": "CSAFPID-1", "name": "Acme Gateway 2.4.0",
                "product_identification_helper": {"cpe": "cpe:2.3:a:acme:gateway:2.4.0:*:*:*:*:*:*:*"}}},
            {"category": "product_version", "name": "2.5.0", "product": {
                "product_id": "CSAFPID-2", "name": "Acme Gateway 2.5.0"}}]}]}]},
    "vulnerabilities": [{
        "cve": "CVE-2026-5555", "title": "Gateway auth bypass", "notes": [{"category": "description", "text": "Bypass."}],
        "product_status": {"known_affected": ["CSAFPID-1"], "fixed": ["CSAFPID-2"]},
        "scores": [{"cvss_v3": {"baseScore": 8.2}}], "references": [{"url": "https://example.invalid/csaf"}]}],
}


def test_csaf_parser():
    recs = p.parse_csaf(CSAF)
    assert len(recs) == 1
    r = recs[0]
    assert r["vuln_id"] == "CVE-2026-5555" and r["fix_status"] == "available" and r["severity"] == "high"
    assert r["affected"][0]["product"] == "gateway" and r["affected"][0]["versions"] == {"eq": ["2.4.0"]}
    assert r["published_at"].startswith("2026-10-11T08:00:00")
    with pytest.raises(p.FeedError):
        p.parse_csaf({"document": {}})


# -- matching -----------------------------------------------------------------------------------------
def test_matching_by_cpe_product_firmware_and_version():
    spec = [{"vendor": "Voltek", "product": "SCADA Web Console", "cpe": "", "versions": {"lt": "4.3.0"}}]
    sw = m.SoftwareRef(name="Voltek SCADA Web Console", vendor="Voltek", version="4.2.1")
    assert m.match_software(spec, sw).basis == "product"
    assert m.match_software(spec, m.SoftwareRef("Voltek SCADA Web Console", "Voltek", "4.3.0")) is None
    assert m.match_software(spec, m.SoftwareRef("Voltek SCADA Web Console", "Voltek", "")) is None  # unknown version
    assert m.match_software(spec, m.SoftwareRef("Other Console", "Other", "4.2.1")) is None

    cpe_spec = [{"vendor": "postgresql", "product": "postgresql", "cpe": "cpe:2.3:a:postgresql:postgresql:*:*:*:*:*:*:*:*",
                 "versions": {"gte": "16.0", "lt": "16.14"}}]
    pg = m.SoftwareRef("PostgreSQL", "PostgreSQL Global Development Group", "16.13",
                       "cpe:2.3:a:postgresql:postgresql:16.13:*:*:*:*:*:*:*")
    assert m.match_software(cpe_spec, pg).basis == "cpe"
    fw = m.SoftwareRef("TC-900", "Voltek", "2.4.0", basis="firmware")
    assert m.match_software([{"vendor": "Voltek", "product": "TC-900", "versions": {"lt": "2.5.0"}}], fw).basis == "firmware"
    assert m.norm("Voltek_SCADA-Server") == "voltek scada server"


def test_a_product_substring_does_not_match_a_different_product():
    spec = [{"vendor": "", "product": "tc", "versions": {}}]
    assert m.match_software(spec, m.SoftwareRef("TC-900 Studio", "Voltek", "1.0")) is None


# -- classification -----------------------------------------------------------------------------------
def test_zero_day_zero_hour_and_decay():
    base = dict(kev=True, epss=None, fix_status="none", published_at=NOW - timedelta(hours=2),
                first_seen_at=NOW - timedelta(hours=1), zero_hour_hours=72, epss_threshold=0.5)
    assert m.classify(now=NOW, **base) == (True, True)
    assert m.classify(now=NOW + timedelta(days=4), **base) == (True, False)  # zero-hour window passed
    fixed = {**base, "fix_status": "available"}
    assert m.classify(now=NOW, **fixed) == (False, True)
    assert m.classify(now=NOW + timedelta(days=4), **fixed) == (False, False)
    not_exploited = {**base, "kev": False, "epss": 0.1}
    assert m.classify(now=NOW, **not_exploited) == (False, False)
    by_epss = {**base, "kev": False, "epss": 0.7, "fix_status": "available"}
    assert m.classify(now=NOW, **by_epss) == (False, True)
    assert m.label(True, True) == "zero_day" and m.label(False, True) == "zero_hour" and m.label(False, False) == "ordinary"


def test_first_seen_is_used_when_no_publication_date_exists():
    r = m.classify(kev=True, epss=None, fix_status="available", published_at=None,
                   first_seen_at=NOW - timedelta(hours=10), now=NOW, zero_hour_hours=72, epss_threshold=0.5)
    assert r == (False, True)


# -- signed bundles -----------------------------------------------------------------------------------
def test_bundle_roundtrip_and_rejections():
    private, public = bundle.generate_keypair()
    records = [{"vuln_id": "DEMO-2026-0100", "severity": "high"}]
    doc = bundle.sign_bundle(records, private, "k1", NOW.isoformat())
    assert bundle.verify_bundle(doc, {"k1": public}) == records

    tampered = json.loads(json.dumps(doc))
    tampered["records"][0]["severity"] = "low"
    with pytest.raises(bundle.BundleError) as e1:
        bundle.verify_bundle(tampered, {"k1": public})
    assert e1.value.code == "bundle.signature_invalid"
    with pytest.raises(bundle.BundleError) as e2:
        bundle.verify_bundle(doc, {"other": public})
    assert e2.value.code == "bundle.unknown_key"
    _other_private, other_public = bundle.generate_keypair()
    with pytest.raises(bundle.BundleError) as e3:
        bundle.verify_bundle(doc, {"k1": other_public})
    assert e3.value.code == "bundle.signature_invalid"
    with pytest.raises(bundle.BundleError) as e4:
        bundle.verify_bundle({"format": "something"}, {"k1": public})
    assert e4.value.code == "bundle.format"
    unsigned = {k: v for k, v in doc.items() if k != "signature"}
    with pytest.raises(bundle.BundleError):
        bundle.verify_bundle(unsigned, {"k1": public})
