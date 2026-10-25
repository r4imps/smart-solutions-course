"""Real mg400-base HTTP server on top of its own ``tests/fake_mg400.py``.

No robot is involved: the fake serves the MG400 TCP ports on localhost. The
mg400-base checkout comes from ``MG400_BASE_DIR`` (default: a sibling
``mg400-base`` folder next to this repo). The lab runs Denys's fork with the
lab-jog (joint guard, /api/check) and API-mode-switch changes.

Manual end-to-end run (three shells, no robot):
    python tests/mg400_base_fake.py --port 8000
    python ../lab1/src/station.py --execute --calibration <fake calibration>
    python -m src.station_adapter --port <Atom port> --executor lab1
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import threading


def mg400_base_dir() -> Path:
    default = Path(__file__).resolve().parents[4] / "mg400-base"
    return Path(os.environ.get("MG400_BASE_DIR", default))


class FakeMG400Base:
    """Fake robot + mg400-base server, connected and enabled like an operator
    would do it in the room (Connect, Enable). Tests only."""

    def __init__(self, port: int = 0, *, z_floor: float = -72.0) -> None:
        base = mg400_base_dir()
        for path in (base, base / "tests"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from fake_mg400 import FakeMG400
        from mg400 import server
        from mg400.driver import DobotMG400
        from werkzeug.serving import make_server

        self.fake = FakeMG400()
        fake = self.fake

        class Robot(DobotMG400):  # the server's robot, pointed at the fake
            def __init__(self, ip):
                super().__init__(ip, command_timeout=0.5, ports=fake.ports,
                                 settings_port=fake.settings_port)

        self.server = server
        self._real_robot = server.DobotMG400
        server.DobotMG400 = Robot
        server.configure(z_floor=z_floor)
        self.http = make_server("127.0.0.1", port, server.app, threaded=True)
        self.url = f"http://127.0.0.1:{self.http.server_port}"
        self._thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self._thread.start()
        self.api = server.app.test_client()

    def connect_and_enable(self) -> None:
        assert self.api.post("/api/connect", json={"ip": "127.0.0.1"}).get_json()["ok"]
        assert self.api.post("/api/enable", json={}).get_json()["ok"]

    def close(self) -> None:
        self.api.post("/api/disconnect", json={})
        self.http.shutdown()
        self.server.DobotMG400 = self._real_robot
        self.server._speed_ratio = 10
        self.fake.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--z-floor", type=float, default=-72.0)
    args = parser.parse_args()
    fake = FakeMG400Base(args.port, z_floor=args.z_floor)
    fake.connect_and_enable()
    print(f"fake MG400 + mg400-base on {fake.url} (connected, enabled); Ctrl+C stops")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        fake.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
