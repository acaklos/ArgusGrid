# ArgusGrid

Prototype cybersecurity module for the protection of energy infrastructure against hybrid threats
(project PTM_226, Expert Solutions s.r.o., target TRL 7).

Status: slices 0 to 6 are implemented: identity baseline, administration (users, roles, audit, e-mail), the asset
registry with device credentials, sensor ingestion with the simulator, partitioned telemetry and the live
operational map, vulnerability intelligence (zero-day and zero-hour), and the correlation of physical tracks and
cyber signals into hybrid incidents with the topology graph and the split-screen operator dashboard, and the
dual-use profiles, hardening and the generated deploy package with a clean-install proof
(`docs/REQUIREMENTS.md`, `docs/evidence/slice-6.md`).

## Layout

| Path | Content |
|------|---------|
| `backend/` | FastAPI application (`app/`), migrations (`migrations/`), tests (`tests/`) |
| `frontend/` | React + TypeScript client (`src/`), unit tests, browser tests (`e2e/`) |
| `docs/` | Requirements, decision log, evidence reports |
| `devtools/` | Development helpers (database, browser test runner, contrast check). Never packaged |

## Development quick start (Windows)

Prerequisites: Python 3.12, Node.js 20 or newer. PostgreSQL 16 is provided as a portable copy under
`.devtools/` (not installed system-wide).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
powershell -File devtools\dev_db.ps1 -Action init      # first time only
powershell -File devtools\dev_db.ps1 -Action start
cd backend
..\.venv\Scripts\python.exe -m app.tools.prepare_database   # prints the initial administrator password once
..\.venv\Scripts\python.exe -m uvicorn app.main:app_factory --factory --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173 (proxies /api to the backend)
```

The initial administrator is `sysadmin`. Its random password is printed once by `prepare_database` and saved to
`backend\data\accounts.txt` (ignored by Git). The first login forces a password change.

## Demo data

The fictional Kestrel Ridge Energy Complex (zones, assets, relations, device credentials):

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.tools.demo_data create   # or reset, delete
```

Device secrets are written once to `backend\data\demo-devices.txt` (ignored by Git).

## Simulator

With the server running and demo data created, play the hybrid attack against the real ingestion API:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.simulator --speed 10          # 14 simulated minutes at 10x
```

Open the *Operational map* in the application to follow it live.

## Threat intelligence

Sources (CISA KEV, FIRST EPSS, NIST NVD, CSAF) are configured under *Threat intelligence > Sources* and are off by
default. Offline: import a signed bundle after trusting its key. `python -I devtools\intel_smoke.py` checks the
real feeds without storing anything.

## Tests

```powershell
cd backend;  ..\.venv\Scripts\python.exe -m pytest              # API and services, real PostgreSQL
cd frontend; npm test; npm run check:shared; npm run typecheck   # components and shared-component guard
powershell -File devtools\e2e.ps1                                # browser tests against the real backend
.\.venv\Scripts\python.exe -I devtools\contrast_check.py         # theme contrast
.\.venv\Scripts\python.exe -I devtools\telemetry_volume_test.py  # telemetry volume test (test database)
.\.venv\Scripts\python.exe -I devtools	elemetry_volume_test.py   # telemetry volume test (test database)
```

## Configuration

| Variable | Meaning |
|----------|---------|
| `ARGUS_DATABASE_URL` | Database URL (default: `backend/data/database.url`) |
| `ARGUS_DATA_DIR`, `ARGUS_CONFIG_DIR` | Locations of generated files and configuration |
| `ARGUS_ENV` | `production` (default), `development`, `test` |
| `ARGUS_SECURE_COOKIES` | `1` when served over HTTPS |
| `ARGUS_BIND_HOST` | Bind address, `127.0.0.1` by default |
| `ARGUS_WORKERS`, `ARGUS_WORKER_SECONDS` | Background mail worker on or off, and its interval in seconds |

## Deploy package

```powershell
# build the client, generate the package, scan it, zip it (writes dist\ArgusGrid-<version>-<package>-<profile>.zip)
.\.venv\Scripts\python.exe -I devtools\make_deploy.py --package production --profile civil
# prove a clean install: extract, set up, start, log in, change password, stop, verify what is left
.\.venv\Scripts\python.exe -I devtools\clean_install_proof.py --package production --profile civil
```

`--package demo` adds the fictional demonstration site and the simulator; `--profile defense` sets the defense
profile (offline intelligence only, marking, longer retention). The Emergency Owner identifier and secret are printed
once by `make_deploy.py` for the envelope and are not stored. On the target: `setup.bat` (options `-CheckOnly`,
`-DryRun`, `-AssumeYes`, `-DatabaseUrl`, `-WithDemo`), then `start.bat` and `stop.bat`.

## Manuals

`docs/manual/ArgusGrid-Pouzivatelska-prirucka.docx` (user manual) and `ArgusGrid-Instalacna-prirucka.docx`
(installation manual), both in Slovak. They are generated: `devtools/manual_screens.py` takes the screenshots from a
clean install of the demo package and `devtools/build_manuals.py` builds the documents (needs `python-docx`,
listed in `backend/requirements-dev.txt`).
