"""Smoke test of the real public feeds with the production fetcher and parsers (needs internet access).

Nothing is stored. It reports what was fetched and parsed, or why it could not be. Development tool.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.intel.parsers import PARSERS  # noqa: E402
from app.services.intel_service import DEFAULT_SOURCES, FetchError, HttpFetcher  # noqa: E402


def main() -> int:
    fetcher = HttpFetcher(timeout=60)
    failures = 0
    for key, name, kind, url, _hours in DEFAULT_SOURCES:
        if not url or kind not in PARSERS:
            continue
        params = None
        if kind == "nvd":
            now = datetime.now(timezone.utc)
            params = {"lastModStartDate": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000"),
                      "lastModEndDate": now.strftime("%Y-%m-%dT%H:%M:%S.000")}
        try:
            data = fetcher.get(url, params)
            records = PARSERS[kind](data)
            sample = records[0]["vuln_id"] if records else "-"
            print(f"OK    {key:5} {len(data):>10,} bytes  {len(records):>6,} records  first: {sample}")
        except FetchError as exc:
            failures += 1
            print(f"FETCH {key:5} {exc}")
        except Exception as exc:  # parsing problem on real data is exactly what this script looks for
            failures += 1
            print(f"PARSE {key:5} {type(exc).__name__}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
