"""Hardware manager wrapping LibreHardwareMonitor via pythonnet."""

from __future__ import annotations

import atexit
import logging
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


class SensorKind(IntEnum):
    """Mirrors LibreHardwareMonitor.Hardware.SensorType enum values."""

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
    """Represents a hardware sensor reading."""

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
    """Represents a controllable fan output."""

    hardware_name: str
    sensor_name: str
    identifier: str
    current_value: float | None  # Current control % (0-100)
    has_control: bool = False


@dataclass
class HardwareScanResult:
    """Result of a full hardware scan."""

    temperatures: list[SensorInfo] = field(default_factory=list)
    fans: list[SensorInfo] = field(default_factory=list)
    controls: list[ControlInfo] = field(default_factory=list)
    all_sensors: list[SensorInfo] = field(default_factory=list)


class HardwareManager:
    """Wraps LibreHardwareMonitorLib for reading sensors and controlling fans.

    Usage:
        with HardwareManager() as hw:
            result = hw.scan()
            for temp in result.temperatures:
                print(f"{temp.sensor_name}: {temp.value}°C")
    """

    def __init__(self):
        self._computer = None
        self._lhm = None
        self._controls: dict[str, object] = {}  # identifier -> ISensor with IControl

    def open(self):
        """Initialize and open the LHM computer instance."""
        from pysysfan.lhm import load_lhm

        self._lhm = load_lhm()

        self._computer = self._lhm.Computer()
        self._computer.IsMotherboardEnabled = True
        self._computer.IsCpuEnabled = True
        self._computer.IsGpuEnabled = True
        self._computer.IsStorageEnabled = True
        self._computer.IsNetworkEnabled = False  # Not needed for fan control
        self._computer.IsMemoryEnabled = True
        self._computer.IsPsuEnabled = False
        self._computer.IsBatteryEnabled = False
        self._computer.IsControllerEnabled = True

        self._computer.Open()

        # Register cleanup
        atexit.register(self._emergency_cleanup)

        logger.info("HardwareManager opened successfully")

    def close(self):
        """Close the computer instance and restore default fan control."""
        if self._computer is not None:
            self.restore_defaults()
            try:
                self._computer.Close()
            except Exception as e:
                logger.warning(f"Error closing LHM computer: {e}")
            self._computer = None
            self._controls.clear()
            logger.info("HardwareManager closed")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _ensure_open(self):
        """Raise if not opened."""
        if self._computer is None:
            raise RuntimeError("HardwareManager is not open. Call open() first.")

    def _update_all(self):
        """Update all hardware sensor readings."""
        self._ensure_open()
        for hw in self._computer.Hardware:
            hw.Update()
            for sub in hw.SubHardware:
                sub.Update()

    def _iter_sensors(self):
        """Iterate over all sensors across all hardware and sub-hardware."""
        self._ensure_open()
        for hw in self._computer.Hardware:
            for sensor in hw.Sensors:
                yield hw, sensor
            for sub in hw.SubHardware:
                for sensor in sub.Sensors:
                    yield sub, sensor

    def _sensor_type_name(self, sensor_type_value: int) -> str:
        """Convert a SensorType enum value to a human-readable name."""
        try:
            return SensorKind(sensor_type_value).name.title()
        except ValueError:
            return f"Unknown({sensor_type_value})"

    def _hardware_type_name(self, hw) -> str:
        """Get human-readable hardware type name."""
        try:
            return str(hw.HardwareType).split(".")[-1]
        except Exception:
            return "Unknown"

    def scan(self) -> HardwareScanResult:
        """Perform a full hardware scan, returning all sensors and controls.

        Updates all hardware readings before scanning.
        """
        self._update_all()

        result = HardwareScanResult()
        self._controls.clear()

        for hw, sensor in self._iter_sensors():
            sensor_type_val = int(sensor.SensorType)
            identifier = str(sensor.Identifier)

            info = SensorInfo(
                hardware_name=str(hw.Name),
                hardware_type=self._hardware_type_name(hw),
                sensor_name=str(sensor.Name),
                sensor_type=self._sensor_type_name(sensor_type_val),
                identifier=identifier,
                value=float(sensor.Value) if sensor.Value is not None else None,
                min_value=float(sensor.Min) if sensor.Min is not None else None,
                max_value=float(sensor.Max) if sensor.Max is not None else None,
            )
            result.all_sensors.append(info)

            if sensor_type_val == SensorKind.TEMPERATURE:
                result.temperatures.append(info)
            elif sensor_type_val == SensorKind.FAN:
                result.fans.append(info)
            elif sensor_type_val == SensorKind.CONTROL:
                has_ctrl = sensor.Control is not None
                ctrl_info = ControlInfo(
                    hardware_name=str(hw.Name),
                    sensor_name=str(sensor.Name),
                    identifier=identifier,
                    current_value=float(sensor.Value)
                    if sensor.Value is not None
                    else None,
                    has_control=has_ctrl,
                )
                result.controls.append(ctrl_info)

                if has_ctrl:
                    self._controls[identifier] = sensor

        return result

    def get_temperatures(self) -> list[SensorInfo]:
        """Get all current temperature readings."""
        self._update_all()
        temps = []
        for hw, sensor in self._iter_sensors():
            if int(sensor.SensorType) == SensorKind.TEMPERATURE:
                temps.append(
                    SensorInfo(
                        hardware_name=str(hw.Name),
                        hardware_type=self._hardware_type_name(hw),
                        sensor_name=str(sensor.Name),
                        sensor_type="Temperature",
                        identifier=str(sensor.Identifier),
                        value=float(sensor.Value) if sensor.Value is not None else None,
                    )
                )
        return temps

    def get_fan_speeds(self) -> list[SensorInfo]:
        """Get all current fan speed readings (RPM)."""
        self._update_all()
        fans = []
        for hw, sensor in self._iter_sensors():
            if int(sensor.SensorType) == SensorKind.FAN:
                fans.append(
                    SensorInfo(
                        hardware_name=str(hw.Name),
                        hardware_type=self._hardware_type_name(hw),
                        sensor_name=str(sensor.Name),
                        sensor_type="Fan",
                        identifier=str(sensor.Identifier),
                        value=float(sensor.Value) if sensor.Value is not None else None,
                    )
                )
        return fans

    def set_fan_speed(self, control_identifier: str, percent: float):
        """Set a fan speed by its control sensor identifier.

        Args:
            control_identifier: The LHM identifier string for the control sensor.
            percent: Speed percentage (0-100). Values are clamped.
        """
        self._ensure_open()

        # Make sure we have a fresh scan of controls
        if control_identifier not in self._controls:
            self.scan()

        if control_identifier not in self._controls:
            raise ValueError(
                f"Control '{control_identifier}' not found. "
                f"Available controls: {list(self._controls.keys())}"
            )

        percent = max(0.0, min(100.0, percent))
        sensor = self._controls[control_identifier]

        try:
            sensor.Control.SetSoftware(percent)
            logger.debug(f"Set {control_identifier} to {percent:.1f}%")
        except Exception as e:
            logger.error(f"Failed to set {control_identifier} to {percent}%: {e}")
            raise

    def restore_defaults(self):
        """Restore all fan controls to BIOS/default mode.

        This is critical for safety — allows the BIOS to resume automatic
        fan control when the daemon exits.
        """
        for identifier, sensor in self._controls.items():
            try:
                sensor.Control.SetDefault()
                logger.debug(f"Restored default control for {identifier}")
            except Exception as e:
                logger.warning(f"Failed to restore default for {identifier}: {e}")

    def _emergency_cleanup(self):
        """atexit handler to restore fan defaults on unexpected exit."""
        try:
            self.restore_defaults()
        except Exception:
            pass  # Best effort — we're exiting anyway
