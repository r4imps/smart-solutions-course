import threading
import time
from urllib.error import URLError

import pytest

from src.camera_server import build_sources, create_camera_app, parse_args
from src.cameras import (
    MockCamera,
    UsbCamera,
    UsbCameraConfig,
    XiaoCamera,
    XiaoCameraConfig,
    XiaoSerialCamera,
    XiaoSerialCameraConfig,
)
from src.cameras.xiao_serial_camera import jpeg_dimensions
from src.e2e_demo import run_demo


def wait_until(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def mock_sources(fps=40.0):
    return {
        "table": MockCamera("table", target_fps=fps),
        "tool": MockCamera("tool", target_fps=fps),
    }


def stop_app(app):
    app.extensions["camera_registry"].stop_all()


def test_mock_table_camera_gives_frames():
    source = MockCamera("table", target_fps=40)
    source.start()
    try:
        frame = source.get_frame(timeout=1)
        assert frame is not None
        assert frame.jpeg.startswith(b"\xff\xd8")
        assert b"MOCK TABLE" in frame.jpeg
    finally:
        source.stop()


def test_mock_tool_camera_gives_frames():
    source = MockCamera("tool", target_fps=40)
    source.start()
    try:
        frame = source.get_frame(timeout=1)
        assert frame is not None
        assert frame.jpeg.endswith(b"\xff\xd9")
        assert b"MOCK TOOL" in frame.jpeg
    finally:
        source.stop()


def test_mock_cameras_are_distinguishable():
    sources = mock_sources()
    for source in sources.values():
        source.start()
    try:
        table = sources["table"].get_frame(timeout=1)
        tool = sources["tool"].get_frame(timeout=1)
        assert table.jpeg != tool.jpeg
    finally:
        for source in sources.values():
            source.stop()


def test_mock_counter_advances_and_stop_is_clean():
    source = MockCamera("table", target_fps=50)
    source.start()
    first = source.get_frame(timeout=1)
    second = source.get_frame(after_counter=first.counter, timeout=1)
    source.stop()
    assert second.counter > first.counter
    assert source.worker_alive is False
    assert source.status()["state"] == "stopped"


def test_local_page_contains_both_camera_sections():
    app = create_camera_app(mock_sources())
    try:
        response = app.test_client().get("/")
        assert response.status_code == 200
        assert b"Table camera" in response.data
        assert b"Tool camera" in response.data
        assert b"dropletisse" in response.data
    finally:
        stop_app(app)


def test_status_endpoint_exposes_local_scope_and_both_sources():
    app = create_camera_app(mock_sources())
    try:
        assert wait_until(
            lambda: all(item["available"] for item in app.extensions["camera_registry"].status().values())
        )
        payload = app.test_client().get("/api/cameras").get_json()
        assert payload["scope"] == "local_station_only"
        assert set(payload["cameras"]) == {"table", "tool"}
    finally:
        stop_app(app)


def test_snapshot_is_jpeg_and_increments_served_counter():
    app = create_camera_app(mock_sources())
    try:
        response = app.test_client().get("/snapshot/table.jpg")
        assert response.status_code == 200
        assert response.content_type == "image/jpeg"
        assert response.data.startswith(b"\xff\xd8")
        metrics = app.extensions["camera_registry"].sources["table"].status()["metrics"]
        assert metrics["frames_served"] == 1
        assert metrics["bytes_served"] == len(response.data)
    finally:
        stop_app(app)


def test_mjpeg_stream_has_boundary_and_frame_headers():
    app = create_camera_app(mock_sources())
    try:
        response = app.test_client().get("/stream/tool.mjpg", buffered=False)
        chunk = next(response.response)
        assert response.status_code == 200
        assert "multipart/x-mixed-replace" in response.content_type
        assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n")
        assert b"Content-Length:" in chunk
        response.close()
    finally:
        stop_app(app)


def test_unknown_camera_returns_404():
    app = create_camera_app(mock_sources())
    try:
        assert app.test_client().get("/snapshot/other.jpg").status_code == 404
    finally:
        stop_app(app)


class ClosedCapture:
    def isOpened(self):
        return False

    def release(self):
        pass


class UnavailableCv2:
    CAP_PROP_FRAME_WIDTH = 1
    CAP_PROP_FRAME_HEIGHT = 2
    CAP_PROP_FPS = 3

    def VideoCapture(self, device):
        return ClosedCapture()


def test_unavailable_usb_is_reported_without_crashing_page():
    table = UsbCamera(
        UsbCameraConfig(retry_interval_s=0.01), cv2_module=UnavailableCv2()
    )
    app = create_camera_app({"table": table, "tool": MockCamera("tool")})
    try:
        assert wait_until(lambda: table.status()["state"] == "unavailable")
        assert app.test_client().get("/").status_code == 200
        response = app.test_client().get("/snapshot/table.jpg")
        assert response.status_code == 503
        assert response.get_json()["error"] == "camera_unavailable"
    finally:
        stop_app(app)


def test_unreachable_xiao_is_reported_and_url_is_not_exposed():
    def offline(request, timeout):
        raise URLError("offline")

    tool = XiaoCamera(
        XiaoCameraConfig(
            snapshot_url="http://camera.invalid/private?token=secret",
            retry_interval_s=0.01,
        ),
        opener=offline,
    )
    tool.start()
    try:
        assert wait_until(lambda: tool.status()["state"] == "unavailable")
        status = tool.status()
        assert status["configuration"]["snapshot_url_configured"] is True
        assert "camera.invalid" not in str(status)
        assert "secret" not in str(status)
    finally:
        tool.stop()


class FakeFrame:
    shape = (720, 1280, 3)


class EncodedJpeg:
    def tobytes(self):
        return b"\xff\xd8fake\xff\xd9"


class WorkingCapture:
    def __init__(self, owner):
        self.owner = owner

    def isOpened(self):
        return True

    def set(self, key, value):
        return True

    def read(self):
        return True, FakeFrame()

    def release(self):
        self.owner.releases += 1


class WorkingCv2:
    CAP_PROP_FRAME_WIDTH = 1
    CAP_PROP_FRAME_HEIGHT = 2
    CAP_PROP_FPS = 3
    IMWRITE_JPEG_QUALITY = 4

    def __init__(self):
        self.opens = 0
        self.releases = 0

    def VideoCapture(self, device):
        self.opens += 1
        return WorkingCapture(self)

    def resize(self, frame, dimensions):
        return frame

    def imencode(self, extension, frame, options):
        return True, EncodedJpeg()


def test_two_browser_consumers_share_one_usb_capture():
    cv2 = WorkingCv2()
    source = UsbCamera(
        UsbCameraConfig(target_fps=50, retry_interval_s=0.01), cv2_module=cv2
    )
    app = create_camera_app({"table": source, "tool": MockCamera("tool")})
    ready = threading.Barrier(3)
    release = threading.Event()
    chunks = []
    errors = []

    def browser():
        try:
            response = app.test_client().get("/stream/table.mjpg", buffered=False)
            chunks.append(next(response.response))
            ready.wait(timeout=2)
            release.wait(timeout=2)
            response.close()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=browser) for _ in range(2)]
    try:
        for thread in threads:
            thread.start()
        ready.wait(timeout=2)
        assert cv2.opens == 1
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=2)
        stop_app(app)
    assert not errors
    assert len(chunks) == 2
    assert all(chunk.startswith(b"--frame") for chunk in chunks)
    assert cv2.releases == 1


def test_usb_source_can_restart_without_dangling_capture():
    cv2 = WorkingCv2()
    source = UsbCamera(
        UsbCameraConfig(target_fps=50, retry_interval_s=0.01), cv2_module=cv2
    )
    source.start()
    assert source.get_frame(timeout=1) is not None
    source.stop()
    source.start()
    assert source.get_frame(timeout=1) is not None
    source.stop()
    assert cv2.opens == 2
    assert cv2.releases == 2


def test_non_mock_defaults_do_not_hardcode_xiao_address():
    sources = build_sources(parse_args([]))
    assert sources["tool"].config.snapshot_url == ""
    assert sources["table"].config.device == 0


# Minimal JPEG: SOI, SOF0 for 1600 x 1200 with 3 components, EOI.
UXGA_JPEG = (
    b"\xff\xd8\xff\xc0\x00\x11\x08\x04\xb0\x06\x40\x03"
    + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    + b"\xff\xd9"
)


class FakeXiaoSerial:
    """Answers like the 3D Printing Lab 2 USB diagnostic firmware."""

    def __init__(self, *, camera="ok", pid="0x3660", boot_line=b"READY sensor PID 0x3660\n"):
        self.camera = camera
        self.pid = pid
        self.pending = bytearray(boot_line)
        self.closed = False

    def reset_input_buffer(self):
        # Keep the boot line: a real port opened right after reset can still
        # hold it, and the source must skip it.
        pass

    def write(self, data):
        if data == b"i":
            self.pending += f"INFO camera={self.camera} pid={self.pid} psram=8386199\n".encode()
        elif data == b"c":
            self.pending += f"JPG {len(UXGA_JPEG)}\n".encode() + UXGA_JPEG

    def flush(self):
        pass

    def readline(self):
        end = self.pending.find(b"\n")
        if end < 0:
            line, self.pending = bytes(self.pending), bytearray()
            return line
        line, self.pending = bytes(self.pending[: end + 1]), self.pending[end + 1 :]
        return line

    def read(self, size):
        data, self.pending = bytes(self.pending[:size]), self.pending[size:]
        return data

    def close(self):
        self.closed = True


def serial_tool(fake, **config):
    opened = []

    def opener(port, baud, timeout):
        opened.append(port)
        return fake

    source = XiaoSerialCamera(
        XiaoSerialCameraConfig(port="COM5", target_fps=50, retry_interval_s=0.01, **config),
        serial_opener=opener,
    )
    return source, opened


def test_xiao_serial_gives_full_jpeg_with_real_resolution_and_sensor():
    source, opened = serial_tool(FakeXiaoSerial())
    source.start()
    try:
        frame = source.get_frame(timeout=1)
        assert frame is not None
        assert frame.jpeg == UXGA_JPEG
        status = source.status()
        assert status["resolution"] == {"width": 1600, "height": 1200}
        assert status["configuration"]["backend"] == "xiao-usb-serial"
        assert status["configuration"]["detected_sensor"] == "OV3660"
        assert opened == ["COM5"]
    finally:
        source.stop()


def test_xiao_serial_camera_fault_is_reported_without_crashing_page():
    fake = FakeXiaoSerial(camera="fail", pid="0x0")
    tool, _ = serial_tool(fake)
    app = create_camera_app({"table": MockCamera("table"), "tool": tool})
    try:
        assert wait_until(lambda: tool.status()["state"] == "unavailable")
        assert "camera=fail" in tool.status()["error"]
        assert fake.closed is True
        assert app.test_client().get("/").status_code == 200
        assert app.test_client().get("/snapshot/tool.jpg").status_code == 503
    finally:
        stop_app(app)


def test_xiao_serial_without_port_is_unavailable():
    source = XiaoSerialCamera(XiaoSerialCameraConfig(retry_interval_s=0.01))
    source.start()
    try:
        assert wait_until(lambda: source.status()["state"] == "unavailable")
        assert "not configured" in source.status()["error"]
    finally:
        source.stop()


def test_serial_port_option_selects_serial_tool_camera():
    sources = build_sources(parse_args(["--xiao-serial-port", "COM5"]))
    assert isinstance(sources["tool"], XiaoSerialCamera)
    assert sources["tool"].config.port == "COM5"


def test_serial_port_and_snapshot_url_are_exclusive():
    with pytest.raises(SystemExit):
        parse_args(["--xiao-serial-port", "COM5", "--xiao-snapshot-url", "http://x/snapshot.jpg"])


def test_jpeg_dimensions_ignores_non_jpeg():
    assert jpeg_dimensions(UXGA_JPEG) == (1600, 1200)
    assert jpeg_dimensions(b"\xff\xd8not a jpeg\xff\xd9") == (0, 0)


def test_public_post_office_has_no_camera_routes(app):
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert not any("camera" in route or "stream" in route or "snapshot" in route for route in routes)


def test_camera_failure_does_not_break_station_job_demo(tmp_path):
    source = XiaoCamera(
        XiaoCameraConfig(snapshot_url="", retry_interval_s=0.01)
    )
    source.start()
    try:
        assert wait_until(lambda: source.status()["state"] == "unavailable")
        result = run_demo(tmp_path)
        assert result["server_status"] == "done"
        assert result["hardware_used"] is False
    finally:
        source.stop()
