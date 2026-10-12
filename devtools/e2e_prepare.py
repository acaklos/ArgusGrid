"""Browser-test preparation: the suite signs in many times within a minute from one address, so the
per-address login throttle (a real protection, tested elsewhere) is raised for the test database only."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.clock import Clock  # noqa: E402
from app.core.config import load_config  # noqa: E402
from app.core.db import Database  # noqa: E402
from app.services.container import Services  # noqa: E402


def main() -> int:
    config = load_config()
    db = Database(config.database_url)
    with db.transaction() as session:
        services = Services(session, Clock(), config)
        settings = services.lockout_settings.get().to_dict()
        settings["source_throttle_per_minute"] = 1000
        services.store.put("lockout_policy", settings)
    db.dispose()
    print("throttle raised for the test database")
    return 0


if __name__ == "__main__":
    sys.exit(main())
