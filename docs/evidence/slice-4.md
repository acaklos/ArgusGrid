# Slice 4 (vulnerability intelligence: zero-day and zero-hour): quality gate evidence

Date: 2026-10-12. Environment as in the previous slices.

## Result

| Check | Evidence | Result |
|-------|----------|--------|
| Backend tests on real PostgreSQL | `pytest` | **242 passed** (201 before, 41 new) |
| Frontend component and logic tests | `vitest run` | **16 passed** |
| Browser tests through the running application | `devtools\e2e.ps1` | **37 passed** (6 new for intelligence) |
| Shared-component check, type check, contrast | scripts | passed (40 files), no errors, 0 of 24 pairs below minimum |
| Real public feeds with the production fetcher and parsers | `devtools\intel_smoke.py` | see below |
| Matching of the live KEV feed against the demo inventory | `devtools\intel_load_test.py` | see below |

## Real feeds (checked on 2026-10-12, nothing was stored)

| Source | Result |
|--------|--------|
| CISA KEV | 1,777,558 bytes, 1,739 records parsed |
| FIRST EPSS (CSV, gzip, one redirect) | 2,708,040 bytes, 385,738 scores parsed |
| NIST NVD CVE API 2.0 (changes of the last day) | 3,194,854 bytes, 1,108 records parsed |

Live KEV imported into the test database with the demo site: 1,739 vulnerabilities created, import and matching 1.8 s,
**0 new findings** (the demo inventory has no product that KEV names with an affected, verifiable version; a
wrongly read "no fix" had first produced 600 findings, see below).

The CSAF parser and the signed bundle are verified against hand-written documents only; no live CSAF provider was
contacted.

## Defects and design flaws found while testing against real data, fixed in this slice

| Finding | Found by | Fix |
|---------|----------|-----|
| The generic KEV sentence "apply mitigations ... or discontinue use if mitigations are unavailable" was read as "no fix exists", so almost every KEV entry became zero-day | live KEV import: 600 findings | Fix state is read from explicit wording only (end-of-life, unsupported, no patch available); the sentence above is a workaround. Regression test in `test_kev_parser` |
| Matching by product name alone raised every KEV entry for "Windows" on every Windows asset (1,400 findings) | live KEV import | Match confidence: a product-only match without a version bound is `low` and is raised only while the vulnerability is zero-day or zero-hour (`AG-D-47`) |
| A very short product name ("tc") matched any software containing that token | `test_a_product_substring_does_not_match...` | A partial product name must have at least 5 characters |
| The EPSS download URL redirects; the fetcher refused every redirect | live smoke test | At most 3 redirects, every target checked like the first URL (HTTPS only, no credentials) |
| EPSS would have created a record for each of 385,738 CVEs | design review of the live volume | EPSS only scores already known vulnerabilities (`AG-D-48`); lookups are chunked |
| Test expected an EPSS score on a non-CVE identifier | `test_merge_never_erases...` | EPSS ignores identifiers that are not CVEs |

## Requirement coverage

| Requirement | Covered by |
|-------------|-----------|
| ARG-016 dynamic identification of zero-day and zero-hour vulnerabilities from external sources | parsers (KEV, NVD, EPSS, CSAF), importer and source runner, worker, classification; `test_intel_units.py` (27), `test_intel_service.py` (14), e2e 32 to 37 |
| Matching against the asset software inventory (and firmware) | `test_demo_intelligence_is_matched_to_the_inventory`, `test_changing_the_software_inventory_triggers_matching` |
| Alerts (template `alert.critical`) to roles that may acknowledge, once per vulnerability | `test_alerts_go_once_to_users_who_can_acknowledge` |
| Offline path for the defense profile (signed bundle, trusted keys, offline-only policy) | `test_signed_bundle_needs_a_trusted_key`, `test_offline_only_profile...`, e2e 35 and 36 |
| Evidence and workflow: acknowledge, mitigate, false positive with note and audit | `test_acknowledging_a_finding_is_audited...`, e2e 33 |

## Definitions in force (AG-D-46)

- **Exploited**: listed as known exploited (KEV) or EPSS at or above the threshold (default 0.5).
- **Zero-day**: exploited and no vendor fix exists.
- **Zero-hour**: exploited and published (else first seen) within the window (default 72 hours).
- Classification is computed when read, so zero-hour decays by itself; a finding is not rewritten.

## Not done in this slice

| Item | Where it belongs |
|------|------------------|
| A live CSAF provider (provider metadata discovery, ROLIE feeds) is not implemented; a single advisory document or URL is | Possible later addition |
| NVD API keys and paging for large ranges; the runner reads the changes since the last run (at most 119 days) in one request | Slice 6 |
| Scheduled runs are done by the mail worker thread of one process | Slice 6 |
| Live push of new findings to the map page (the stream publishes `intel` messages; the map does not show them yet) | Slice 5 (dashboard) |
| Correlation of a finding with physical events into a hybrid incident | Slice 5 |
| The inventory carries what operators enter; there is no automatic discovery of installed software | Out of scope |
| Timing of failed logins, accessibility scan, visual regression | Slice 6 |

## Reproduce

`README.md`. Online smoke test: `python -I devtools\intel_smoke.py`. Live volume test:
`python -I devtools\intel_load_test.py` (replaces the content of the test database).
