"""XIAO ESP32S3 Sense tool camera over USB Serial.

Fallback for a station PC that cannot reach the XIAO over Wi-Fi. Speaks the
protocol of the 3D Printing Lab 2 diagnostic firmware
(3d-printing-course/3d-print/lab2/tool-camera/firmware):

  host sends 'c'  -> board answers "JPG <bytes>\\n" followed by the JPEG
  host sends 'i'  -> board answers "INFO camera=ok pid=0x3660 psram=<bytes>"
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, BinaryIO, Callable

from .base import CameraSource

SENSOR_NAMES = {0x2642: "OV2640", 0x3660: "OV3660", 0x5640: "OV5640"}
# JPEG start-of-frame markers that carry the image size (not DHT/JPG/DAC).
_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


@dataclass(frozen=True)
class XiaoSerialCameraConfig:
    port: str = ""
    baud: int = 115200
    target_fps: float = 5.0
    read_timeout_s: float = 3.0
    retry_interval_s: float = 2.0
    max_frame_bytes: int = 5_000_000
    max_text_lines: int = 20


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Width and height from the JPEG SOF header, or (0, 0) if not found."""
    i = 2
    while i + 9 <= len(data):
        if data[i] != 0xFF:
            return 0, 0
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        if marker in _SOF_MARKERS:
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return width, height
        if marker == 0xDA:  # start of scan: no SOF before the image data
            return 0, 0
        i += 2 + length
    return 0, 0


def _open_serial(port: str, baud: int, timeout: float) -> BinaryIO:
    import serial

    stream = serial.serial_for_url(port, baud, timeout=timeout, do_not_open=True)
    # Toggling DTR/RTS resets the ESP32-S3, so keep both low.
    stream.dtr = False
    stream.rts = False
    stream.open()
    return stream


class XiaoSerialCamera(CameraSource):
    def __init__(
        self,
        config: XiaoSerialCameraConfig,
        *,
        serial_opener: Callable[[str, int, float], BinaryIO] = _open_serial,
    ) -> None:
        super().__init__(
            "tool",
            target_fps=config.target_fps,
            retry_interval_s=config.retry_interval_s,
        )
        self.config = config
        self._serial_opener = serial_opener
        self._sensor: str | None = None

    def open_source(self) -> object:
        if not self.config.port:
            raise RuntimeError("XIAO serial port is not configured")
        stream = self._serial_opener(self.config.port, self.config.baud, self.config.read_timeout_s)
        try:
            self._sensor = self._read_sensor(stream)
        except Exception:
            stream.close()
            raise
        return stream

    def capture_frame(self, resource: object) -> tuple[bytes, int, int]:
        stream: BinaryIO = resource  # type: ignore[assignment]
        stream.reset_input_buffer()
        stream.write(b"c")
        stream.flush()
        size = int(self._read_reply(stream, "JPG ").split()[1])
        if size <= 0 or size > self.config.max_frame_bytes:
            raise RuntimeError(f"XIAO JPEG size {size} is outside the configured limit")
        data = stream.read(size)
        if len(data) != size:
            raise RuntimeError(f"XIAO JPEG short read: {len(data)} of {size} bytes")
        if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
            raise RuntimeError("XIAO serial response is not a complete JPEG")
        width, height = jpeg_dimensions(data)
        return data, width, height

    def close_source(self, resource: object) -> None:
        resource.close()  # type: ignore[attr-defined]

    def configuration(self) -> dict[str, object]:
        return {
            "backend": "xiao-usb-serial",
            **asdict(self.config),
            "detected_sensor": self._sensor,
        }

    def _read_sensor(self, stream: BinaryIO) -> str:
        stream.reset_input_buffer()
        stream.write(b"i")
        stream.flush()
        fields = dict(
            part.split("=", 1) for part in self._read_reply(stream, "INFO ").split()[1:] if "=" in part
        )
        if fields.get("camera") != "ok":
            raise RuntimeError(f"XIAO camera not ready: camera={fields.get('camera')}")
        pid = int(fields.get("pid", "0"), 16)
        return SENSOR_NAMES.get(pid, f"unknown (0x{pid:x})")

    def _read_reply(self, stream: BinaryIO, prefix: str) -> str:
        # Boot messages such as "READY sensor PID 0x3660" may arrive first.
        for _ in range(self.config.max_text_lines):
            line = stream.readline().decode("ascii", errors="replace").strip()
            if not line:
                raise TimeoutError(f"no {prefix.strip()} reply from XIAO on {self.config.port}")
            if line.startswith("ERR"):
                raise RuntimeError(f"XIAO reported: {line[:120]}")
            if line.startswith(prefix):
                return line
        raise RuntimeError(f"no {prefix.strip()} reply within {self.config.max_text_lines} lines")
