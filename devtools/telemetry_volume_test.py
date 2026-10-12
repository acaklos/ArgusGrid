"""Telemetry volume test (ARG-025): fills the partitioned table with synthetic rows and times the queries the
application uses. Development tool; it works on the test database and removes its data afterwards.

Usage: python devtools/telemetry_volume_test.py [--days 7] [--rows-per-day 300000]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]


def test_url() -> str:
    dev = (ROOT / "backend" / "data" / "database.url").read_text(encoding="utf-8").strip()
    return re.sub(r"/argusgrid$", "/argusgrid_test", dev).replace("postgresql+psycopg://", "postgresql://")


def timed(conn: psycopg.Connection, sql: str, params: tuple = (), repeat: int = 5) -> tuple[float, float, int]:
    times, rows = [], 0
    for _ in range(repeat):
        t0 = time.perf_counter()
        cur = conn.execute(sql, params)
        data = cur.fetchall() if cur.description else []
        times.append((time.perf_counter() - t0) * 1000)
        rows = len(data)
    return statistics.median(times), max(times), rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--rows-per-day", type=int, default=300_000)
    args = parser.parse_args()

    conn = psycopg.connect(test_url(), autocommit=True)
    if conn.execute("SELECT to_regclass('telemetry_events')").fetchone()[0] is None:
        print("telemetry_events does not exist; run the migrations on the test database first")
        return 1
    today = datetime.now(timezone.utc).date()
    first = today - timedelta(days=args.days - 1)
    names: list[str] = []
    day = first
    while day <= today:
        name = f"telemetry_events_{day:%Y%m%d}"
        names.append(name)
        nxt = day + timedelta(days=1)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF telemetry_events "
                     f"FOR VALUES FROM ('{day}') TO ('{nxt}')")
        day = nxt

    # Real data has no timestamps in the future: today's partition only holds the elapsed part of the day.
    now_utc = datetime.now(timezone.utc)
    elapsed_today = max(3600.0, (now_utc - datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)).total_seconds())
    per_day = [args.rows_per_day] * (args.days - 1) + [int(args.rows_per_day * elapsed_today / 86400)]
    spans = [86400.0] * (args.days - 1) + [elapsed_today]
    total = sum(per_day)
    print(f"Inserting {total:,} rows into {args.days} daily partitions ...")
    t0 = time.perf_counter()
    for i in range(args.days):
        day_start = datetime.combine(first + timedelta(days=i), datetime.min.time(), tzinfo=timezone.utc)
        conn.execute(
            """
            INSERT INTO telemetry_events (ts, received_at, asset_id, kind, event_type, track_id, x, y, altitude,
                                          speed, heading, confidence, zone_code, severity, payload)
            SELECT %(start)s + (g * interval '1 second') * (%(span)s / %(n)s),
                   %(start)s + (g * interval '1 second') * (%(span)s / %(n)s),
                   1 + (g %% 40),
                   (ARRAY['radar','rf','eoir','acoustic','fence','access','weather'])[1 + (g %% 7)],
                   (ARRAY['track','detection','status'])[1 + (g %% 3)],
                   'VOL-' || (g %% 500),
                   random() * 1000, random() * 700, random() * 120, random() * 20, random() * 359, random(),
                   (ARRAY['Z0','Z1','Z2','Z3','Z4','Z5','Z6'])[1 + (g %% 7)],
                   (ARRAY['info','info','info','warning','critical'])[1 + (g %% 5)],
                   '{"synthetic": true}'::jsonb
            FROM generate_series(0, %(n)s - 1) AS g
            """,
            {"start": day_start, "n": per_day[i], "span": spans[i]},
        )
    insert_s = time.perf_counter() - t0
    conn.execute("ANALYZE telemetry_events")
    size = conn.execute("SELECT pg_size_pretty(sum(pg_total_relation_size(c.oid))) FROM pg_class c "
                        "WHERE c.relname LIKE 'telemetry_events_%' AND c.relkind = 'r'").fetchone()[0]

    # queries as the application issues them, against the most recent day (the "live" window)
    live_start = datetime.now(timezone.utc) - timedelta(minutes=5)
    tests = {
        "state: latest position per track (5 min)": (
            "SELECT DISTINCT ON (track_id) track_id, ts, x, y FROM telemetry_events "
            "WHERE ts >= %s AND track_id IS NOT NULL AND x IS NOT NULL ORDER BY track_id, ts DESC", (live_start,)),
        "track history (30 min)": (
            "SELECT ts, x, y FROM telemetry_events WHERE track_id = 'VOL-7' AND ts >= %s ORDER BY ts LIMIT 2000",
            (datetime.now(timezone.utc) - timedelta(minutes=30),)),
        "events page (60 min, severity critical)": (
            "SELECT ts, kind, severity FROM telemetry_events WHERE ts >= %s AND severity = 'critical' "
            "ORDER BY ts DESC LIMIT 50 OFFSET 0", (datetime.now(timezone.utc) - timedelta(minutes=60),)),
        "count critical (60 min)": (
            "SELECT count(*) FROM telemetry_events WHERE ts >= %s AND severity = 'critical'",
            (datetime.now(timezone.utc) - timedelta(minutes=60),)),
        "count one day": (
            "SELECT count(*) FROM telemetry_events WHERE ts >= %s AND ts < %s",
            (datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
             datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc))),
    }
    results = {}
    for label, (sql, params) in tests.items():
        median, worst, rows = timed(conn, sql, params)
        results[label] = {"median_ms": round(median, 1), "worst_ms": round(worst, 1), "rows": rows}

    # retention: dropping the oldest partition
    t1 = time.perf_counter()
    conn.execute(f"DROP TABLE {names[0]}")
    drop_ms = (time.perf_counter() - t1) * 1000
    left = conn.execute("SELECT count(*) FROM telemetry_events").fetchone()[0]

    print(json.dumps({
        "rows_inserted": total, "insert_seconds": round(insert_s, 1), "rows_per_second": int(total / insert_s),
        "total_size": size, "queries": results, "drop_oldest_partition_ms": round(drop_ms, 1),
        "rows_after_drop": left,
    }, indent=2))

    # clean up everything this script created
    for name in names[1:]:
        conn.execute(f"DROP TABLE IF EXISTS {name}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

