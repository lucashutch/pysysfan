"""Base hardware abstraction layer for pysysfan.

This module defines the abstract base classes and shared types used by
platform-specific hardware implementations (Windows, Linux, etc.).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self

logger = logging.getLogger(__name__)


class SensorKind(IntEnum):
    """Mirrors LibreHardwareMonitor.Hardware.SensorType enum values.

    Used for cross-platform sensor type identification.
    """

    VOLTAGE = 0
    CURRENT = 1
    POWER = 2
    CLOCK = 3
    TEMPERATURE = 4
    LOAD = 5
    FREQUENCY = 6
    FAN = 7
    FLOW = 8
    CONTROL = 9
    LEVEL = 10
    FACTOR = 11
    DATA = 12
    SMALLDATA = 13
    THROUGHPUT = 14
    TIMESPAN = 15
    ENERGY = 16
    NOISE = 17
    HUMIDITY = 18


@dataclass
class SensorInfo:
    """Represents a hardware sensor reading.

    This dataclass is used across all platforms for consistent
    sensor representation.
    """

    hardware_name: str
    hardware_type: str
    sensor_name: str
    sensor_type: str
    identifier: str
    value: float | None
    min_value: float | None = None
    max_value: float | None = None


@dataclass
class ControlInfo:
    """Represents a controllable fan output.

    This dataclass is used across all platforms for consistent
    control representation.
    """

    hardware_name: str
    sensor_name: str
    identifier: str
    current_value: float | None  # Current control % (0-100)
    has_control: bool = False


@dataclass
class HardwareScanResult:
    """Result of a full hardware scan.

    Contains all discovered sensors and controls from a hardware scan.
    """

    temperatures: list[SensorInfo] = field(default_factory=list)
    fans: list[SensorInfo] = field(default_factory=list)
    controls: list[ControlInfo] = field(default_factory=list)
    all_sensors: list[SensorInfo] = field(default_factory=list)


class BaseHardwareManager(ABC):
    """Abstract base class for hardware managers.

    All platform-specific hardware implementations must inherit from this
    class and implement the abstract methods.

    Usage:
        with HardwareManager() as hw:
            result = hw.scan()
            for temp in result.temperatures:
                print(f"{temp.sensor_name}: {temp.value}°C")
    """

    def __init__(self):
        """Initialize the hardware manager."""
        self._off_mode_fans: set[str] = set()  # Track fans currently off

    @abstractmethod
    def open(self) -> None:
        """Initialize and open the hardware connection.

        This method should perform any necessary initialization, such as:
        - Loading drivers/libraries
        - Opening handles
        - Detecting hardware capabilities

        Raises:
            RuntimeError: If initialization fails
            PermissionError: If insufficient privileges
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the hardware connection and cleanup resources.

        This method should:
        - Restore default fan control (safety)
        - Close handles
        - Cleanup resources
        """
        pass

    def __enter__(self) -> Self:
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - always cleanup."""
        self.close()
        return False

    @abstractmethod
    def scan(self) -> HardwareScanResult:
        """Perform a full hardware scan.

        Discovers and returns all available sensors and controls.

        Returns:
            HardwareScanResult containing all discovered hardware

        Raises:
            RuntimeError: If hardware access fails
        """
        pass

    @abstractmethod
    def get_temperatures(self) -> list[SensorInfo]:
        """Get all current temperature readings.

        Returns:
            List of temperature SensorInfo objects
        """
        pass

    @abstractmethod
    def get_fan_speeds(self) -> list[SensorInfo]:
        """Get all current fan speed readings (RPM).

        Returns:
            List of fan speed SensorInfo objects
        """
        pass

    @abstractmethod
    def get_controls(self) -> list[ControlInfo]:
        """Get all controllable fan outputs.

        Returns:
            List of ControlInfo objects
        """
        pass

    @abstractmethod
    def set_fan_speed(
        self, control_identifier: str, percent: float, force_zero: bool = True
    ) -> None:
        """Set a fan speed by its control identifier.

        Args:
            control_identifier: The platform-specific identifier for the control
            percent: Speed percentage (0-100). Values should be clamped.
            force_zero: If True, actively set 0% duty cycle. If False, release to BIOS.

        Raises:
            ValueError: If the control_identifier is invalid
            RuntimeError: If setting the speed fails
            PermissionError: If insufficient privileges
        """
        pass

    @abstractmethod
    def restore_defaults(self) -> None:
        """Restore all fan controls to BIOS/default mode.

        This is critical for safety - allows the BIOS/firmware to resume
        automatic fan control when the daemon exits.

        Should be called automatically on close() and via signal handlers.
        """
        pass

    @abstractmethod
    def get_hardware_fingerprint(self) -> str:
        """Get a fingerprint of the current hardware configuration.

        Used to detect hardware changes and invalidate caches.

        Returns:
            A string fingerprint that changes when hardware changes
        """
        pass


class PlatformNotSupportedError(Exception):
    """Raised when the current platform is not supported."""

    pass
