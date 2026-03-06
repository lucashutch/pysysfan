"""Platform detection and factory module.

This module provides platform detection and factory functions to get
the appropriate hardware manager and service implementations for the
current operating system.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Type

from pysysfan.platforms.base import (
    BaseHardwareManager,
    PlatformNotSupportedError,
    SensorKind,
    SensorInfo,
    ControlInfo,
    HardwareScanResult,
)

if TYPE_CHECKING:
    pass

__all__ = [
    "detect_platform",
    "get_hardware_manager",
    "BaseHardwareManager",
    "PlatformNotSupportedError",
    "SensorKind",
    "SensorInfo",
    "ControlInfo",
    "HardwareScanResult",
]


def detect_platform() -> str:
    """Detect the current operating system platform.

    Returns:
        "windows" for Windows systems

    Raises:
        PlatformNotSupportedError: If the platform is not Windows
    """
    if sys.platform.startswith("win"):
        return "windows"
    else:
        raise PlatformNotSupportedError(
            f"Platform '{sys.platform}' is not supported. "
            "pysysfan only supports Windows."
        )


def get_hardware_manager() -> Type[BaseHardwareManager]:
    """Get the appropriate HardwareManager class for the current platform.

    This factory function returns the platform-specific hardware manager
    class. Use it to instantiate a hardware manager:

        HardwareManager = get_hardware_manager()
        with HardwareManager() as hw:
            result = hw.scan()

    Returns:
        The HardwareManager class for the current platform

    Raises:
        PlatformNotSupportedError: If the platform is not supported
        ImportError: If the platform module cannot be imported
    """
    platform = detect_platform()

    if platform == "windows":
        from pysysfan.platforms.windows import WindowsHardwareManager

        return WindowsHardwareManager
    else:
        # This should never happen due to detect_platform check
        raise PlatformNotSupportedError(f"Unexpected platform: {platform}")


def get_service_manager():
    """Get the appropriate service manager module for the current platform.

    Returns:
        Module with install_task, uninstall_task, get_task_status functions
        (Windows)
    """
    platform = detect_platform()

    if platform == "windows":
        from pysysfan.platforms import windows_service

        return windows_service
    else:
        raise PlatformNotSupportedError(f"Unexpected platform: {platform}")
