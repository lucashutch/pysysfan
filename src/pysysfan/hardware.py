"""Hardware manager exports.

This module exports the Windows hardware manager and shared types.
"""

from pysysfan.platforms.windows import WindowsHardwareManager as HardwareManager
from pysysfan.platforms.base import (
    BaseHardwareManager,
    PlatformNotSupportedError,
    SensorKind,
    SensorInfo,
    ControlInfo,
    HardwareScanResult,
)

__all__ = [
    "HardwareManager",
    "BaseHardwareManager",
    "PlatformNotSupportedError",
    "SensorKind",
    "SensorInfo",
    "ControlInfo",
    "HardwareScanResult",
]
