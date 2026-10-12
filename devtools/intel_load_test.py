"""Import the live CISA KEV feed into the TEST database (with the demo site) and time matching.

Development tool: it drops and recreates the test database content. Needs internet access.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

dev = (ROOT / "backend" / "data" / "database.url").read_text(encoding="utf-8").strip()
os.environ["ARGUS_DATABASE_URL"] = re.sub(r"/argusgrid$", "/argusgrid_test", dev)
os.environ.setdefault("ARGUS_DATA_DIR", str(ROOT / ".devtools" / "intel_load"))
os.environ.setdefault("ARGUS_CONFIG_DIR", str(ROOT / ".devtools" / "intel_load"))

from sqlalchemy import func, select, text  # noqa: E402

from app.core.clock import Clock  # noqa: E402
from app.core.config import load_config  # noqa: E402
from app.core.db import Database  # noqa: E402
from app.intel.parsers import parse_kev  # noqa: E402
from app.models.intel import Finding, Vulnerability  # noqa: E402
from app.services.container import Services  # noqa: E402
from app.services.demo_service import DemoService  # noqa: E402
from app.services.intel_service import HttpFetcher  # noqa: E402
from app.tools.prepare_database import prepare  # noqa: E402


def main() -> int:
    config = load_config()
    db = Database(config.database_url)
    with db.transaction() as s:
        names = s.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                               "AND tablename <> 'alembic_version'")).scalars().all()
        s.execute(text("TRUNCATE " + ", ".join(f'"{n}"' for n in names) + " RESTART IDENTITY CASCADE"))
    prepare(config)
    with db.transaction() as s:
        svc = Services(s, Clock(), config)
        DemoService(s, svc.clock, svc.box, svc.audit, svc.intel).create()

    t0 = time.perf_counter()
    data = HttpFetcher(timeout=60).get(
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
    fetched = time.perf_counter() - t0
    records = parse_kev(data)
    with db.transaction() as s:
        svc = Services(s, Clock(), config)
        t1 = time.perf_counter()
        report = svc.intel.import_payload(None, "records", records, source_key="kev")
        elapsed = time.perf_counter() - t1
        vulns = s.execute(select(func.count()).select_from(Vulnerability)).scalar_one()
        findings = s.execute(select(func.count()).select_from(Finding)).scalar_one()
        by_basis = dict(s.execute(select(Finding.match_basis, func.count()).group_by(Finding.match_basis)).all())
    print(f"fetched {len(data):,} bytes in {fetched:.1f}s, parsed {len(records):,} records")
    print(f"import + match: {elapsed:.1f}s; created {report.created:,}; new findings {report.new_findings:,}; "
          f"notified {report.notified}")
    print(f"vulnerabilities in database: {vulns:,}; findings: {findings:,}; by basis: {by_basis}")
    db.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
