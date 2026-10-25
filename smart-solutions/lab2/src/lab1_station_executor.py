"""Forward a whitelisted ``letter`` job to the running Lab 1 station.

The Lab 1 station (``lab1/src/station.py --execute``) stays the only program
that moves the MG400: it owns the calibration, speed, reach/Z checks, the
mg400-base safety gate and the stop on error. This module sends no motion
command and imports no MG400 client. It posts the Atom letter to Lab 1
``POST /api/letter`` and waits on the read-only
``GET /api/letter/status`` until the drawing is completed or failed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json
import logging
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from .executor import ExecutionOutcome


LOGGER = logging.getLogger(__name__)

DEFAULT_LAB1_URL = "http://127.0.0.1:5000"
# Nominal, not measured: long enough for one letter at 2 % speed (Lab 1 moves
# at ~4 mm/s there). Waiting longer only delays the result; Lab 1 has its own
# per-move timeouts and stops the arm itself.
DEFAULT_WAIT_SECONDS = 600.0

Reply = tuple[int, dict[str, Any]]
Transport = Callable[[str, str, "dict | None"], Reply]


class Lab1Unreachable(RuntimeError):
    """No HTTP answer from the Lab 1 station."""


def urllib_transport(base_url: str, timeout: float) -> Transport:
    base = base_url.rstrip("/")

    def send(method: str, path: str, body: dict | None) -> Reply:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            base + path, data=data, method=method,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        except OSError as error:
            raise Lab1Unreachable(f"{method} {path}: {error}") from error
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            payload = None
        return status, payload if isinstance(payload, dict) else {}

    return send


@dataclass
class ForwardReport:
    """Local diagnostics for the operator; never sent over the wire."""

    job_id: str
    letter: str
    stage: str = "health"
    detail: str | None = None
    lab1_status: str | None = None
    polls: int = 0
    log: list[str] = field(default_factory=list)


class Lab1StationLetterExecutor:
    """Letter executor that hands the job to Lab 1 and reports its outcome."""

    def __init__(
        self,
        base_url: str = DEFAULT_LAB1_URL,
        *,
        network_timeout: float = 2.0,
        wait_seconds: float = DEFAULT_WAIT_SECONDS,
        poll_interval: float = 0.5,
        transport: Transport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if network_timeout <= 0 or wait_seconds <= 0 or poll_interval <= 0:
            raise ValueError("timeouts and poll interval must be positive")
        self.base_url = base_url
        self.wait_seconds = wait_seconds
        self.poll_interval = poll_interval
        self._send = transport or urllib_transport(base_url, network_timeout)
        self._monotonic = monotonic
        self._sleep = sleep
        self.last_report: ForwardReport | None = None

    @property
    def ready(self) -> bool:
        # Lab 1 /health is checked again before every job.
        return True

    def execute_letter(
        self,
        letter: str,
        job_id: str,
        *,
        session: str,
        seq: int,
        atom_sent_ms: int | None,
    ) -> ExecutionOutcome:
        report = ForwardReport(job_id, letter)
        self.last_report = report
        outcome = self._forward(report, letter, session, seq, atom_sent_ms)
        if outcome.status != "done":
            LOGGER.warning("letter %s (%s) refused: %s [%s] %s", letter, job_id,
                           outcome.reason, report.stage, report.detail)
        return outcome

    def _forward(self, report, letter, session, seq, atom_sent_ms) -> ExecutionOutcome:
        try:
            status, health = self._send("GET", "/health", None)
        except Lab1Unreachable as error:
            report.detail = f"Lab 1 station unreachable: {error}"
            return ExecutionOutcome.refused("robot_not_enabled")
        if status != 200 or health.get("execution_mode") != "execute":
            # A dry-run Lab 1 would accept the letter without drawing it.
            report.detail = f"Lab 1 is not in execute mode ({health.get('execution_mode')})"
            return ExecutionOutcome.refused("robot_not_enabled")

        report.stage = "submit"
        body = {"letter": letter, "session": session, "seq": seq}
        if atom_sent_ms is not None:
            body["atom_sent_ms"] = atom_sent_ms
        try:
            status, reply = self._send("POST", "/api/letter", body)
        except Lab1Unreachable as error:
            # The POST may or may not have arrived; the status record decides.
            report.detail = f"no reply to POST /api/letter: {error}"
            return self._wait(report, session, seq, unknown_means_refused=True)

        report.lab1_status = reply.get("execution_status")
        report.detail = reply.get("error")
        state = reply.get("execution_status")
        if status in (200, 202) and state in ("started", "preflight"):
            return self._wait(report, session, seq)
        if status == 200 and state == "completed":
            return ExecutionOutcome.done()
        if status == 202 and reply.get("dry_run", True) is not False:
            return ExecutionOutcome.refused("robot_not_enabled")
        if state == "failed":
            return ExecutionOutcome.refused("execution_failed")
        if state == "superseded":
            # Lab 1 already took a later seq of this session; it will not draw.
            return ExecutionOutcome.refused("duplicate_conflict")
        if status == 409:
            return ExecutionOutcome.refused("executor_busy")
        if status == 422 and reply.get("error") == "letter path not configured":
            return ExecutionOutcome.refused("invalid_letter")
        if status == 503:
            # Lab 1 preflight (calibration, robot enabled/healthy, reach) failed
            # before any motion command.
            return ExecutionOutcome.refused("robot_not_enabled")
        report.detail = report.detail or f"unexpected Lab 1 reply HTTP {status}"
        return ExecutionOutcome.refused("execution_failed")

    def _wait(self, report, session, seq, *, unknown_means_refused=False) -> ExecutionOutcome:
        report.stage = "wait"
        path = "/api/letter/status?" + urllib.parse.urlencode({"session": session, "seq": seq})
        deadline = self._monotonic() + self.wait_seconds
        while True:
            try:
                status, reply = self._send("GET", path, None)
            except Lab1Unreachable as error:
                status, reply = None, {}
                report.log.append(str(error))
            report.polls += 1
            if status == 200:
                state = reply.get("execution_status")
                report.lab1_status = state
                if state == "completed":
                    report.stage = "done"
                    return ExecutionOutcome.done()
                if state == "failed":
                    report.stage, report.detail = "failed", reply.get("error")
                    return ExecutionOutcome.refused("execution_failed")
            elif status == 404 and unknown_means_refused:
                report.detail = "Lab 1 has no record of the letter; nothing was started"
                return ExecutionOutcome.refused("robot_not_enabled")
            elif status == 404:
                # Lab 1 restarted mid-job: whether the arm moved is unknown.
                report.stage, report.detail = "failed", "Lab 1 lost the letter record"
                return ExecutionOutcome.refused("execution_failed")
            if self._monotonic() >= deadline:
                report.stage = "timeout"
                report.detail = (f"no completed/failed from Lab 1 in {self.wait_seconds:g} s; "
                                 "check the robot in the room")
                return ExecutionOutcome.refused("execution_failed")
            self._sleep(self.poll_interval)
