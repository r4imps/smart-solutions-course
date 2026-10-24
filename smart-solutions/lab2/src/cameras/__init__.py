"""Local-only Lab 2 camera sources."""

from .base import CameraFrame, CameraSource
from .mock_camera import MockCamera
from .usb_camera import UsbCamera, UsbCameraConfig
from .xiao_camera import XiaoCamera, XiaoCameraConfig
from .xiao_serial_camera import XiaoSerialCamera, XiaoSerialCameraConfig

__all__ = [
    "CameraFrame",
    "CameraSource",
    "MockCamera",
    "UsbCamera",
    "UsbCameraConfig",
    "XiaoCamera",
    "XiaoCameraConfig",
    "XiaoSerialCamera",
    "XiaoSerialCameraConfig",
]
