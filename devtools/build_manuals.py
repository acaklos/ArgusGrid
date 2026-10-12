"""Build the Slovak manuals (.docx) from docs/manual/screens (DOC-002, DOC-003).

Usage (repository root):  .venv\\Scripts\\python.exe -I devtools\\build_manuals.py
Output: docs/manual/ArgusGrid-Pouzivatelska-prirucka.docx and ArgusGrid-Instalacna-prirucka.docx
The screenshots come from devtools/manual_screens.py (clean install, demo data, normal login).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "devtools"))

from manuals import install, user  # noqa: E402

SCREENS = ROOT / "docs" / "manual" / "screens"
OUT = ROOT / "docs" / "manual"


def main() -> int:
    missing = [n for n in ("01-prihlasenie", "04-operatorsky-panel", "25-mobil-graf") if not (SCREENS / f"{n}.png").is_file()]
    if missing:
        print("Screenshots are missing, run devtools/manual_screens.py first:", ", ".join(missing))
        return 1
    user.build(SCREENS, OUT / "ArgusGrid-Pouzivatelska-prirucka.docx")
    install.build(SCREENS, OUT / "ArgusGrid-Instalacna-prirucka.docx")
    for f in sorted(OUT.glob("*.docx")):
        print(f"{f.name}: {f.stat().st_size // 1024} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
