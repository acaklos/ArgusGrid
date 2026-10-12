"""Publish security scan for a deploy package (DEP-020 to DEP-022, DEV-006).

Scans a directory tree for secrets and for items that must never be in a package. A hit stops the publish.
Usage:  python -I devtools/secret_scan.py <directory>      (exit code 0 = clean, 2 = findings)
Used by devtools/make_deploy.py and tested by backend/tests/test_deploy_scan.py.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# -- deny list (DEP-010 to DEP-014, DEV-005) -----------------------------------------------------------
DENIED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".devtools", "tests", "e2e", "devtools",
               ".pytest_cache", "results"}
DENIED_NAMES = {"owner_tool.py", "dev_loginless.py", "accounts.txt", "secret.key", "database.url", ".env",
                "id_rsa", "id_ed25519"}
DENIED_SUFFIXES = {".log", ".pem", ".pfx", ".p12", ".key", ".pyc", ".sqlite", ".db", ".cred", ".bak", ".map"}
# strings that mean development-only code or a development-only flag is inside the package (DEV-006)
DENIED_TEXT = ("LOGINLESS DEV MODE", "ARGUS_DEV_LOGINLESS")
OWNER_FILE = "owner.sealed"

TEXT_SUFFIXES = {".py", ".js", ".json", ".html", ".css", ".txt", ".md", ".ini", ".cfg", ".toml", ".yml", ".yaml",
                 ".bat", ".ps1", ".sh", ".env", ".template", ".mako", ".csv", ".svg", ".xml", ".conf", ""}
MAX_BYTES = 6_000_000

# -- secret patterns (DEP-020) ------------------------------------------------------------------------
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY")
URL_CREDENTIALS = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@'\"<>]+:([^\s/@'\"<>]{3,})@[^\s'\"<>]+", re.I)
AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
TOKEN_LITERAL = re.compile(r"\b(?:ghp|gho|ghs|xox[abprs]|sk-[A-Za-z0-9]{8})[-_A-Za-z0-9]{20,}")
ASSIGNED_SECRET = re.compile(
    r"""(?ix)\b(?P<name>[a-z0-9_.-]*(?:password|passwd|secret|api[_-]?key|token|private[_-]?key)[a-z0-9_.-]*)
        \s*[:=]\s*(?P<q>["'])(?P<value>[^"'\n]{10,})(?P=q)""")
# values that are placeholders, examples or obvious non-secrets
PLACEHOLDER = re.compile(
    r"(?i)(change[-_ ]?me|example|placeholder|your[-_ ]|<[^>]+>|\{\{|\$\{|%\(|xxxx|\*{4}|none|null|true|false|"
    r"password|secret|token|test|dummy|sample|\.\.\.|replace|generated|random|hidden|redacted|csrf)")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    detail: str
    action: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{where}  [{self.kind}] {self.detail}  -> {self.action}"


def _is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= MAX_BYTES


def check_owner_file(path: Path, rel: str) -> list[Finding]:
    """The one allowed exception (DEP-022): a sealed verifier, no plaintext, an installation id of its own."""
    out: list[Finding] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [Finding(rel, 0, "owner_file", "not valid JSON", "regenerate with the owner tool")]
    allowed = {"version", "installation_id", "identifier_digest", "verifier", "checksum"}
    extra = set(data) - allowed
    if extra:
        out.append(Finding(rel, 0, "owner_file", f"unexpected fields {sorted(extra)}", "regenerate"))
    if not str(data.get("verifier", "")).startswith("$argon2"):
        out.append(Finding(rel, 0, "owner_file", "verifier is not an Argon2 hash", "regenerate"))
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                        str(data.get("installation_id", ""))):
        out.append(Finding(rel, 0, "owner_file", "installation id missing or malformed", "regenerate"))
    return out


def scan_file(path: Path, rel: str) -> list[Finding]:
    out: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return out
    for number, line in enumerate(text.splitlines(), 1):
        if len(line) > 4000:  # minified bundles: checked only for the denied strings below
            continue
        if PRIVATE_KEY.search(line):
            out.append(Finding(rel, number, "private_key", "private key block", "remove the key from the package"))
        match = URL_CREDENTIALS.search(line)
        if match and not PLACEHOLDER.search(match.group(1)):
            out.append(Finding(rel, number, "url_credentials", "connection string with a password",
                               "use the setup script to create it on the target"))
        if AWS_KEY.search(line) or TOKEN_LITERAL.search(line):
            out.append(Finding(rel, number, "token", "access token literal", "revoke the token and remove it"))
        for m in ASSIGNED_SECRET.finditer(line):
            value = m.group("value")
            if PLACEHOLDER.search(value) or " " in value.strip():
                continue
            out.append(Finding(rel, number, "assigned_secret", f"{m.group('name')} has a literal value",
                               "load it from the environment or a key file"))
    for needle in DENIED_TEXT:
        if needle in text:
            line = next((i for i, row in enumerate(text.splitlines(), 1) if needle in row), 0)
            out.append(Finding(rel, line, "dev_only", f"development-only string {needle!r}",
                               "remove the loginless code path from the package (DEV-005)"))
    return out


def scan_tree(root: Path, *, expect_owner_file: bool = True) -> list[Finding]:
    findings: list[Finding] = []
    root = root.resolve()
    owner_seen = False
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        parts = rel.split("/")
        if path.is_dir():
            if path.name in DENIED_DIRS:
                findings.append(Finding(rel, 0, "denied_dir", f"{path.name} must not be packaged", "exclude it"))
            continue
        if any(p in DENIED_DIRS for p in parts[:-1]):
            continue  # reported once at the directory
        if path.name == OWNER_FILE:
            owner_seen = True
            findings.extend(check_owner_file(path, rel))
            continue
        if path.name in DENIED_NAMES or path.suffix.lower() in DENIED_SUFFIXES or path.name.startswith(".env"):
            findings.append(Finding(rel, 0, "denied_file", f"{path.name} must not be packaged", "exclude it"))
            continue
        if _is_text(path):
            findings.extend(scan_file(path, rel))
    if expect_owner_file and not owner_seen:
        findings.append(Finding(OWNER_FILE, 0, "owner_file", "sealed owner file is missing",
                                "generate it with the owner tool (the package builds it)"))
    return findings


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    optional_owner = "--no-owner-file" in args
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        print(__doc__)
        return 1
    findings = scan_tree(Path(paths[0]), expect_owner_file=not optional_owner)
    if not findings:
        print("Publish scan: clean.")
        return 0
    print(f"Publish scan: {len(findings)} finding(s). The package must not be published.")
    for f in findings:
        print("  " + str(f))
    return 2


if __name__ == "__main__":
    sys.exit(main())
