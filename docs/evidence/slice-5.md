# Slice 5 (hybrid correlation, topology graph, split-screen dashboard): quality gate evidence

Date: 2026-10-12. Environment as in the previous slices (Windows, portable PostgreSQL 16, Python 3.12, Node 20).

## Result

| Check | Evidence | Result |
|-------|----------|--------|
| Backend tests on real PostgreSQL | `pytest` | **262 passed** (242 before, 20 new in `test_incidents.py`) |
| Frontend component and logic tests | `vitest run` | **20 passed** (4 new for the layered layout) |
| Browser tests through the running application | `devtools\e2e.ps1` | **40 passed** (3 new: dashboard split, workflow, tablet and phone) |
| Shared-component check, type check | `npm run check:shared`, `tsc --noEmit` | passed (47 files), no errors |
| Production build | `npm run build` | passed; cytoscape and leaflet are separate chunks (main 486 kB, 147 kB gzip) |

Screenshots of the browser run: `frontend/e2e/results/40-dashboard-split.png`, `41-dashboard-tablet.png`,
`42-dashboard-mobile.png` (generated, not committed).

## Requirement coverage

| Requirement | Covered by |
|-------------|-----------|
| ARG-017 correlation of physical threats and cyber incidents into hybrid incidents, pushed live | engine unit tests (blast radius, paths, physical link, scoring, recommendations); `test_a_drone_at_the_wireless_access_point_and_a_zero_day...`, `test_incidents_are_published_on_the_stream`, `test_simulated_attack_produces_the_expected_incident_end_to_end`; e2e 38 |
| ARG-018 topology graph with the domino effect on PLCs by hop distance | `test_graph_for_the_cyber_pane`, layout tests, e2e 38 (`data-nodes` holds the roles: UAV-001 physical event, SCADA-SRV-01 compromised, PLC-SW1 and PLC-GT1 at risk) |
| ARG-019 split-screen dashboard with one shared incident state | e2e 38 (both panes side by side at 1440 px, incident chip drives map link and graph), e2e 40 (stacked at 900 px, tabs at 375 px, no horizontal overflow) |
| Incident workflow, escalation, notes, audit, capabilities | `test_workflow_transitions_capabilities_notes_and_audit`, `test_escalation_raises_severity_and_alerts_managers`, `test_incident_views_need_the_capability`; e2e 39 |
| Alert e-mail for incidents (`incident.hybrid`) | `test_alert_mail_goes_to_people_who_can_triage_and_has_the_incident_in_it` |

## Defects and design flaws found while testing, fixed in this slice

| Finding | Found by | Fix |
|---------|----------|-----|
| Leaflet panes use z-index up to 1000 and sat above the password dialog; the Radix overlay could not be clicked through the buttons below the map | browser test 3 timed out (click intercepted by a zone path) | `.sitemap` is its own stacking context |
| The incident timeline received an "Evidence updated" entry every second while the drone moved | screenshot review of the dashboard | `AG-D-58`: signature of the operator-relevant evidence, refresh of the position at most every 15 s; `test_a_moving_track_does_not_flood_the_timeline` |
| Several assets were exposed to the same drone (access point and tablet), the first version showed one | scenario test | all candidates are kept in the evidence, entry nodes and hybrid edges for each, one `disable_wireless` recommendation per wireless asset |
| One incident per drone was not guaranteed when two assets had signals | scenario test | one incident per track, the others listed as `other_assets` (`AG-D-53`) |
| My new dashboard style `.chip` overrode the existing chip of the e-mail variable list | review of a failing browser test screenshot | renamed `.incident-chip` |
| The template editor test edited the body while the editor was still reloading the saved version (race that the new page timing exposed) | browser test 18 | the test waits for the "Customised (version n)" badge; the page behaviour is unchanged |

## Not done in this slice

| Item | Where it belongs |
|------|------------------|
| A connector line drawn across the splitter between the two panes; the link is drawn on the map and the selection is shared | Possible refinement, `AG-D-59` |
| Replay of the blast radius hop by hop as an animation; the list and the graph show the hops statically | Possible refinement |
| Scoring weights and exposure radii are first proposals, not calibrated with real operations or sensor data | Validation in slice 6 and with the customer |
| Correlation runs in one process (rate limited per process); several workers would each evaluate | Slice 6 (shared store, `AG-D-24`) |
| Cyber alarms come from the simulator and the sensors of the demo site; no real IDS or SIEM connector exists | Out of scope for the prototype |
| Browser tests run in Chromium only; accessibility scan and visual regression not run | Slice 6 |

## Reproduce

`README.md`. Backend: `pytest` in `backend\`. Browser: `powershell -File devtools\e2e.ps1` (optionally
`-Spec identity` to run one spec file). Simulator for a manual look: `python -m app.simulator --speed 15`.
