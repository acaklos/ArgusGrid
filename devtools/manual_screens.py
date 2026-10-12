"""Take the screenshots of the manuals from a clean install of the demo package (DOC-010 to DOC-012).

Builds the demo package, installs it into an empty folder against a new empty database, starts it, plays the
simulated attack through the real API, then drives the real client with Playwright (Slovak, light theme, normal
login). Afterwards the server is stopped and the installation folder is removed (DOC-011).

Usage (repository root):  .venv\\Scripts\\python.exe -I devtools\\manual_screens.py [--skip-build] [--port 18090]
Output: docs/manual/screens/*.png
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "devtools"))
import clean_install_proof as proof  # noqa: E402
import secret_scan  # noqa: E402

OUT = ROOT / "docs" / "manual" / "screens"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=18090)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    work = Path(tempfile.mkdtemp(prefix="argus-manual-"))
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    build = [str(py), "-I", str(ROOT / "devtools" / "make_deploy.py"), "--package", "demo", "--profile", "civil",
             "--out", str(work / "build")]
    if args.skip_build:
        build.append("--skip-build")
    r = proof.run(build, ROOT)
    if r.returncode != 0 or "Publish scan: clean." not in r.stdout:
        print(proof.redact(r.stdout[-1500:]))
        return 1
    archive = next((work / "build").glob("*.zip"))
    with zipfile.ZipFile(archive) as z:
        z.extractall(work / "install")
    install = next((work / "install").iterdir())

    # empty database (the same helper logic as the clean-install proof)
    dev_url = (ROOT / "backend" / "data" / "database.url").read_text(encoding="utf-8").strip()
    url = re.sub(r"/[^/]+$", "/argusgrid_manual", dev_url)
    parts = re.match(r"postgresql(?:\+psycopg)?://([^:]+):[^@]*@([^:/]+):?(\d+)?/", dev_url)
    assert parts is not None
    role, host, port = parts.group(1), parts.group(2), parts.group(3) or "5432"
    pw = (ROOT / ".devtools" / "pg.superuser.pw").read_text(encoding="utf-8").strip()
    helper = work / "db.py"
    helper.write_text("\n".join([
        "import psycopg, sys",
        "with psycopg.connect(sys.argv[1], autocommit=True) as c:",
        "    c.execute('DROP DATABASE IF EXISTS argusgrid_manual WITH (FORCE)')",
        "    c.execute('CREATE DATABASE argusgrid_manual OWNER \"' + sys.argv[2] + '\"')",
        "",
    ]), encoding="utf-8")
    r = proof.run([str(py), "-I", str(helper), f"postgresql://argus_super:{pw}@{host}:{port}/postgres", role], work)
    if r.returncode != 0:
        print("database creation failed")
        return 1

    server_started = False
    try:
        r = proof.run(["cmd", "/c", str(install / "setup.bat"), "-AssumeYes", "-DatabaseUrl", url, "-WithDemo"],
                      install, env, timeout=1500)
        if r.returncode != 0:
            print(proof.redact(r.stdout[-2500:]))
            return 1
        accounts = (install / "backend" / "data" / "accounts.txt").read_text(encoding="utf-8")
        match = re.search(r"^sysadmin\s*[:=]\s*(\S+)", accounts, re.M)
        assert match, "initial administrator not found"
        initial = match.group(1)

        r = proof.run(["cmd", "/c", str(install / "start.bat"), "-NoBrowser", "-Port", str(args.port)], install, env,
                      timeout=300)
        if r.returncode != 0:
            print(proof.redact(r.stdout[-1500:]))
            return 1
        server_started = True
        base = f"http://127.0.0.1:{args.port}"

        # the simulated attack, through the real API with the generated device keys
        venv_py = install / ".venv" / "Scripts" / "python.exe"
        r = proof.run([str(venv_py), "-m", "app.simulator", "--speed", "15", "--until", "330", "--base-url", base,
                       "--creds", str(install / "backend" / "data" / "demo-devices.txt")],
                      install / "backend", env, timeout=300)
        print(proof.redact(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "simulator: no output"))
        if r.returncode != 0:
            return 1

        if OUT.exists():
            shutil.rmtree(OUT)
        node_env = {**env, "BASE_URL": base, "ADMIN_USER": "sysadmin", "ADMIN_PASSWORD": initial,
                    "NEW_PASSWORD": "Manual-" + os.urandom(8).hex() + "!Qz7", "OUT_DIR": str(OUT)}
        r = proof.run(["node", "e2e/manual-screens.mjs"], ROOT / "frontend", node_env, timeout=600)
        print(proof.redact(r.stdout[-1500:]), proof.redact(r.stderr[-1500:]))
        if r.returncode != 0:
            return 1
    finally:
        if server_started:
            proof.run(["cmd", "/c", str(install / "stop.bat")], install, env)

    # DOC-011: the installation folder and the secrets of this run are removed, the package is scanned again
    findings = secret_scan.scan_tree(archive.parent / archive.stem)
    shutil.rmtree(work, ignore_errors=True)
    print("Screens written to", OUT, f"({len(list(OUT.glob('*.png')))} files); package scan findings: {len(findings)}")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
