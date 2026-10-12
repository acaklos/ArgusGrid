"""The runtime requirements list every third-party module the application imports (found by the clean-install
proof: httpx was installed in the development environment only)."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
# import name -> distribution name in requirements.txt
DISTRIBUTION = {"argon2": "argon2-cffi", "yaml": "pyyaml", "psycopg": "psycopg"}


def imported_modules() -> set[str]:
    found: set[str] = set()
    for folder in ("app", "migrations"):
        for path in (BACKEND / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    found |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
    return {m for m in found if m not in sys.stdlib_module_names and m != "app"}


def declared() -> set[str]:
    names = set()
    for line in (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)", line.strip())
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def test_every_third_party_import_is_a_runtime_requirement():
    have = declared()
    missing = sorted(m for m in imported_modules() if DISTRIBUTION.get(m, m).lower() not in have)
    assert missing == []
