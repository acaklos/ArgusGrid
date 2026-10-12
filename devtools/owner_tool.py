"""DEVELOPMENT ONLY: generate the sealed credential file of the Emergency Owner (OWN-006).

This tool is excluded from every deploy and publish package (DEP-010). It prints the identifier and the
secret ONCE, for the envelope kept in the owner's safe. The sealed file holds only a verifier.

Usage (repository root):
    .venv\\Scripts\\python.exe devtools\\owner_tool.py            # use the installation id of the dev database
    .venv\\Scripts\\python.exe devtools\\owner_tool.py --new-installation   # fresh id (for a new package)
"""
from __future__ import annotations

import argparse
import base64
import json
import secrets
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.security import hash_password  # noqa: E402
from app.services.owner_service import SEAL_VERSION, identifier_digest, seal_checksum  # noqa: E402

_ALPHABET = "abcdefghijkmnopqrstuvwxyz23456789"


def build_sealed(installation_id: str) -> tuple[dict[str, object], str, str]:
    """Return (sealed file content, identifier, secret). The secret is only returned, never stored."""
    identifier = "o-" + "".join(secrets.choice(_ALPHABET) for _ in range(10))
    secret = secrets.token_urlsafe(24)
    id_digest = identifier_digest(installation_id, identifier)
    verifier = hash_password(secret)
    sealed = {
        "version": SEAL_VERSION,
        "installation_id": installation_id,
        "identifier_digest": id_digest,
        "verifier": verifier,
        "checksum": seal_checksum(installation_id, id_digest, verifier),
    }
    return sealed, identifier, secret


def write_sealed(path: Path, installation_id: str) -> tuple[str, str]:
    sealed, identifier, secret = build_sealed(installation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    return identifier, secret


def _database_installation_id() -> str | None:
    from app.core.config import load_config
    from app.core.db import Database
    from app.services.owner_service import INSTALLATION_KEY
    from sqlalchemy import text

    try:
        db = Database(load_config().database_url)
        with db.session() as session:
            row = session.execute(
                text("SELECT value->>'id' FROM app_settings WHERE key = :k"), {"k": INSTALLATION_KEY}
            ).first()
        db.dispose()
        return row[0] if row and row[0] else None
    except Exception:  # the database may not exist yet
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", default=str(ROOT / "backend" / "config"))
    parser.add_argument("--new-installation", action="store_true")
    parser.add_argument("--force", action="store_true", help="overwrite an existing sealed file")
    args = parser.parse_args()

    target = Path(args.config_dir) / "owner.sealed"
    if target.exists() and not args.force:
        print(f"{target} already exists. Use --force to regenerate (the old envelope becomes invalid).")
        return 1
    installation_id = None if args.new_installation else _database_installation_id()
    installation_id = installation_id or str(uuid.uuid4())
    identifier, secret = write_sealed(target, installation_id)
    print(f"Sealed file written: {target}")
    print(f"Installation: {installation_id}")
    print("Write these on the envelope NOW. They are not stored anywhere:")
    print(f"  identifier: {identifier}")
    print(f"  secret:     {secret}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
