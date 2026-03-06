"""Platform exports module.

This module exports Windows-specific implementations and shared types.
"""

from __future__ import annotations

from pysysfan.platforms.base import (
    BaseHardwareManager,
    PlatformNotSupportedError,
    SensorKind,
    SensorInfo,
    ControlInfo,
    HardwareScanResult,
)
from pysysfan.platforms.windows import WindowsHardwareManager
from pysysfan.platforms import windows_service

__all__ = [
    "WindowsHardwareManager",
    "windows_service",
    "BaseHardwareManager",
    "PlatformNotSupportedError",
    "SensorKind",
    "SensorInfo",
    "ControlInfo",
    "HardwareScanResult",
]
