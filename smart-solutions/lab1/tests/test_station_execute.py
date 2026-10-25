from __future__ import annotations

import csv
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

LAB1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB1_ROOT / "src"))

import station
from letter_paths import DEFAULT_LETTERS_PATH, load_letter_paths
from mg400_client import MG400Client, MG400Error
from test_robot_calibration import synthetic_document


def safe_status(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "connected": True,
        "enabled": True,
        "error": False,
        "fault_kind": None,
        "fault_label": None,
        "pose": [5.0, 6.0, 7.0, 8.0],
        "feedback_ok": True,
        "servo_active": True,
        "link_error": None,
        "servo_error": None,
        "stalled": False,
    }
    result.update(overrides)
    return result


class FakeMG400Client:
    instances: list["FakeMG400Client"] = []
    next_status: dict[str, object] = safe_status()
    trace: list[str] = []

    def __init__(self, base_url: str, *, network_timeout: float) -> None:
        self.base_url = base_url
        self.network_timeout = network_timeout
        self.status = dict(self.next_status)
        self.speed_calls: list[float] = []
        self.moves: list[tuple[float, float, float, float]] = []
        self.stop_calls = 0
        self.instances.append(self)

    def get_status(self) -> dict[str, object]:
        return dict(self.status)

    require_safe_status = staticmethod(MG400Client.require_safe_status)
    pose_from_status = staticmethod(MG400Client.pose_from_status)

    def set_speed(self, ratio: float) -> dict[str, object]:
        self.trace.append("speed")
        self.speed_calls.append(ratio)
        return {"ok": True}

    def move_and_wait(
        self,
        x: float,
        y: float,
        z: float,
        r: float,
        *,
        tolerance: float,
        timeout: float,
    ) -> dict[str, object]:
        self.trace.append("move")
        self.moves.append((x, y, z, r))
        self.status["pose"] = [x, y, z, r]
        return dict(self.status)

    unreachable: set[tuple[float, float, float]] = set()

    def check_pose(self, x: float, y: float, z: float) -> bool | None:
        self.trace.append("check")
        return (round(x, 2), round(y, 2), z) not in self.unreachable

    def stop(self) -> dict[str, object]:
        self.stop_calls += 1
        return {"ok": True}


class StationExecuteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.log_path = root / "letter_events.csv"
        self.calibration_path = root / "robot_calibration.json"
        self.calibration_path.write_text(
            json.dumps(synthetic_document()), encoding="utf-8"
        )
        station.CONFIG = station.Config(
            log_path=self.log_path,
            letters_path=DEFAULT_LETTERS_PATH,
            dry_run=False,
            calibration_path=self.calibration_path,
        )
        station.LETTER_PATHS = load_letter_paths(DEFAULT_LETTERS_PATH)
        station.LAST_SEQ.clear()
        station.EXECUTION_EVENTS.clear()
        FakeMG400Client.instances.clear()
        FakeMG400Client.next_status = safe_status()
        FakeMG400Client.trace.clear()
        station.MG400_CLIENT_FACTORY = FakeMG400Client
        self.addCleanup(self.restore_factory)

    @staticmethod
    def restore_factory() -> None:
        station.MG400_CLIENT_FACTORY = MG400Client

    @staticmethod
    def payload(
        letter: str, session: str = "execute", seq: int = 1
    ) -> dict[str, object]:
        return {"letter": letter, "session": session, "seq": seq, "atom_sent_ms": 100}

    def post(self, letter: str, session: str = "execute", seq: int = 1):
        return station.app.test_client().post(
            "/api/letter", json=self.payload(letter, session, seq)
        )

    def wait_for_worker(self) -> None:
        self.assertTrue(station.EXECUTION_LOCK.acquire(timeout=2))
        station.EXECUTION_LOCK.release()

    def test_happy_a_maps_xy_and_controls_pen_safely(self) -> None:
        clock_values = iter((111111, 123456))

        def clock() -> int:
            FakeMG400Client.trace.append("clock")
            return next(clock_values)

        with mock.patch.object(station, "monotonic_ns", side_effect=clock):
            response = self.post("A")
            self.wait_for_worker()

        self.assertEqual(response.status_code, 202)
        body = response.get_json()
        self.assertTrue(body["robot_started"])
        self.assertFalse(body["dry_run"])
        self.assertTrue(body["accepted"])
        self.assertEqual(body["execution_status"], "started")
        self.assertNotIn("robot_command_monotonic_ns", body)
        robot = FakeMG400Client.instances[0]
        self.assertEqual(robot.speed_calls, [20.0])
        self.assertEqual(
            FakeMG400Client.trace[:4], ["clock", "speed", "clock", "move"]
        )
        self.assertEqual(robot.moves[0], (5.0, 6.0, 30.0, 0.0))
        self.assertEqual(robot.moves[1], (20.0, 20.0, 30.0, 0.0))
        self.assertEqual(robot.moves[2], (20.0, 20.0, 25.0, 0.0))
        self.assertEqual(robot.moves[-1][2], 30.0)
        pen_up_before_second_stroke = robot.moves[5:7]
        self.assertEqual(
            [move[2] for move in pen_up_before_second_stroke], [30.0, 30.0]
        )

        with self.log_path.open(newline="", encoding="utf-8") as handle:
            row = list(csv.DictReader(handle))[0]
        self.assertEqual(row["robot_command_monotonic_ns"], "123456")
        self.assertEqual(row["status"], "executed")

    def test_incomplete_calibration_makes_no_api_call(self) -> None:
        document = synthetic_document()
        document["workspace"]["origin_x"] = None  # type: ignore[index]
        self.calibration_path.write_text(json.dumps(document), encoding="utf-8")
        response = self.post("A")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["robot_started"])
        self.assertEqual(FakeMG400Client.instances, [])

    def test_disabled_robot_makes_no_movement(self) -> None:
        FakeMG400Client.next_status = safe_status(enabled=False)
        response = self.post("A")
        self.assertEqual(response.status_code, 503)
        robot = FakeMG400Client.instances[0]
        self.assertEqual(robot.speed_calls, [])
        self.assertEqual(robot.moves, [])

    def test_same_event_can_retry_after_failed_preflight(self) -> None:
        FakeMG400Client.next_status = safe_status(enabled=False)
        first = self.post("A", session="retry-preflight", seq=1)
        self.assertEqual(first.status_code, 503)
        self.assertEqual(FakeMG400Client.instances[0].moves, [])

        FakeMG400Client.next_status = safe_status()
        second = self.post("A", session="retry-preflight", seq=1)

        self.assertEqual(second.status_code, 202)
        self.assertFalse(second.get_json()["duplicate"])
        self.assertTrue(second.get_json()["robot_started"])
        self.wait_for_worker()
        self.assertEqual(len(FakeMG400Client.instances), 2)
        self.assertTrue(FakeMG400Client.instances[1].moves)

    def test_fault_and_stall_make_no_movement(self) -> None:
        for seq, unsafe in enumerate(
            (safe_status(fault_label="alarm"), safe_status(stalled=True)), start=1
        ):
            with self.subTest(unsafe=unsafe):
                FakeMG400Client.next_status = unsafe
                response = self.post("A", session=f"unsafe-{seq}")
                self.assertEqual(response.status_code, 503)
                robot = FakeMG400Client.instances[-1]
                self.assertEqual(robot.speed_calls, [])
                self.assertEqual(robot.moves, [])

    def test_servo_inactive_makes_no_movement(self) -> None:
        FakeMG400Client.next_status = safe_status(servo_active=False)
        response = self.post("A")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["robot_started"])
        self.assertEqual(FakeMG400Client.instances[0].moves, [])

    def test_missing_path_makes_no_api_call(self) -> None:
        response = self.post("Z")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(FakeMG400Client.instances, [])

    def test_motion_error_stops_and_does_not_claim_success(self) -> None:
        def failed_move(*args: object, **kwargs: object) -> dict[str, object]:
            raise MG400Error("synthetic move failure")

        with mock.patch.object(FakeMG400Client, "move_and_wait", failed_move):
            response = self.post("A", session="move-error")
            self.wait_for_worker()

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.get_json()["ok"])
        self.assertTrue(response.get_json()["robot_started"])
        self.assertEqual(FakeMG400Client.instances[0].stop_calls, 1)

        retry = self.post("A", session="move-error")
        self.assertEqual(retry.status_code, 409)
        self.assertTrue(retry.get_json()["duplicate"])
        self.assertEqual(retry.get_json()["execution_status"], "failed")
        self.assertTrue(retry.get_json()["robot_started"])
        self.assertEqual(len(FakeMG400Client.instances), 1)

    def test_clamped_move_aborts_remaining_plan(self) -> None:
        def clamped_move(client: FakeMG400Client, *args: object, **kwargs: object) -> dict[str, object]:
            client.moves.append(tuple(args[:4]))
            raise MG400Error("MG400 target was clamped; drawing stopped")

        with mock.patch.object(FakeMG400Client, "move_and_wait", clamped_move):
            response = self.post("A", session="clamped")
            self.wait_for_worker()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(station.EXECUTION_EVENTS[("clamped", 1)].state, "failed")
        self.assertEqual(len(FakeMG400Client.instances[0].moves), 1)
        self.assertEqual(FakeMG400Client.instances[0].stop_calls, 1)

    def test_duplicate_is_not_executed_twice(self) -> None:
        first = self.post("L", session="same", seq=4)
        self.wait_for_worker()
        duplicate = self.post("L", session="same", seq=4)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.get_json()["duplicate"])
        self.assertEqual(duplicate.get_json()["execution_status"], "completed")
        self.assertEqual(len(FakeMG400Client.instances), 1)

    def test_simultaneous_new_event_returns_busy(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)
        original = FakeMG400Client.move_and_wait

        def blocking_move(client: FakeMG400Client, *args: object, **kwargs: object) -> dict[str, object]:
            entered.set()
            self.assertTrue(release.wait(timeout=2))
            return original(client, *args, **kwargs)

        with mock.patch.object(FakeMG400Client, "move_and_wait", blocking_move):
            first = self.post("A", "first", 1)
            self.assertEqual(first.status_code, 202)
            self.assertTrue(first.get_json()["accepted"])
            self.assertTrue(entered.wait(timeout=2))

            duplicate = self.post("A", "first", 1)
            self.assertIn(duplicate.status_code, (200, 202))
            self.assertTrue(duplicate.get_json()["duplicate"])
            self.assertEqual(duplicate.get_json()["execution_status"], "started")

            busy = self.post("L", "second", 1)
            release.set()
            self.wait_for_worker()

        self.assertEqual(busy.status_code, 409)
        self.assertFalse(busy.get_json()["robot_started"])
        self.assertEqual(len(FakeMG400Client.instances), 1)

    def test_letter_status_reports_lifecycle_read_only(self) -> None:
        client = station.app.test_client()
        url = "/api/letter/status?session=status&seq=3"
        self.assertEqual(client.get(url).status_code, 404)

        self.post("L", session="status", seq=3)
        self.wait_for_worker()
        moves = len(FakeMG400Client.instances[0].moves)
        body = client.get(url).get_json()
        self.assertEqual(body["execution_status"], "completed")
        self.assertIsNone(body["error"])
        self.assertFalse(body["dry_run"])
        # Reading the status never starts or repeats motion.
        client.get(url)
        self.assertEqual(len(FakeMG400Client.instances), 1)
        self.assertEqual(len(FakeMG400Client.instances[0].moves), moves)

        with mock.patch.object(
            FakeMG400Client, "move_and_wait",
            lambda *args, **kwargs: (_ for _ in ()).throw(MG400Error("synthetic")),
        ):
            self.post("L", session="status", seq=4)
            self.wait_for_worker()
        failed = client.get("/api/letter/status?session=status&seq=4").get_json()
        self.assertEqual(failed["execution_status"], "failed")
        self.assertIn("synthetic", failed["error"])
        self.assertEqual(client.get("/api/letter/status?session=status&seq=x").status_code, 400)
        self.assertEqual(client.get("/api/letter/status?seq=1").status_code, 400)

    def test_ack_does_not_wait_for_slow_drawing(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)
        original = FakeMG400Client.move_and_wait

        def blocking_move(client: FakeMG400Client, *args: object, **kwargs: object) -> dict[str, object]:
            entered.set()
            self.assertTrue(release.wait(timeout=2))
            return original(client, *args, **kwargs)

        with mock.patch.object(FakeMG400Client, "move_and_wait", blocking_move):
            response = self.post("A", session="slow")
            self.assertEqual(response.status_code, 202)
            self.assertTrue(entered.wait(timeout=2))
            self.assertFalse(release.is_set())
            self.assertEqual(station.EXECUTION_EVENTS[("slow", 1)].state, "started")
            release.set()
            self.wait_for_worker()


if __name__ == "__main__":
    unittest.main()
