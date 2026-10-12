"""Development SMTP sink: accepts any message and stores it as an .eml file. For the browser tests only.

Usage: python devtools/smtp_sink.py --port 1025 --out <directory>
"""
from __future__ import annotations

import argparse
import itertools
import signal
import sys
import time
from pathlib import Path

from aiosmtpd.controller import Controller


class Store:
    def __init__(self, out: Path) -> None:
        self._out = out
        self._counter = itertools.count(1)
        out.mkdir(parents=True, exist_ok=True)

    async def handle_DATA(self, server, session, envelope):  # type: ignore[no-untyped-def]
        name = f"{next(self._counter):04d}.eml"
        header = f"X-Envelope-To: {', '.join(envelope.rcpt_tos)}\r\n".encode("ascii", "replace")
        (self._out / name).write_bytes(header + envelope.content)
        return "250 Message accepted"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=1025)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    controller = Controller(Store(Path(args.out)), hostname="127.0.0.1", port=args.port)
    controller.start()
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
    try:
        while not stop["now"]:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
