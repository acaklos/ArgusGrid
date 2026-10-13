"""Generate the deploy package (DEP-001 to DEP-004, DEP-020 to DEP-022).

Nobody edits the package by hand. The package is built from an allow list, receives a sealed owner file with a
fresh installation id, is scanned for secrets and development-only code, and only then zipped.

Usage (repository root):
    .venv\\Scripts\\python.exe -I devtools\\make_deploy.py [--package production|demo] [--profile civil|defense]
                                                         [--out dist] [--skip-build]

The owner identifier and secret are printed ONCE for the envelope in the owner's safe. They are not stored.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "devtools"))
sys.path.insert(0, str(ROOT / "backend"))

import owner_tool  # noqa: E402
import secret_scan  # noqa: E402

BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
TEMPLATES = ROOT / "devtools" / "deploy_templates"

# allow list: only these paths are ever copied (DEP-003)
EXCLUDE_ANYWHERE = {"__pycache__", ".pytest_cache"}
ALWAYS_EXCLUDED_FILES = {"app/dev_loginless.py"}  # DEV-005: removed by the build, not by a runtime switch
DEMO_ONLY = {"app/demo", "app/simulator", "app/tools/demo_data.py", "app/services/demo_service.py"}


def version() -> str:
    text = (BACKEND / "app" / "__init__.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


def build_frontend() -> None:
    npm = shutil.which("npm") or "npm.cmd"
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)


def copy_tree(src: Path, dst: Path, *, rel_root: Path, skip: set[str]) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in sorted(src.iterdir()):
        if item.name in EXCLUDE_ANYWHERE or item.suffix == ".pyc":
            continue
        rel = item.relative_to(rel_root).as_posix()
        if rel in skip or rel in ALWAYS_EXCLUDED_FILES:
            continue
        target = dst / item.name
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            copy_tree(item, target, rel_root=rel_root, skip=skip)
        else:
            shutil.copy2(item, target)


def stage(out_dir: Path, package: str, profile: str) -> tuple[Path, str, str]:
    name = f"ArgusGrid-{version()}-{package}-{profile}"
    staging = out_dir / name
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "backend").mkdir(parents=True)
    skip = set() if package == "demo" else set(DEMO_ONLY)

    copy_tree(BACKEND / "app", staging / "backend" / "app", rel_root=BACKEND, skip=skip)
    # `app` was copied relative to BACKEND, so paths in `skip` start with "app/": fine.
    copy_tree(BACKEND / "migrations", staging / "backend" / "migrations", rel_root=BACKEND, skip=set())
    for name_ in ("alembic.ini", "requirements.txt"):
        shutil.copy2(BACKEND / name_, staging / "backend" / name_)

    dist = FRONTEND / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("frontend/dist is missing: run without --skip-build")
    copy_tree(dist, staging / "frontend" / "dist", rel_root=dist, skip=set())

    config = staging / "backend" / "config"
    config.mkdir(parents=True)
    template = (TEMPLATES / "app.env.template").read_text(encoding="utf-8").replace("__PROFILE__", profile)
    (config / "app.env.template").write_text(template, encoding="utf-8")

    for script in ("setup.bat", "setup.ps1", "start.bat", "start.ps1", "stop.bat", "stop.ps1"):
        shutil.copy2(TEMPLATES / script, staging / script)
    if package == "demo":
        # AG-D-70: only the demo package can install its own Python and PostgreSQL (pinned downloads)
        shutil.copy2(TEMPLATES / "bootstrap.ps1", staging / "bootstrap.ps1")
    (staging / "INSTALL.txt").write_text(install_text(package, profile), encoding="utf-8")

    # a fresh installation id for this package; the secret only goes to the console (OWN-005, OWN-006)
    installation_id = str(uuid.uuid4())
    identifier, secret = owner_tool.write_sealed(config / "owner.sealed", installation_id)
    return staging, identifier, secret


def install_text(package: str, profile: str) -> str:
    if package == "demo":
        return f"""ArgusGrid {version()} (demo package, profile {profile})

SK
1. Spustite setup.bat. Ak nezadáte -DatabaseUrl, setup stiahne a nainštaluje PostgreSQL 16 (asi 311 MB)
   do priečinka runtime\\ a podľa potreby vložený Python 3.12. Súbory pochádzajú z pevných adries a kontroluje sa
   ich SHA-256. Databáza počúva iba na 127.0.0.1. Bez siete: súbory vložte do runtime\\cache alebo zadajte
   -LocalCache <priečinok>. Voľby: -CheckOnly, -DryRun, -AssumeYes, -WithDemo, -DatabaseUrl <url>, -EmbeddedPython.
   Po úspešnom dokončení sa setup.bat a setup.ps1 sám vymaže.
2. Spustite start.bat (spustí aj databázu v tomto priečinku). Prihláste sa ako sysadmin, heslo sa musí hneď zmeniť.
3. Zastavenie: stop.bat zastaví aplikáciu aj databázu z tohto priečinka (-KeepDatabase ju ponechá bežať).
   Externá databáza sa nikdy nezastavuje. Vymazanie: stop.bat a potom zmažte celý priečinok.

EN
1. Run setup.bat. Without -DatabaseUrl the setup downloads and installs PostgreSQL 16 (about 311 MB) into
   runtime\\ and, when needed, an embedded Python 3.12. The files come from fixed addresses and are checked against
   pinned SHA-256 values. The database listens on 127.0.0.1 only. Offline: put the files into runtime\\cache or
   give -LocalCache <folder>. Options: -CheckOnly, -DryRun, -AssumeYes, -WithDemo, -DatabaseUrl <url>,
   -EmbeddedPython. After a fully successful run setup.bat and setup.ps1 delete themselves.
2. Run start.bat (it also starts the database of this folder). Sign in as sysadmin; change the password at once.
3. Stop with stop.bat: it stops the application and the database of this folder (-KeepDatabase leaves it running).
   An external database is never stopped. To remove: stop.bat, then delete the whole folder.

Configuration: backend\\config\\app.env (ARGUS_PROFILE civil | defense, ARGUS_BIND_HOST, ARGUS_SECURE_COOKIES).
"""
    return f"""ArgusGrid {version()} ({package} package, profile {profile})

SK
1. Pripravte PostgreSQL 16, prázdnu databázu a rolu pre ňu.
2. Spustite setup.bat (voľby: -CheckOnly, -DryRun, -AssumeYes, -DatabaseUrl <url>{', -WithDemo' if package == 'demo' else ''}).
   Setup vytvorí prostredie, pripraví databázu a vytvorí počiatočného administrátora s náhodným heslom.
   Po úspešnom dokončení sa setup.bat a setup.ps1 sám vymaže.
3. Spustite start.bat. Prihláste sa ako sysadmin, heslo sa musí hneď zmeniť.
4. Zastavenie: stop.bat. Databázový server sa nikdy nezastavuje.

EN
1. Prepare PostgreSQL 16 with an empty database and a role for it.
2. Run setup.bat (options: -CheckOnly, -DryRun, -AssumeYes, -DatabaseUrl <url>{', -WithDemo' if package == 'demo' else ''}).
   It creates the environment, prepares the database and creates the initial administrator with a random
   password. After a fully successful run setup.bat and setup.ps1 delete themselves.
3. Run start.bat. Sign in as sysadmin; the password must be changed immediately.
4. Stop with stop.bat. The database server is never stopped.

Configuration: backend\\config\\app.env (ARGUS_PROFILE civil | defense, ARGUS_BIND_HOST, ARGUS_SECURE_COOKIES).
"""


def zip_tree(staging: Path, archive: Path) -> str:
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                z.write(path, Path(staging.name) / path.relative_to(staging))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--package", choices=["production", "demo"], default="production")
    parser.add_argument("--profile", choices=["civil", "defense"], default="civil")
    parser.add_argument("--out", default=str(ROOT / "dist"))
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--print-owner", action="store_true",
                        help="print the owner identifier and secret (default: print them, this flag is kept for scripts)")
    args = parser.parse_args(argv)

    if not args.skip_build:
        build_frontend()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    staging, identifier, secret = stage(out_dir, args.package, args.profile)

    findings = secret_scan.scan_tree(staging)
    if findings:
        print(f"Publish scan: {len(findings)} finding(s). The package was NOT zipped.")
        for f in findings:
            print("  " + str(f))
        return 2
    print("Publish scan: clean.")

    archive = out_dir / f"{staging.name}.zip"
    digest = zip_tree(staging, archive)
    count = sum(1 for p in staging.rglob("*") if p.is_file())
    print(f"Package: {archive}  ({count} files, sha256 {digest[:16]}...)")
    print("Emergency Owner envelope - write it down NOW, it is not stored anywhere:")
    print(f"  identifier: {identifier}")
    print(f"  secret:     {secret}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
