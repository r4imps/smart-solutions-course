"""Smart Solutions Lab 1 station-side letter receiver.

Dry-run is the default. Real motion requires the explicit ``--execute`` flag,
a complete calibration and a safe status from the official mg400-base server.

Run:
    python -m pip install -r requirements.txt
    python station.py --host 0.0.0.0 --port 5000

Test without Atom:
    python mock_atom.py --url http://127.0.0.1:5000 --letter A
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from fonts import FontError, available_fonts, load_font, normalized_letter
from letter_paths import (
    DEFAULT_LETTERS_PATH,
    LetterPaths,
    get_letter_path,
    load_letter_paths,
)
from mg400_client import MG400Client, MG400Error
from motion_plan import MotionAction, build_motion_plan, format_motion_plan
from robot_calibration import (
    DEFAULT_CALIBRATION_PATH,
    CalibrationError,
    RobotCalibration,
    load_robot_calibration,
)
from robot_mapping import map_normalized_point
from text_job import (
    TextJobError,
    build_robot_plan,
    build_text_job,
    letter_on_paper,
    parse_request,
    preview_svg,
)


app = Flask(__name__)
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    log_path: Path
    letters_path: Path
    dry_run: bool
    calibration_path: Path = DEFAULT_CALIBRATION_PATH
    mg400_url: str = "http://127.0.0.1:8000"
    network_timeout: float = 1.0
    move_timeout: float = 15.0
    move_tolerance: float = 0.5
    # Pen up/down must settle before the next XY move: with the looser XY
    # tolerance the arm started the line while Z was still falling and
    # overshot by 0.7 mm at 2 % and 1.3 mm at 4 % speed (lab, 03.10.2026).
    pen_tolerance: float = 0.15
    # Font used for A-Z letters that letters.json does not define (None = 422).
    letter_font: str | None = None
    # Atom letters on a calibrated sheet: cell size (capital height), mm.
    letter_size_mm: float = 20.0


@dataclass
class ExecutionRecord:
    state: str
    error: str | None = None


CONFIG = Config(
    log_path=Path("data/letter_events.csv"),
    letters_path=DEFAULT_LETTERS_PATH,
    dry_run=True,
)
LOG_LOCK = threading.Lock()
# Flask serves requests on threads: the duplicate check and the update must be atomic.
SEQ_LOCK = threading.Lock()
EXECUTION_LOCK = threading.Lock()

# The latest accepted sequence number per Atom boot/session id.
# It prevents a retry from accidentally starting the same robot drawing twice.
LAST_SEQ: dict[str, int] = {}
# Execute-mode lifecycle per Atom event. Preflight failures are removed so the
# same event can be retried; once the first move is attempted the record stays.
EXECUTION_EVENTS: dict[tuple[str, int], ExecutionRecord] = {}
LETTER_PATHS: LetterPaths = load_letter_paths(CONFIG.letters_path)
MG400_CLIENT_FACTORY = MG400Client
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEXT_JOB_SEQ = 0
# Typewriter cursor for Atom letters on the sheet: paper (left, top) of the
# next letter cell; None = top-left of the reachable area.
LETTER_CURSOR: tuple[float, float] | None = None


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def monotonic_ns() -> int:
    return time.monotonic_ns()


def text_log_path() -> Path:
    """Text jobs get their own CSV so the Atom latency log stays clean."""
    return CONFIG.log_path.with_name("text_events.csv")


def ensure_log(path: Path | None = None) -> None:
    path = path or CONFIG.log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                "letter",
                "session",
                "seq",
                "atom_sent_ms",
                "station_received_iso",
                "station_received_monotonic_ns",
                "robot_command_monotonic_ns",
                "status",
                "note",
            ]
        )


def append_log(
    *,
    letter: str,
    session: str,
    seq: int,
    atom_sent_ms: int | None,
    station_received_iso: str,
    station_received_monotonic_ns: int,
    robot_command_monotonic_ns: int | None,
    status: str,
    note: str = "",
    path: Path | None = None,
) -> None:
    path = path or CONFIG.log_path
    ensure_log(path)
    with LOG_LOCK, path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                letter,
                session,
                seq,
                "" if atom_sent_ms is None else atom_sent_ms,
                station_received_iso,
                station_received_monotonic_ns,
                "" if robot_command_monotonic_ns is None else robot_command_monotonic_ns,
                status,
                note,
            ]
        )


def validate_message(payload: object) -> tuple[str, str, int, int | None]:
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")

    letter = payload.get("letter")
    if not isinstance(letter, str):
        raise ValueError("letter must be a string")

    letter = letter.strip().upper()
    if len(letter) != 1 or not ("A" <= letter <= "Z"):
        raise ValueError("letter must be one character A-Z")

    # Session + sequence make retries idempotent.
    session = payload.get("session", "default")
    if not isinstance(session, str) or not session.strip():
        raise ValueError("session must be a non-empty string")
    session = session.strip()[:64]

    seq = payload.get("seq", 0)
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ValueError("seq must be a non-negative integer")

    atom_sent_ms = payload.get("atom_sent_ms")
    if atom_sent_ms is not None:
        if isinstance(atom_sent_ms, bool) or not isinstance(atom_sent_ms, int) or atom_sent_ms < 0:
            raise ValueError("atom_sent_ms must be a non-negative integer")

    return letter, session, seq, atom_sent_ms


@app.get("/health")
def health():
    try:
        calibration_complete = load_robot_calibration(CONFIG.calibration_path).is_complete
    except CalibrationError:
        calibration_complete = False
    return jsonify(
        ok=True,
        service="smart-solutions-station",
        execution_mode="dry-run" if CONFIG.dry_run else "execute",
        calibration_complete=calibration_complete,
    )


def _execute_plan(
    plan: list[MotionAction],
    calibration: RobotCalibration,
    client: MG400Client,
    on_first_move: Callable[[int], None],
) -> None:
    """Execute one complete normalized plan after a fresh safety check."""
    if any(item["action"] == "MOVE_NORMALIZED" for item in plan):
        calibration.require_complete()
    else:
        calibration.require_text_ready()
    status = client.get_status()
    client.require_safe_status(status)
    current_x, current_y, current_z, _ = client.pose_from_status(status)

    speed = calibration.motion.speed_percent
    r = calibration.pose.r
    pen_up_z = calibration.pose.pen_up_z
    pen_down_z = calibration.pose.pen_down_z
    if None in (speed, r, pen_up_z, pen_down_z):
        raise CalibrationError("roboti kalibratsioon on puudulik")

    client.set_speed(speed)
    first_move_recorded = False
    for item in plan:
        previous = (current_x, current_y, current_z)
        action = item["action"]
        if action == "PEN_UP":
            current_z = pen_up_z
        elif action == "PEN_DOWN":
            current_z = pen_down_z
        elif action == "MOVE_NORMALIZED":
            point = map_normalized_point(calibration, item["x"], item["y"])
            current_x, current_y = point.x, point.y
        elif action == "MOVE_ROBOT":
            current_x, current_y = float(item["x"]), float(item["y"])
        else:
            raise ValueError(f"unknown motion action: {action}")
        if not first_move_recorded:
            on_first_move(monotonic_ns())
            first_move_recorded = True
        client.move_and_wait(
            current_x,
            current_y,
            current_z,
            r,
            tolerance=(
                CONFIG.pen_tolerance
                if action in ("PEN_UP", "PEN_DOWN")
                else CONFIG.move_tolerance
            ),
            timeout=move_timeout(previous, (current_x, current_y, current_z), speed),
        )


def move_timeout(
    start: tuple[float, float, float], end: tuple[float, float, float], speed_percent: float
) -> float:
    """Time allowed for one move: its expected duration twice over plus slack.

    03.10.26: a fixed 15 s stopped the arm half-way on a 280 mm travel at 4 %
    (~8 mm/s, ~35 s). mg400-base: 100 % = 200 mm/s.
    """
    distance = math.dist(start, end)
    speed_mm_s = max(speed_percent, 1.0) / 100 * 200.0
    return max(CONFIG.move_timeout, 2.0 * distance / speed_mm_s + 5.0)


def _run_execution(
    *,
    key: tuple[str, int],
    letter: str,
    atom_sent_ms: int | None,
    received_iso: str,
    received_mono: int,
    plan: list[MotionAction],
    calibration: RobotCalibration,
    client: MG400Client,
) -> None:
    command_ns: int | None = None
    final_state = "completed"
    error: str | None = None

    def record_first_move(value: int) -> None:
        nonlocal command_ns
        command_ns = value

    try:
        _execute_plan(plan, calibration, client, record_first_move)
    except Exception as exc:
        final_state = "failed"
        error = str(exc)
        LOGGER.exception("MG400 letter execution failed for %s seq=%s", *key)
        try:
            client.stop()
        except MG400Error as stop_exc:
            LOGGER.warning("best-effort MG400 stop failed: %s", stop_exc)
    finally:
        with SEQ_LOCK:
            record = EXECUTION_EVENTS[key]
            record.state = final_state
            record.error = error
        try:
            append_log(
                letter=letter,
                session=key[0],
                seq=key[1],
                atom_sent_ms=atom_sent_ms,
                station_received_iso=received_iso,
                station_received_monotonic_ns=received_mono,
                robot_command_monotonic_ns=command_ns,
                status="executed" if final_state == "completed" else "execution_error",
                note="MG400 motion plan completed" if error is None else error,
                path=text_log_path() if key[0] == "text" else None,
            )
        except Exception:
            LOGGER.exception("could not write MG400 execution log")
        finally:
            EXECUTION_LOCK.release()


def _letter_strokes(letter: str):
    try:
        return get_letter_path(letter, LETTER_PATHS)
    except ValueError:
        if CONFIG.letter_font is None:
            raise
    try:
        return normalized_letter(letter, load_font(CONFIG.letter_font))
    except FontError as exc:
        raise ValueError(f"letter path not configured: {letter} ({exc})") from exc


def _advance_letter_cursor(next_cursor: tuple[float, float] | None) -> None:
    global LETTER_CURSOR
    if next_cursor is not None:
        LETTER_CURSOR = next_cursor


@app.get("/api/paper/cursor")
def paper_cursor():
    cursor = LETTER_CURSOR
    return jsonify(ok=True, cursor=None if cursor is None else {"x": cursor[0], "top": cursor[1]})


@app.post("/api/paper/cursor")
def paper_cursor_set():
    """Put the next Atom letter at paper (x, top) mm, e.g. the start of row 2
    when row 1 of a reused sheet is already written. Off-sheet values wrap
    like the typewriter does."""
    global LETTER_CURSOR
    data = request.get_json(silent=True) or {}
    try:
        x, top = float(data["x"]), float(data["top"])
    except (KeyError, TypeError, ValueError):
        return jsonify(ok=False, error="x and top must be numbers (mm)"), 400
    if not (math.isfinite(x) and math.isfinite(top)):
        return jsonify(ok=False, error="x and top must be finite"), 400
    LETTER_CURSOR = (x, top)
    return jsonify(ok=True, cursor={"x": x, "top": top})


@app.post("/api/paper/cursor/reset")
def paper_cursor_reset():
    """Next Atom letter starts again at the top-left of the sheet."""
    global LETTER_CURSOR
    LETTER_CURSOR = None
    return jsonify(ok=True, cursor=None)


@app.post("/api/letter")
def receive_letter():
    # Timestamp as early as possible after Flask has accepted the request.
    received_mono = monotonic_ns()
    received_iso = utc_iso()

    try:
        payload = request.get_json(force=False, silent=False)
        letter, session, seq, atom_sent_ms = validate_message(payload)
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 400

    try:
        strokes = _letter_strokes(letter)
    except ValueError as exc:
        append_log(
            letter=letter,
            session=session,
            seq=seq,
            atom_sent_ms=atom_sent_ms,
            station_received_iso=received_iso,
            station_received_monotonic_ns=received_mono,
            robot_command_monotonic_ns=None,
            status="path_not_configured",
            note=str(exc),
        )
        return (
            jsonify(
                ok=False,
                error="letter path not configured",
                letter=letter,
                robot_started=False,
            ),
            422,
        )

    plan = build_motion_plan(strokes)
    # With a calibrated sheet the letter goes next to the previous one, upright
    # for the reader; otherwise into the fixed workspace box as before.
    next_cursor = None
    layout_calibration, _ = _calibration_or_none()
    if layout_calibration is not None and layout_calibration.paper.is_complete:
        try:
            plan, next_cursor = letter_on_paper(
                strokes, layout_calibration, LETTER_CURSOR, CONFIG.letter_size_mm
            )
        except TextJobError as exc:
            append_log(
                letter=letter,
                session=session,
                seq=seq,
                atom_sent_ms=atom_sent_ms,
                station_received_iso=received_iso,
                station_received_monotonic_ns=received_mono,
                robot_command_monotonic_ns=None,
                status="layout_error",
                note=str(exc),
            )
            return jsonify(ok=False, error=str(exc), letter=letter, robot_started=False), 422
    execution_lock_acquired = False
    execution_key = (session, seq)
    execution_record: ExecutionRecord | None = None
    with SEQ_LOCK:
        previous = LAST_SEQ.get(session)
        execution_record = EXECUTION_EVENTS.get(execution_key)
        duplicate = execution_record is not None or (
            previous is not None and seq <= previous
        )
        if not duplicate:
            if not CONFIG.dry_run:
                execution_lock_acquired = EXECUTION_LOCK.acquire(blocking=False)
                if execution_lock_acquired:
                    execution_record = ExecutionRecord("preflight")
                    EXECUTION_EVENTS[execution_key] = execution_record
            else:
                LAST_SEQ[session] = seq

    if duplicate:
        state = execution_record.state if execution_record else "superseded"
        failed = state in ("failed", "preflight")
        error = (
            execution_record.error
            if state == "failed" and execution_record is not None
            else "preflight is still in progress" if state == "preflight" else None
        )
        append_log(
            letter=letter,
            session=session,
            seq=seq,
            atom_sent_ms=atom_sent_ms,
            station_received_iso=received_iso,
            station_received_monotonic_ns=received_mono,
            robot_command_monotonic_ns=None,
            status=f"duplicate_{state}",
            note=error or "acknowledged; robot command suppressed",
        )
        return (
            jsonify(
                ok=not failed,
                duplicate=True,
                letter=letter,
                seq=seq,
                station_received_iso=received_iso,
                robot_started=state in ("started", "failed", "completed"),
                dry_run=CONFIG.dry_run,
                execution_status=state,
                **({"error": error} if error else {}),
            ),
            409 if failed else (202 if state == "started" else 200),
        )

    if not CONFIG.dry_run and not execution_lock_acquired:
        append_log(
            letter=letter,
            session=session,
            seq=seq,
            atom_sent_ms=atom_sent_ms,
            station_received_iso=received_iso,
            station_received_monotonic_ns=received_mono,
            robot_command_monotonic_ns=None,
            status="busy",
            note="another letter execution is already running",
        )
        return (
            jsonify(
                ok=False,
                error="station is already drawing another letter",
                letter=letter,
                robot_started=False,
                dry_run=False,
            ),
            409,
        )

    if not CONFIG.dry_run:
        try:
            calibration = load_robot_calibration(CONFIG.calibration_path)
            if next_cursor is None:
                calibration.require_complete()
            else:
                calibration.require_text_ready()
            client = MG400_CLIENT_FACTORY(
                CONFIG.mg400_url, network_timeout=CONFIG.network_timeout
            )
            # Complete the safety gate while this request owns the busy lock.
            # No MG400 motion command is sent during preflight.
            status = client.get_status()
            client.require_safe_status(status)
            client.pose_from_status(status)
            if next_cursor is not None:
                _check_plan_with_server(plan, calibration, client)
        except (CalibrationError, MG400Error, ValueError) as exc:
            with SEQ_LOCK:
                # The event was not accepted; the same Atom seq may retry.
                EXECUTION_EVENTS.pop(execution_key, None)
            EXECUTION_LOCK.release()
            append_log(
                letter=letter,
                session=session,
                seq=seq,
                atom_sent_ms=atom_sent_ms,
                station_received_iso=received_iso,
                station_received_monotonic_ns=received_mono,
                robot_command_monotonic_ns=None,
                status="preflight_error",
                note=str(exc),
            )
            return (
                jsonify(
                    ok=False,
                    error=str(exc),
                    letter=letter,
                    robot_started=False,
                    dry_run=False,
                ),
                503,
            )

        worker = threading.Thread(
            target=_run_execution,
            kwargs={
                "key": execution_key,
                "letter": letter,
                "atom_sent_ms": atom_sent_ms,
                "received_iso": received_iso,
                "received_mono": received_mono,
                "plan": plan,
                "calibration": calibration,
                "client": client,
            },
            name=f"mg400-letter-{session[:12]}-{seq}",
            daemon=False,
        )
        with SEQ_LOCK:
            try:
                worker.start()
            except RuntimeError as exc:
                EXECUTION_EVENTS.pop(execution_key, None)
                EXECUTION_LOCK.release()
                return jsonify(ok=False, error=str(exc), robot_started=False), 503
            EXECUTION_EVENTS[execution_key].state = "started"
            LAST_SEQ[session] = max(seq, LAST_SEQ.get(session, seq))
            _advance_letter_cursor(next_cursor)
        return (
            jsonify(
                ok=True,
                accepted=True,
                duplicate=False,
                letter=letter,
                seq=seq,
                station_received_iso=received_iso,
                robot_started=True,
                execution_status="started",
                dry_run=False,
                action_count=len(plan),
            ),
            202,
        )

    _advance_letter_cursor(next_cursor)
    append_log(
        letter=letter,
        session=session,
        seq=seq,
        atom_sent_ms=atom_sent_ms,
        station_received_iso=received_iso,
        station_received_monotonic_ns=received_mono,
        robot_command_monotonic_ns=None,
        status="accepted_dry_run",
        note="normalized motion plan only; no robot command sent",
    )

    print(
        json.dumps(
            {
                "event": "letter",
                "letter": letter,
                "session": session,
                "seq": seq,
                "station_received_iso": received_iso,
                "status": "accepted_dry_run",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(format_motion_plan(plan), flush=True)

    return (
        jsonify(
            ok=True,
            duplicate=False,
            letter=letter,
            seq=seq,
            station_received_iso=received_iso,
            robot_started=False,
            dry_run=True,
            action_count=len(plan),
        ),
        202,
    )


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/fonts")
def fonts():
    result = []
    for name in available_fonts():
        try:
            result.append({"name": name, "title": load_font(name).title})
        except FontError as exc:
            LOGGER.warning("skipping broken font %s: %s", name, exc)
    return jsonify(ok=True, fonts=result)


def _calibration_or_none() -> tuple[RobotCalibration | None, str | None]:
    try:
        return load_robot_calibration(CONFIG.calibration_path), None
    except CalibrationError as exc:
        return None, str(exc)


def _text_job_from_request():
    calibration, calibration_error = _calibration_or_none()
    job = build_text_job(parse_request(request.get_json(silent=True)), calibration)
    if calibration_error:
        job.warnings.append(f"calibration file: {calibration_error}")
    speed = calibration.motion.speed_percent if calibration is not None else None
    return job, calibration, speed


@app.post("/api/text/preview")
def text_preview():
    """Lay the text out and return an SVG preview; never touches the robot."""
    try:
        job, _, speed = _text_job_from_request()
    except TextJobError as exc:
        return jsonify(ok=False, error=str(exc)), 422
    return jsonify(ok=True, dry_run=CONFIG.dry_run, svg=preview_svg(job), **job.summary(speed))


@app.post("/api/text/draw")
def text_draw():
    """Draw text on the calibrated sheet; dry-run unless the station runs --execute."""
    global TEXT_JOB_SEQ
    received_mono = monotonic_ns()
    received_iso = utc_iso()
    try:
        job, calibration, speed = _text_job_from_request()
        plan = build_robot_plan(job) if job.calibrated or not CONFIG.dry_run else None
    except TextJobError as exc:
        return jsonify(ok=False, error=str(exc), robot_started=False), 422
    label = " ".join(job.request.text.split())[:40]

    if CONFIG.dry_run:
        if plan is not None:
            print(format_motion_plan(plan), flush=True)
        return (
            jsonify(
                ok=True,
                dry_run=True,
                robot_started=False,
                action_count=None if plan is None else len(plan),
                **job.summary(speed),
            ),
            202,
        )

    assert plan is not None and calibration is not None
    if not EXECUTION_LOCK.acquire(blocking=False):
        return (
            jsonify(ok=False, error="station is already drawing", robot_started=False),
            409,
        )
    with SEQ_LOCK:
        TEXT_JOB_SEQ += 1
        key = ("text", TEXT_JOB_SEQ)
        EXECUTION_EVENTS[key] = ExecutionRecord("preflight")
    try:
        calibration.require_text_ready()
        client = MG400_CLIENT_FACTORY(CONFIG.mg400_url, network_timeout=CONFIG.network_timeout)
        status = client.get_status()
        client.require_safe_status(status)
        _check_plan_with_server(plan, calibration, client)
    except (CalibrationError, MG400Error, ValueError) as exc:
        with SEQ_LOCK:
            EXECUTION_EVENTS.pop(key, None)
        EXECUTION_LOCK.release()
        return jsonify(ok=False, error=str(exc), robot_started=False), 503

    worker = threading.Thread(
        target=_run_execution,
        kwargs={
            "key": key,
            "letter": label,
            "atom_sent_ms": None,
            "received_iso": received_iso,
            "received_mono": received_mono,
            "plan": plan,
            "calibration": calibration,
            "client": client,
        },
        name=f"mg400-text-{key[1]}",
        daemon=False,
    )
    with SEQ_LOCK:
        try:
            worker.start()
        except RuntimeError as exc:
            EXECUTION_EVENTS.pop(key, None)
            EXECUTION_LOCK.release()
            return jsonify(ok=False, error=str(exc), robot_started=False), 503
        EXECUTION_EVENTS[key].state = "started"
    return (
        jsonify(
            ok=True,
            dry_run=False,
            robot_started=True,
            job=key[1],
            execution_status="started",
            action_count=len(plan),
            **job.summary(speed),
        ),
        202,
    )


def _check_plan_with_server(
    plan: list[MotionAction], calibration: RobotCalibration, client: MG400Client
) -> None:
    """Every plan point at both pen heights through mg400-base's joint model."""
    points = {
        (round(item["x"], 2), round(item["y"], 2))
        for item in plan
        if item["action"] == "MOVE_ROBOT"
    }
    for z in (calibration.pose.pen_down_z, calibration.pose.pen_up_z):
        for x, y in sorted(points):
            reachable = client.check_pose(x, y, z)  # type: ignore[arg-type]
            if reachable is None:
                LOGGER.warning("mg400-base has no /api/check; using the reach ring only")
                return
            if not reachable:
                raise MG400Error(
                    f"point X {x:.1f} Y {y:.1f} Z {z:.1f} hits an MG400 joint limit; "
                    "move the sheet closer to the robot's middle reach"
                )


@app.get("/api/text/<int:job_id>")
def text_status(job_id: int):
    with SEQ_LOCK:
        record = EXECUTION_EVENTS.get(("text", job_id))
        if record is None:
            return jsonify(ok=False, error="unknown job"), 404
        return jsonify(ok=True, job=job_id, execution_status=record.state, error=record.error)


@app.get("/api/letter/status")
def letter_status():
    """Read-only lifecycle of one execute-mode Atom letter (?session=&seq=), so
    a caller such as the Lab 2 adapter can wait for completed/failed. Dry-run
    letters and unknown events have no record."""
    session = request.args.get("session", "").strip()[:64]
    try:
        seq = int(request.args.get("seq", ""))
    except ValueError:
        return jsonify(ok=False, error="seq must be an integer"), 400
    if not session or seq < 0:
        return jsonify(ok=False, error="session and a non-negative seq are required"), 400
    with SEQ_LOCK:
        record = EXECUTION_EVENTS.get((session, seq))
        if record is None:
            return jsonify(ok=False, error="unknown letter event", dry_run=CONFIG.dry_run), 404
        return jsonify(
            ok=True,
            session=session,
            seq=seq,
            execution_status=record.state,
            error=record.error,
            dry_run=CONFIG.dry_run,
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--log", type=Path, default=Path("data/letter_events.csv"))
    p.add_argument("--letters", type=Path, default=DEFAULT_LETTERS_PATH)
    p.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION_PATH)
    p.add_argument("--mg400-url", default="http://127.0.0.1:8000")
    p.add_argument(
        "--letter-font",
        default="futural",
        help="font for Atom letters missing from letters.json ('none' = reject them)",
    )
    p.add_argument(
        "--letter-size",
        type=float,
        default=20.0,
        help="Atom letter cell size in mm when the sheet is calibrated (typewriter mode)",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        action="store_true",
        help="allow MG400 commands after calibration and safety checks",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="build and print normalized plans without sending robot commands (default)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    CONFIG = Config(
        log_path=args.log,
        letters_path=args.letters,
        dry_run=not args.execute,
        calibration_path=args.calibration,
        mg400_url=args.mg400_url,
        letter_font=None if args.letter_font.lower() == "none" else args.letter_font,
        letter_size_mm=args.letter_size,
    )
    LETTER_PATHS = load_letter_paths(CONFIG.letters_path)
    if CONFIG.letter_font is not None:
        load_font(CONFIG.letter_font)  # fail at start-up, not on the first key press
    ensure_log()
    # Debug/reloader off: the station must have one process and one event queue.
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
