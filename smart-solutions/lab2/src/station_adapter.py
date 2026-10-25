"""Atom serial message -> validated high-level executor -> Atom result."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .executor import (
    Lab1LetterCatalog,
    LetterExecutor,
    MockLetterExecutor,
    MockPickPlaceExecutor,
    PickPlaceExecutor,
)
from .lab1_station_executor import (
    DEFAULT_LAB1_URL,
    DEFAULT_WAIT_SECONDS,
    Lab1StationLetterExecutor,
)
from .models import (
    AtomLetterJob,
    MessageValidationError,
    StationResult,
    parse_atom_message,
    parse_json_line,
)
from .pick_place_preflight import PickPlacePreflightExecutor
from .serial_transport import run_serial_forever
from .station_store import StationJobStore


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "station_jobs.sqlite3"


class StationAdapter:
    def __init__(
        self,
        store: StationJobStore,
        *,
        executor: LetterExecutor | None = None,
        pick_place_executor: PickPlaceExecutor | None = None,
        catalog: Lab1LetterCatalog | None = None,
        local_execution_enabled: bool = False,
    ) -> None:
        self.store = store
        self.executor = executor or MockLetterExecutor()
        self.pick_place_executor = pick_place_executor or MockPickPlaceExecutor()
        self.catalog = catalog or Lab1LetterCatalog()
        self.local_execution_enabled = local_execution_enabled

    def handle_line(self, line: str | bytes) -> str:
        try:
            payload, _ = parse_json_line(line)
            job = parse_atom_message(payload)
        except MessageValidationError as error:
            return StationResult(error.job_id, "refused", error.reason).to_json_line()

        decision = self.store.claim(job)
        if decision.action != "execute":
            assert decision.result is not None
            return decision.result.to_json_line()

        if not self.local_execution_enabled:
            result = StationResult(job.job_id, "refused", "robot_not_enabled")
        elif isinstance(job, AtomLetterJob):
            if not self.executor.ready:
                result = StationResult(job.job_id, "refused", "robot_not_enabled")
            elif not self.catalog.supports(job.letter):
                result = StationResult(job.job_id, "refused", "invalid_letter")
            else:
                try:
                    outcome = self.executor.execute_letter(
                        job.letter,
                        job.job_id,
                        session=job.session,
                        seq=job.seq,
                        atom_sent_ms=job.atom_sent_ms,
                    )
                    result = StationResult(job.job_id, outcome.status, outcome.reason)
                except Exception:
                    result = StationResult(job.job_id, "refused", "execution_failed")
        else:
            if not self.pick_place_executor.ready:
                result = StationResult(job.job_id, "refused", "robot_not_enabled")
            else:
                try:
                    outcome = self.pick_place_executor.execute_pick_place(
                        job.routine,
                        job.job_id,
                        session=job.session,
                        seq=job.seq,
                        atom_sent_ms=job.atom_sent_ms,
                    )
                    result = StationResult(job.job_id, outcome.status, outcome.reason)
                except Exception:
                    result = StationResult(job.job_id, "refused", "execution_failed")

        self.store.finish(result)
        return result.to_json_line()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Atom USB port, for example COM4")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--database", default=str(DEFAULT_DB))
    parser.add_argument(
        "--allow-mock-jobs",
        action="store_true",
        help="allow only the software mock executor; this never enables MG400",
    )
    parser.add_argument(
        "--executor",
        choices=("mock", "lab1"),
        default="mock",
        help="lab1 forwards letter jobs to the running Lab 1 station (default: mock)",
    )
    parser.add_argument("--lab1-url", default=DEFAULT_LAB1_URL)
    parser.add_argument(
        "--lab1-wait",
        type=float,
        default=DEFAULT_WAIT_SECONDS,
        help="seconds to wait for Lab 1 to report completed or failed",
    )
    args = parser.parse_args(argv)
    if args.executor == "lab1" and args.allow_mock_jobs:
        parser.error("--allow-mock-jobs is for the mock executor only")
    return args


def build_adapter(args: argparse.Namespace) -> StationAdapter:
    store = StationJobStore(args.database)
    if args.executor != "lab1":
        return StationAdapter(
            store,
            executor=MockLetterExecutor(),
            local_execution_enabled=args.allow_mock_jobs,
        )
    # Lab 1 moves the MG400; pick_place has no live executor and its preflight
    # refuses, so the mock can never report a fake "done" next to the robot.
    return StationAdapter(
        store,
        executor=Lab1StationLetterExecutor(args.lab1_url, wait_seconds=args.lab1_wait),
        pick_place_executor=PickPlacePreflightExecutor(),
        local_execution_enabled=True,
    )


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    adapter = build_adapter(args)
    run_serial_forever(args.port, args.baud, adapter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
