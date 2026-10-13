# Slice 6 (dual-use profiles, hardening, packaging, clean-install proof): quality gate evidence

Date: 2026-10-12. Environment as in the previous slices (Windows 11, portable PostgreSQL 16, Python 3.12, Node 20).

## Result

| Check | Evidence | Result |
|-------|----------|--------|
| Backend tests on real PostgreSQL | `pytest` | **295 passed** (262 before, 33 new) |
| Frontend component and logic tests | `vitest run` | **23 passed** (3 new: marking banner, row wrapping of the graph layout) |
| Browser tests through the running application | `devtools\e2e.ps1` | **46 passed** (6 new: accessibility in 2 themes + login, visual baselines x3) |
| Shared-component check, type check, build | scripts | passed (50 files), no errors, built |
| Clean install, production package, civil profile | `devtools\clean_install_proof.py` | **28 of 28 checks passed** |
| Clean install, demo package, defense profile | `devtools\clean_install_proof.py --package demo --profile defense` | **28 of 28 checks passed** |

## New tests and what they prove

| Area | Tests | Proves |
|------|-------|--------|
| Profiles | `test_profile.py` (6) | the profile comes from the environment and unknown values are refused; the session tells the client the profile before login; defense forces offline-only and an administrator cannot switch it off (422 `intel.profile_offline_forced`); audit export starts with the marking line; defense retention default is 90 days and an explicit setting wins |
| Scan and package | `test_deploy_scan.py` (21) | each denied file, directory, private key, connection string with password, token, assigned secret, the loginless flag, banner and module stop the publish; placeholders do not; the sealed owner file is checked (verifier only, no extra fields, installation id); the packaged application has no `dev_loginless.py`, no demo or simulator in production, and the owner secret is not written anywhere in the package |
| Requirements | `test_requirements.py` (1) | every third-party import of the application is a runtime requirement |
| Hardening | `test_hardening.py` (3) | security headers on every response; WebSocket origin in the policy; failed-login timing |
| Accessibility | `ui-a11y.spec.ts` (3) | no serious or critical axe-core violation (WCAG 2.0 and 2.1 A and AA rules) on the login page and on 12 pages, dark and light theme |
| Visual regression | `ui-visual.spec.ts` (3) | login page unchanged (dark and light desktop, dark phone); baselines in `frontend/e2e/ui-visual.spec.ts-snapshots` |

## Clean-install proof (release gate, rule 21 section 7)

The script builds the package, extracts it into an empty folder, creates a new empty database, runs setup, start,
login, password change and stop, and checks what is left. Both runs (production civil, demo defense) passed these
checks:

- package builds and the publish scan is clean, and the extracted package passes the scan again;
- check-only reports no blockers; dry run changes nothing and keeps the setup files;
- setup succeeds, then `setup.bat`, `setup.ps1` and the marker file are gone (D-13);
- the initial administrator password is generated (12 or more characters) and saved to the ignored file only;
- start prepares the database and the server becomes ready; health and the client are served;
- the loginless flag is set in the environment on purpose (`development` and flag on) and is ignored: login is
  required and no development header exists;
- the profile reported by the API is the one in the package; wrong password refused; the first login with the
  generated password forces a change; the change works; administration works;
- the site endpoint works without the demo module (production) and serves the demonstration site (demo);
- stop ends only this server, the process file is removed, the server no longer answers;
- no bytecode caches in the application folder, only the expected top-level items, the sealed owner file holds a
  verifier and no plaintext, the installed tree (outside `.venv`, `data` and `config\app.env`) passes the scan.

## Failed-login timing (LCK-011)

12 failed logins against known users and 12 against unknown names, in process on this machine:
median 101 ms (known user) and 97 ms (unknown user). The answers are the same text and the same status. This is an
indication, not a proof; the test bound is a ratio between 0.5 and 2.0.

## Defects and design flaws found while testing, fixed in this slice

| Finding | Found by | Fix |
|---------|----------|-----|
| `httpx` was imported by the application but missing from `requirements.txt`; the package installed but did not start | clean-install proof (first real run) | added; `test_requirements.py` keeps imports and requirements in step |
| The production site endpoint imported the demo module and would have failed in a production package | design review while building the allow list | the endpoint falls back to the extent of the defined zones; the map fits to the site extent |
| The loginless flag name and banner text were in `config.py` and the client bundle; the scan (DEV-006) would have failed on every package | scan design against rule 20 | flag and banner live only in the development module; the session payload carries the banner |
| A table region was not reachable by keyboard (`/audit`) | axe-core scan | shared `TableWrap` (focusable, labelled region), `check:shared` forbids the raw wrapper |
| The incident chips used `aria-pressed` on a `listitem`; the splitter handle pointed `aria-controls` at an id that did not exist | axe-core scan | chips are buttons in a labelled group; the panes carry the id the splitter references |
| `setup.ps1` could not detect Python (embedded double quotes are mangled by Windows PowerShell 5.1) | clean-install proof | one number is printed, no quotes inside the code |
| The proof script waited forever: the server started by `start.bat` inherits the captured pipe | clean-install proof | output goes to files; documented in the script |
| A shell patch put a BEL character into the decision log and a tab into a setup script | review of the patch result | removed; byte scan of all text files added to my routine (CLAUDE.md pitfall) |

## Not done in this slice (carried forward)

| Item | Note |
|------|------|
| The manuals have not been opened in Word (no Word on this machine); layout and the table of contents are unchecked | open and review once, see the section on manuals |
| Larger password blocklist | the shipped list has 110 entries; the file `app/data/common_passwords.txt` is read as is, so a large public list can be dropped in. No breach list was fabricated |
| Shared replay and throttle store for more than one worker (AG-D-24, AG-D-34) | still in process memory; documented limit: run one worker |
| HTTP load test of the API under concurrent clients | only the database volume test exists |
| NVD paging and API keys for large ranges | one request per run |
| SMTP over STARTTLS or SSL against a real server | tested against a local sink only |
| Hardened container form for the defense profile (no outbound network) | the Windows package is the only form built |
| PostgreSQL installation by the setup | production package: by decision AG-D-64 the operator provides the database. Demo package: done, see "Addendum: tools bootstrap" |
| Code signing of the archive | a SHA-256 file is written, nothing is signed |
| The markings, retention and exposure radii of the defense profile are proposals | to be set by the customer; no accreditation or certification is claimed |
| The clean install ran on the development machine (Python and PostgreSQL were already present, network for pip) | a pristine machine run is still to be done for the TRL 7 evidence package |
| Visual baselines were taken on this machine (Windows, Chromium) | they must be regenerated on another platform |

## Reproduce

`README.md` section "Deploy package". Tests: `pytest` in `backend\`, `npx vitest run` and `devtools\e2e.ps1` for the
browser suite. Note: `make_deploy.py` prints the Emergency Owner identifier and secret of the package it builds;
a package built for a test (such as the proof) must never be installed on a real site.

## Manuals (DOC-002, DOC-003, DOC-010 to DOC-012, DOC-020 to DOC-023)

| Item | Result |
|------|--------|
| User manual, Slovak | `docs/manual/ArgusGrid-Pouzivatelska-prirucka.docx`: 14 chapters, 21 tables, 24 screens |
| Installation manual, Slovak | `docs/manual/ArgusGrid-Instalacna-prirucka.docx`: 9 chapters, 12 tables |
| Screenshots | 25 files in `docs/manual/screens`, taken by `devtools/manual_screens.py` from a clean install of the demo package (new empty database, setup with demo data, simulator played through the real API, normal login, Slovak, light theme). Password fields are masked in the images |
| After the run | the server was stopped, the installation folder and its credentials deleted, and the package scanned again (0 findings) |
| Checks | a test fails when the package notes or the built manuals mention the owner credential, recovery, reset tools or development modes; both files re-open with python-docx and pass a zip integrity test |

Defects found while taking the screenshots and fixed (AG-D-68, AG-D-69):

| Finding | Fix |
|---------|-----|
| The create-user dialog preselected the service role "Device Agent" (the lowest level of the list) and the server accepted it for a person | the service role is neither offered nor accepted for people; default SOC Operator; test `test_the_service_role_is_not_offered_or_accepted_for_people` |
| Slovak screens showed English incident titles and English system entries on the timeline | titles and entries are built by the client from structured fields (catalogue keys `incident.title.*`, `incident.event_text.*`) |
| The topology graph was unreadable in a half-screen pane: nine controllers in one row shrank the whole graph | layers wrap after six nodes, tighter spacing, larger labels; test for the wrapping |
| The password masks in screenshots used a flashy colour | neutral mask colour |

Not verified for the manuals: the .docx files could not be rendered here (no Word or LibreOffice on this machine),
so page breaks, the table of contents (a field that Word refreshes on opening) and the look of the tables were
not seen. They should be opened and checked once in Word before they are handed over. Texts that come from
sensors and feeds, the names of e-mail templates and the descriptions of roles are shown by the application in
English; the manuals say so.

## Addendum: tools bootstrap for the demo package (AG-D-70)

Date: 2026-10-13. Request: the demo should be ready to use after one installation, without a prepared database.

| Check | Evidence | Result |
|-------|----------|--------|
| Backend tests | `pytest` (whole suite) | **299 passed** (4 new in `test_deploy_scan.py`: demo-only bootstrap file, pin format and host list, script parsing, checksum check) |
| Clean install with no database given, demo package, defense profile | `clean_install_proof.py --package demo --profile defense --bootstrap --local-cache <folder>` | **33 of 33 checks passed** |
| Real download path | first run without cache: Python, pip and PostgreSQL archives were downloaded and accepted by their SHA-256, unpacked, requirements installed | worked up to the cluster start (found the defect below); the repeat used the verified local copies |

What the proof exercised: embedded Python used, no virtual environment; only `bin`, `lib`, `share` of the PostgreSQL
archive unpacked (no administration tool); cluster on 127.0.0.1 at port 54340; database URL stored only in
`backend\data\database.url`; setup removed itself; start started the cluster; login, forced password change and the
demo site worked; stop ended the application and the cluster; nothing but the expected top-level items was left.

Defects found and fixed:

| Finding | Fix |
|---------|-----|
| `pip install` of the pinned wheel through the wheel itself refused ("to modify pip, run python -m pip") | the pure-Python wheel is unpacked into `site-packages` |
| `Start-Process -Wait` on `pg_ctl start` never returned, because it also waits for the server that pg_ctl leaves running (setup hung) | one helper waits for the single process; output goes to files |

How the pins were obtained: the pip wheel hash is the digest published by the package index. The Python and
PostgreSQL archives were downloaded once and hashed here (the vendors' download pages were not used as a
cross-check): the values prove that later downloads are the same files, not that the vendor's first file was
authentic. Review the pins before a release.

Not verified: a machine without Python or without the Visual C++ runtime (the proof ran on the development machine
with `-EmbeddedPython`; the missing-runtime path only copies the DLLs of the embedded Python and checks that
`postgres.exe --version` runs); an offline install end to end (pip still needs the package index); proxies and
virus scanners that block the download; running two installations on one machine at the same time.
