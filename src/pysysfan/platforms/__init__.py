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
        "linux" for Linux systems

    Raises:
        PlatformNotSupportedError: If the platform is not Windows or Linux
    """
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("linux"):
        return "linux"
    else:
        raise PlatformNotSupportedError(
            f"Platform '{sys.platform}' is not supported. "
            "Only Windows and Linux are supported."
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
    elif platform == "linux":
        from pysysfan.platforms.linux import LinuxHardwareManager

        return LinuxHardwareManager
    else:
        # This should never happen due to detect_platform check
        raise PlatformNotSupportedError(f"Unexpected platform: {platform}")


def get_service_manager():
    """Get the appropriate service manager module for the current platform.

    Returns:
        Module with install_task, uninstall_task, get_task_status functions
        (Windows) or install_systemd_service, uninstall_systemd_service,
        get_systemd_service_status functions (Linux)
    """
    platform = detect_platform()

    if platform == "windows":
        from pysysfan.platforms import windows_service

        return windows_service
    elif platform == "linux":
        from pysysfan.platforms import linux_service

        return linux_service
    else:
        raise PlatformNotSupportedError(f"Unexpected platform: {platform}")
