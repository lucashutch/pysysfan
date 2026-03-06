"""Hardware manager factory and re-exports.

This module provides backward compatibility by re-exporting the platform
detection and factory functions. The actual implementations are in the
platforms/ package.

For new code, you can use either:
    # Factory pattern (recommended for library code)
    from pysysfan.platforms import get_hardware_manager
    HardwareManager = get_hardware_manager()

    # Direct import (backward compatible)
    from pysysfan.hardware import HardwareManager

Both approaches return the same platform-specific hardware manager class.
"""

import sys

from pysysfan.platforms import (
    get_hardware_manager,
    BaseHardwareManager,
    PlatformNotSupportedError,
    SensorKind,
    SensorInfo,
    ControlInfo,
    HardwareScanResult,
)

# For backward compatibility: HardwareManager is the platform-specific class
# This is lazily loaded to avoid import errors on non-Windows platforms
if sys.platform.startswith("win"):
    HardwareManager = get_hardware_manager()
else:
    # On non-Windows platforms, set to None to avoid import errors
    # Tests and Windows code will set this appropriately
    HardwareManager = None

__all__ = [
    "HardwareManager",
    "BaseHardwareManager",
    "PlatformNotSupportedError",
    "SensorKind",
    "SensorInfo",
    "ControlInfo",
    "HardwareScanResult",
    "get_hardware_manager",
]
