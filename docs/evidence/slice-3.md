# Slice 3 (sensor ingestion, telemetry storage, simulator, operational map): quality gate evidence

Date: 2026-10-12. Environment as in the previous slices.

## Result

| Check | Evidence | Result |
|-------|----------|--------|
| Backend tests on real PostgreSQL | `pytest` | **201 passed** (175 before, 26 new) |
| Frontend component and logic tests | `vitest run` | **16 passed** |
| Browser tests through the running application, real database, demo data, SMTP sink and the real simulator | `devtools\e2e.ps1` | **31 passed** (4 new for the map) |
| Shared-component check, type check, contrast check | scripts | passed (39 files), no errors, 0 of 24 pairs below minimum |
| Telemetry volume test | `devtools\telemetry_volume_test.py` | see below |

## Volume test (ARG-025), measured on this development machine

1,944,750 synthetic rows in 7 daily partitions (about 4 events per second on average, the rate of the simulated
site), PostgreSQL 16.13 with default settings, total size 556 MB including indexes.

| Operation | Median | Worst of 5 |
|-----------|--------|------------|
| Insert (server side, set based) | 26,277 rows per second | - |
| State query: latest position per track, last 5 minutes (500 tracks) | 75 ms | 120 ms |
| Track history, 30 minutes | 2.2 ms | 20 ms |
| Events page, last 60 minutes, severity critical | 2.1 ms | 3 ms |
| Count critical events, 60 minutes | 27 ms | 37 ms |
| Count one day (about 300,000 rows) | 176 ms | 295 ms |
| Drop the oldest daily partition (retention) | 71 ms | - |

What this does and does not show: the database layer keeps the live queries in the tens of milliseconds at about two
million rows and retention is a partition drop, not a row-by-row delete. It is not a load test of the HTTP path with
many concurrent devices. The first run exposed a flaw of the test itself (rows with future timestamps), which was
corrected before the numbers above were taken.

HTTP ingestion measured with the simulator on the same machine: 214 requests in 5.0 s, about 23 ms per request, no
failures.

## Defects and design flaws found by the tests and the screenshot review, fixed in this slice

| Finding | Found by | Fix |
|---------|----------|-----|
| Every ingest request re-checked the daily partitions (4 catalogue queries), slowing ingestion | review of the first live run | Per-process partition cache, checked once per day |
| The per-address device limit (600 per minute) dropped simulator traffic mid-scenario | browser test | Limits per claimed key (1,200 per minute) and per address (12,000), `AG-D-41` |
| The alarm list was flooded by routine critical track updates and hid the cyber alarm | `test_simulator_drives_the_real_api...` | Alarms are events of type alarm only; threat is shown by tracks and sectors |
| The fallback zone Z0 (whole site) was shown as a "threatened sector" | screenshot | Background zones locate a position but are not sectors, `AG-D-42` |
| The track jumped between radar and coarse RF fixes | screenshot | Precise sources (radar, EO/IR) win within 5 s, on the server and in the client, `AG-D-43` |
| A consumed iterator emptied the zone list | `test_site_endpoint_and_airspace_settings` | `list(...)` |
| Ring test assumed the mast lies in the alert ring; it lies in the warning ring (about 540 m) | `test_ring_and_zone_classification` | Test corrected |

## Requirement coverage

| Requirement | Covered by |
|-------------|-----------|
| ARG-014 ingestion of UAV tracks, perimeter and door events with signed device requests | `test_telemetry.py`: validation (10 cases), per-scope authorisation, device binding, batch limit, simulator end to end |
| ARG-015 map with floor plan, zones, sensors, moving UAV marker and the threatened sector | e2e 28 to 30, `geometry.test.ts` |
| ARG-025 time-partitioned telemetry apart from configuration, retention, volume test | migration 0004, `test_retention_drops_whole_old_partitions`, volume test above |
| ARG-018/019 (precondition) physical context and live stream | WebSocket `/api/v1/stream`: authenticated, same-origin, `test_stream_*` |
| IDN-014 simulator uses the generated device credential file, never prompts | `python -m app.simulator`, e2e 28 |

## Behaviour worth stating

- A device can only report event kinds its key allows, always against its own asset; the server classifies position
  (ring, zone, severity) and a device can raise but never lower the severity.
- Positions outside the site by more than 2 km, ages over one hour and future timestamps over two minutes are rejected
  event by event; accepted and rejected events are reported in one response.
- The live stream drops messages for slow clients instead of blocking ingestion; the page also refreshes its state
  every 30 seconds.

## Not done in this slice

| Item | Where it belongs |
|------|------------------|
| Correlation of physical tracks and cyber events into hybrid incidents; the `cyber` event is stored and shown as an alarm only | Slice 5 |
| Cytoscape topology graph and the split-screen dashboard | Slice 5 |
| Vulnerability intelligence (zero-day, zero-hour) | Slice 4 |
| The simulator emits already fused tracks (one track id for all sensors). Association of detections from several sensors is not modelled | Out of scope for the prototype |
| HTTP load test with many concurrent devices, WebSocket behaviour with many clients | Slice 6 |
| Several server processes: the stream hub, replay cache and throttles are per process (AG-D-24, AG-D-34) | Slice 6 |
| Rollups of old telemetry before purge (retention only drops) | Possible later addition |
| Map rendering is verified in Chromium only; no automated accessibility scan of the map | Slice 6 |

## Reproduce

`README.md`: demo data, simulator (`python -m app.simulator --speed 10`), tests, volume test.
