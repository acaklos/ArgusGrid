# Slice 2 (asset registry and device credentials): quality gate evidence

Date: 2026-10-12. Environment as in the previous slices.

## Result

| Check | Evidence | Result |
|-------|----------|--------|
| Backend tests on real PostgreSQL | `pytest` | **175 passed** (139 before, 36 new) |
| Frontend component tests | `vitest run` | **10 passed** |
| Browser tests through the running application, real database, demo data and SMTP sink | `devtools\e2e.ps1` | **27 passed** (10 identity, 10 administration, 7 operations) |
| Shared-component check, type check | `check:shared`, `tsc --noEmit` | passed (34 files), no errors |
| Demo data consistency | `test_demo.py` (7 tests) | every asset inside the site and its zone, every relation endpoint exists, private addresses only |

## Defects found by the tests and fixed in this slice

| Defect | Found by | Fix |
|--------|----------|-----|
| Opening or reloading `/assets/<id>` returned `{"detail":"Not Found"}`: the built client files lived under `/assets`, which is also a page of the application | browser test (reload on the asset page) | Build output moved to `/static` (`vite.config.ts`, `main.py`); regression test `test_deep_links_to_application_pages_serve_the_client` |
| Demo asset RF-04 was placed in zone Z4 although its coordinates lie outside it | `test_every_asset_is_valid_and_inside_site_and_its_zone` | Assigned to the buffer zone Z0 |
| An identical signed request sent twice within one second is refused as a replay | `test_rotation_...` | Intended behaviour (replay protection). Device clients must vary the timestamp or the body. Recorded as AG-D-34 |

## Requirement coverage

| Requirement | Covered by |
|-------------|-----------|
| ARG-012 devices, communication nodes and endpoints; type, lifecycle, software inventory, physical zone, exposure, relations | `test_assets.py` (13 tests incl. validation of every field, lifecycle, relations, topology), e2e 21 to 22, 26 |
| ARG-013 own rotatable key, scope, allowed networks, signed payloads, a device writes only its own events | `test_devices.py` (11 tests), e2e 23 to 25 |
| IDN-014 service credentials generated at setup, stored in an ignored file, read automatically | `demo-devices.txt` written by `app.tools.demo_data`; test `test_demo_credentials_are_least_privilege_and_secrets_are_written_to_an_ignored_file` |
| DEP-050, DEP-051 demo data create, reset, delete; no duplicates; random secrets in an ignored file | `test_create_is_idempotent_and_delete_removes_only_demo_data` |
| ARG-010 capabilities at API level | `test_capabilities_for_assets`, credential endpoints refuse users without `asset.credential.rotate` |

## Security behaviour verified

- The device secret appears once (response of create and rotate). It is stored encrypted (AES-256-GCM) and is absent from
  listings, audit records and the page after a reload (`test_secret_is_shown_once_and_stored_encrypted`, e2e 23).
- Every authentication failure (unknown key, wrong signature, stale or future timestamp, missing headers, source network,
  expiry, revocation, decommissioned asset, replay) gives the same answer `401 device_auth_failed` and one audit record
  with the reason (`test_every_failure_looks_the_same_and_is_audited`).
- A signature is bound to method, path with query and body hash (`test_a_signature_is_bound_to_path_method_and_body`).
- A device key does not open user endpoints, and a user session does not open device endpoints.
- Decommissioning an asset revokes its credentials and ends its access immediately.

## Not done in this slice

| Item | Where it belongs |
|------|------------------|
| Sensor event ingestion (tracks, perimeter and door events) and the simulator that uses the demo credentials | Slice 3 |
| Floor-plan map (Leaflet) and the topology graph (Cytoscape.js): the topology data endpoint exists, the views do not | Slices 3 and 5 |
| Vulnerability matching against the software inventory | Slice 4 |
| Zones are seeded by the demo profile; there is no zone editor and no zone-capability | Possible later addition |
| A shared replay cache for several server processes (it lives in the memory of one process, like the throttle, AG-D-24) | Slice 6 |
| Heartbeat is the only device endpoint so far; per-scope ingestion routes arrive with slice 3 | Slice 3 |
| Visual regression and automated accessibility scan, timing of failed logins | Slice 6 |

## Reproduce

`README.md`, section Tests. Demo data: `python -m app.tools.demo_data create|reset|delete` from the backend directory.
