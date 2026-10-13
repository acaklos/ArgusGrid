"""Publish scan and package generator (DEP-001..DEP-022, DEV-005, DEV-006)."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "devtools"))

import make_deploy  # noqa: E402
import owner_tool  # noqa: E402
import secret_scan  # noqa: E402


def sealed(root: Path) -> None:
    owner_tool.write_sealed(root / "backend" / "config" / "owner.sealed", str(uuid.uuid4()))


def kinds(root: Path) -> set[str]:
    return {f.kind for f in secret_scan.scan_tree(root)}


@pytest.fixture()
def pkg(tmp_path: Path) -> Path:
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "main.py").write_text("PORT = 8000\n", encoding="utf-8")
    sealed(tmp_path)
    return tmp_path


def test_a_clean_package_passes_with_its_sealed_owner_file(pkg: Path):
    assert secret_scan.scan_tree(pkg) == []


@pytest.mark.parametrize("name", [".env", "accounts.txt", "secret.key", "database.url", "owner_tool.py",
                                  "dev_loginless.py", "server.log", "id_rsa"])
def test_denied_files_stop_the_publish(pkg: Path, name: str):
    (pkg / "backend" / name).write_text("x", encoding="utf-8")
    assert "denied_file" in kinds(pkg)


@pytest.mark.parametrize("directory", ["tests", ".venv", "node_modules", "__pycache__", ".git", "devtools"])
def test_denied_directories_stop_the_publish(pkg: Path, directory: str):
    (pkg / "backend" / directory).mkdir()
    assert "denied_dir" in kinds(pkg)


def test_private_keys_connection_strings_and_tokens_are_found(pkg: Path):
    f = pkg / "backend" / "app" / "settings.py"
    f.write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
    assert "private_key" in kinds(pkg)
    f.write_text('URL = "postgresql://argus:Zx9qLm27pRt@db.internal/argusgrid"\n', encoding="utf-8")
    assert "url_credentials" in kinds(pkg)
    f.write_text('KEY = "AKIAABCDEFGHIJKLMNOP"\n', encoding="utf-8")
    assert "token" in kinds(pkg)
    f.write_text('smtp_password = "Tr0ub4dor&3xyz"\n', encoding="utf-8")
    assert "assigned_secret" in kinds(pkg)


def test_placeholders_and_code_that_only_names_a_secret_are_not_findings(pkg: Path):
    (pkg / "backend" / "app" / "ok.py").write_text(
        'URL = "postgresql+psycopg://argusgrid:<password>@localhost:5432/argusgrid"\n'
        'password: str = Field(max_length=128)\nsecret_label = "Password"\ntoken = request.headers["x"]\n'
        'EXAMPLE = "postgresql://user:changeme@localhost/db"\n', encoding="utf-8")
    assert secret_scan.scan_tree(pkg) == []


def test_loginless_flag_banner_and_module_are_denied(pkg: Path):
    (pkg / "backend" / "app" / "m.py").write_text('FLAG = "ARGUS_DEV_LOGINLESS"\n', encoding="utf-8")
    assert "dev_only" in kinds(pkg)
    (pkg / "backend" / "app" / "m.py").write_text('BANNER = "LOGINLESS DEV MODE"\n', encoding="utf-8")
    assert "dev_only" in kinds(pkg)


def test_the_sealed_file_is_the_only_exception_and_is_checked(pkg: Path):
    path = pkg / "backend" / "config" / "owner.sealed"
    data = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**data, "secret": "plain"}), encoding="utf-8")
    assert "owner_file" in kinds(pkg)
    path.write_text(json.dumps({**data, "verifier": "plaintext-secret"}), encoding="utf-8")
    assert "owner_file" in kinds(pkg)
    path.write_text("not json", encoding="utf-8")
    assert "owner_file" in kinds(pkg)
    path.unlink()
    assert "owner_file" in kinds(pkg)


def test_the_packaged_application_has_no_loginless_module_and_no_flag(tmp_path: Path):
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        pytest.skip("frontend/dist not built")
    staging, identifier, secret = make_deploy.stage(tmp_path, "production", "defense")
    assert secret_scan.scan_tree(staging) == []
    app = staging / "backend" / "app"
    assert not (app / "dev_loginless.py").exists()
    assert not (app / "demo").exists() and not (app / "simulator").exists()
    assert (staging / "setup.bat").is_file() and (staging / "backend" / "config" / "owner.sealed").is_file()
    assert "ARGUS_PROFILE=defense" in (staging / "backend" / "config" / "app.env.template").read_text("utf-8")
    # the secret is not written anywhere in the package
    assert not any(secret in p.read_text("utf-8", errors="ignore") for p in staging.rglob("*") if p.is_file()
                   and p.suffix in {".txt", ".json", ".py", ".ps1", ".bat", ".template", ".sealed"})
    assert len(identifier) > 8


def test_the_demo_package_keeps_the_demo_code_and_still_has_no_loginless(tmp_path: Path):
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        pytest.skip("frontend/dist not built")
    staging, _id, _secret = make_deploy.stage(tmp_path, "demo", "civil")
    app = staging / "backend" / "app"
    assert (app / "demo" / "krec.py").is_file() and (app / "tools" / "demo_data.py").is_file()
    assert not (app / "dev_loginless.py").exists()
    assert secret_scan.scan_tree(staging) == []


BOOTSTRAP = ROOT / "devtools" / "deploy_templates" / "bootstrap.ps1"
SCRIPTS = ("setup.ps1", "start.ps1", "stop.ps1", "bootstrap.ps1")


def _powershell(command: str) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("powershell")
    if exe is None:
        pytest.skip("Windows PowerShell is not available")
    return subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True,
                          text=True, timeout=120)


def test_only_the_demo_package_carries_the_bootstrap_script(tmp_path: Path):
    """AG-D-70: the production package never installs tools; the operator provides Python and PostgreSQL."""
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        pytest.skip("frontend/dist not built")
    demo, _i, _s = make_deploy.stage(tmp_path / "d", "demo", "civil")
    prod, _i, _s = make_deploy.stage(tmp_path / "p", "production", "civil")
    assert (demo / "bootstrap.ps1").is_file() and not (prod / "bootstrap.ps1").exists()
    assert secret_scan.scan_tree(demo) == []
    assert "311 MB" in (demo / "INSTALL.txt").read_text("utf-8")
    assert "311 MB" not in (prod / "INSTALL.txt").read_text("utf-8")


def test_the_pinned_downloads_are_complete_fixed_https_addresses_with_a_checksum():
    text = BOOTSTRAP.read_text("utf-8")
    pins = re.findall(r"File = '([^']+)'.*?Url = '([^']+)'.*?Sha256 = '([^']+)'", text, flags=re.S)
    assert {p[0].split("-")[0] for p in pins} == {"python", "pip", "postgresql"}
    hosts = set(re.search(r"AllowedHosts = @\(([^)]*)\)", text).group(1).replace("'", "").replace(" ", "").split(","))
    for file, url, digest in pins:
        assert re.fullmatch(r"[0-9a-f]{64}", digest), f"{file}: checksum is not set"
        assert url.startswith("https://") and url.endswith("/" + file)
        assert url.split("/")[2] in hosts
    assert "__" not in "".join(p[2] for p in pins)


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell scripts of the Windows package")
def test_the_package_scripts_parse():
    names = ", ".join(f"'{ROOT / 'devtools' / 'deploy_templates' / n}'" for n in SCRIPTS)
    command = (f"foreach ($f in @({names})) {{ $e = $null; [void][System.Management.Automation.Language.Parser]"
               "::ParseFile($f, [ref]$null, [ref]$e); if ($e) { $e | ForEach-Object { $f + ': ' + $_.Message }; exit 1 } }")
    r = _powershell(command)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell scripts of the Windows package")
def test_the_checksum_check_accepts_the_exact_file_only(tmp_path: Path):
    good = tmp_path / "good.bin"
    good.write_bytes(b"argusgrid")
    digest = hashlib.sha256(b"argusgrid").hexdigest()
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"argusgrid!")
    command = (f". '{BOOTSTRAP}'; "
               f"$a = Test-Sha256 '{good}' '{digest.upper()}'; $b = Test-Sha256 '{bad}' '{digest}'; "
               f"$c = Test-Sha256 '{tmp_path / 'missing.bin'}' '{digest}'; \"$a $b $c\"")
    r = _powershell(command)
    assert r.stdout.split() == ["True", "False", "False"], r.stdout + r.stderr


def test_distributed_documents_do_not_describe_recovery_owner_or_development_modes(tmp_path: Path):
    """DOC-020 to DOC-022: nothing about the owner credential, recovery tools or loginless mode ships."""
    forbidden = ("emergency", "owner", "loginless", "recovery", "reset tool")
    for package in ("production", "demo"):
        text = make_deploy.install_text(package, "civil").lower()
        assert not [w for w in forbidden if w in text], package
    manual_dir = ROOT / "docs" / "manual"
    for name in ("ArgusGrid-Pouzivatelska-prirucka.docx", "ArgusGrid-Instalacna-prirucka.docx"):
        path = manual_dir / name
        if not path.is_file():
            continue
        import zipfile

        with zipfile.ZipFile(path) as z:
            body = z.read("word/document.xml").decode("utf-8").lower()
        docs_forbidden = ("emergency", "loginless", "owner.sealed", "owner secret", "owner credential", "recovery")
        assert not [w for w in docs_forbidden if w in body], name
