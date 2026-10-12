"""Clean-install proof (release gate, rules/21 section 7). Development only, never packaged.

Builds the package, extracts it into an empty folder, runs setup and start there against a new database,
logs in with the generated password, changes it, stops, and verifies what is left behind.

Usage (repository root):
    .venv\\Scripts\\python.exe -I devtools\\clean_install_proof.py [--package production|demo] [--profile civil|defense]
                                                               [--port 18080] [--skip-build]
Needs the development PostgreSQL cluster (devtools\\dev_db.ps1 -Action start) and network access for pip.
The report is printed as a table and written to dist\\proof-<package>-<profile>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "devtools"))
import secret_scan  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    return bool(ok)


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    """Run to completion with output going to files: a server started by start.bat inherits pipe handles, so
    waiting for pipe EOF would never end."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=out, stderr=err, timeout=timeout)
        out.seek(0)
        err.seek(0)
        return subprocess.CompletedProcess(cmd, proc.returncode, out.read().decode("utf-8", "replace"),
                                           err.read().decode("utf-8", "replace"))


def redact(text: str) -> str:
    return re.sub(r"(password|secret)(\s*[:=]\s*)\S+", r"\1\2<hidden>", text, flags=re.I)


class Client:
    def __init__(self, base: str) -> None:
        self.base = base
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | str, dict[str, str]]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.csrf and method != "GET":
            req.add_header("X-CSRF-Token", self.csrf)
        try:
            with self.opener.open(req, timeout=15) as r:
                raw, status, headers = r.read().decode("utf-8"), r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            raw, status, headers = e.read().decode("utf-8"), e.code, dict(e.headers)
        try:
            return status, json.loads(raw) if raw else "", headers
        except ValueError:
            return status, raw, headers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--package", choices=["production", "demo"], default="production")
    parser.add_argument("--profile", choices=["civil", "defense"], default="civil")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    py = ROOT / ".venv" / "Scripts" / "python.exe"
    work = Path(tempfile.mkdtemp(prefix="argus-proof-"))
    print(f"Working folder: {work}")
    out = ROOT / "dist"

    # 1. build ---------------------------------------------------------------------------------------
    build = [str(py), "-I", str(ROOT / "devtools" / "make_deploy.py"), "--package", args.package,
             "--profile", args.profile, "--out", str(work / "build")]
    if args.skip_build:
        build.append("--skip-build")
    r = run(build, ROOT)
    check("package builds and the publish scan is clean", r.returncode == 0 and "Publish scan: clean." in r.stdout)
    if r.returncode != 0:
        print(redact(r.stdout[-2000:]), redact(r.stderr[-1000:]))
        return 1
    archive = next((work / "build").glob("*.zip"))

    # 2. extract into an empty folder -----------------------------------------------------------------
    target = work / "install"
    target.mkdir()
    with zipfile.ZipFile(archive) as z:
        z.extractall(target)
    install = next(target.iterdir())
    check("package extracts into an empty folder", (install / "setup.bat").is_file())
    # the package content passes the scan again after unzipping (the archive is what is delivered)
    check("extracted package passes the publish scan", secret_scan.scan_tree(install) == [])

    # 3. database ---------------------------------------------------------------------------------------
    dev_url = (ROOT / "backend" / "data" / "database.url").read_text(encoding="utf-8").strip()
    proof_url = re.sub(r"/[^/]+$", "/argusgrid_proof", dev_url)
    parts = re.match(r"postgresql(?:\+psycopg)?://([^:]+):[^@]*@([^:/]+):?(\d+)?/", dev_url)
    if parts is None:
        return 1
    role, host, port = parts.group(1), parts.group(2), parts.group(3) or "5432"
    pw_file = ROOT / ".devtools" / "pg.superuser.pw"
    superuser_pw = pw_file.read_text(encoding="utf-8").strip() if pw_file.is_file() else ""
    admin_url = f"postgresql://argus_super:{superuser_pw}@{host}:{port}/postgres"
    helper = work / "db.py"
    helper.write_text("\n".join([
        "import psycopg, sys",
        "url, role = sys.argv[1], sys.argv[2]",
        "with psycopg.connect(url, autocommit=True) as c:",
        "    c.execute('DROP DATABASE IF EXISTS argusgrid_proof WITH (FORCE)')",
        "    c.execute('CREATE DATABASE argusgrid_proof OWNER \"' + role + '\"')",
        "",
    ]), encoding="utf-8")
    r = run([str(py), "-I", str(helper), admin_url, role], work)
    if not check("empty proof database created", r.returncode == 0, redact(r.stderr[-200:])):
        return 1

    # 4. setup ------------------------------------------------------------------------------------------
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    check("check-only reports no blockers", run(["cmd", "/c", str(install / "setup.bat"), "-CheckOnly", "-DatabaseUrl", proof_url],
                                                  install, env).returncode == 0)
    r = run(["cmd", "/c", str(install / "setup.bat"), "-DryRun", "-DatabaseUrl", proof_url], install, env)
    check("dry run changes nothing and keeps the setup files",
          r.returncode == 0 and (install / "setup.ps1").exists() and not (install / ".venv").exists())
    extra = ["-WithDemo"] if args.package == "demo" else []
    r = run(["cmd", "/c", str(install / "setup.bat"), "-AssumeYes", "-DatabaseUrl", proof_url, *extra], install, env, timeout=1500)
    check("setup succeeds", r.returncode == 0, f"exit {r.returncode}")
    if r.returncode != 0:
        print(redact(r.stdout[-3000:]), redact(r.stderr[-1500:]))
        return 1
    check("setup removed itself after success (D-13)",
          not (install / "setup.bat").exists() and not (install / "setup.ps1").exists()
          and not (install / ".setup-done").exists())
    accounts = install / "backend" / "data" / "accounts.txt"
    check("initial administrator saved to the ignored file", accounts.is_file())
    match = re.search(r"^sysadmin\s*[:=]\s*(\S+)", accounts.read_text(encoding="utf-8"), re.M) if accounts.is_file() else None
    check("password has the generated form (not in source or documents)", bool(match) and len(match.group(1)) >= 12)
    admin_password = match.group(1) if match else ""

    # 5. start (development flags set on purpose: they must be ignored, DEV-007) ------------------------
    start_env = {**env, "ARGUS_ENV": "development", "ARGUS_DEV_LOGINLESS": "1"}
    r = run(["cmd", "/c", str(install / "start.bat"), "-NoBrowser", "-Port", str(args.port)], install, start_env, timeout=300)
    check("start prepares the database and the server becomes ready", r.returncode == 0, redact(r.stdout[-200:]))
    base = f"http://127.0.0.1:{args.port}"
    c = Client(base)
    try:
        status, health, _h = c.call("GET", "/api/v1/health")
        check("health endpoint answers", status == 200 and isinstance(health, dict) and health.get("status") == "ok")
        status, page, _h = c.call("GET", "/")
        check("the client is served", status == 200 and isinstance(page, str) and "<div id=\"root\"" in page)
        status, info, headers = c.call("GET", "/api/v1/auth/session")
        check("loginless flag is ignored in the package (login required, no dev banner)",
              status == 200 and isinstance(info, dict) and info.get("authenticated") is False
              and "X-Argus-Dev-Mode" not in headers and "x-argus-dev-mode" not in {k.lower() for k in headers})
        check(f"profile is {args.profile}", isinstance(info, dict) and info.get("profile", {}).get("name") == args.profile)

        status, bad, _h = c.call("POST", "/api/v1/auth/login", {"username": "sysadmin", "password": "wrong-password-1"})
        check("a wrong password is refused", status in (401, 403))
        status, login, _h = c.call("POST", "/api/v1/auth/login", {"username": "sysadmin", "password": admin_password})
        ok = status == 200 and isinstance(login, dict) and login.get("must_change_password") is True
        check("first login with the generated password forces a change", ok)
        c.csrf = (login or {}).get("csrf_token", "") if isinstance(login, dict) else ""
        new_password = "Proof-" + os.urandom(9).hex() + "!Zq7"
        status, _b, _h = c.call("POST", "/api/v1/auth/change-password",
                                {"current_password": admin_password, "new_password": new_password})
        check("password changed", status == 204, f"status {status}")
        status, info, _h = c.call("GET", "/api/v1/auth/session")
        check("session is fully usable after the change",
              isinstance(info, dict) and info.get("authenticated") and not info.get("must_change_password"))
        status, users, _h = c.call("GET", "/api/v1/users?page_size=5")
        check("administration works (user list)", status == 200)
        status, site, _h = c.call("GET", "/api/v1/site")
        check("site endpoint works without the demo module" if args.package == "production" else
              "site endpoint serves the demonstration site",
              status == 200 and isinstance(site, dict)
              and (bool(site.get("buildings")) if args.package == "demo" else site.get("buildings") == []))
    finally:
        r = run(["cmd", "/c", str(install / "stop.bat")], install, env)
    check("stop ends only this server", r.returncode == 0 and "stopped" in r.stdout.lower(), r.stdout.strip()[-80:])
    time.sleep(1.0)
    try:
        urllib.request.urlopen(base + "/api/v1/health", timeout=3)
        check("server no longer answers", False)
    except (urllib.error.URLError, OSError):
        check("server no longer answers", True)
    check("process file removed", not (install / "backend" / "data" / "server.pid").exists())

    # 6. what is left behind -----------------------------------------------------------------------------
    leftovers = [p.relative_to(install).as_posix() for p in (install / "backend" / "app").rglob("__pycache__")]
    check("no bytecode caches in the application folder", not leftovers, ", ".join(leftovers[:3]))
    top = sorted(p.name for p in install.iterdir())
    allowed = {".venv", "backend", "frontend", "INSTALL.txt", "start.bat", "start.ps1", "stop.bat", "stop.ps1"}
    check("only the expected top-level items exist", set(top) <= allowed, ", ".join(top))
    owner = install / "backend" / "config" / "owner.sealed"
    check("sealed owner file is present and holds no plaintext secret",
          owner.is_file() and "$argon2" in owner.read_text(encoding="utf-8"))
    runtime_findings = [f for f in secret_scan.scan_tree(install, expect_owner_file=True)
                        if not f.path.startswith((".venv", "backend/data", "backend/config/app.env"))]
    check("installed tree (outside runtime folders) passes the scan", runtime_findings == [],
          "; ".join(str(f) for f in runtime_findings[:3]))

    # report ------------------------------------------------------------------------------------------
    out.mkdir(exist_ok=True)
    report = {"package": args.package, "profile": args.profile, "archive": archive.name,
              "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in RESULTS]}
    (out / f"proof-{args.package}-{args.profile}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    failed = [n for n, ok, _d in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed.")
    shutil.rmtree(work, ignore_errors=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
