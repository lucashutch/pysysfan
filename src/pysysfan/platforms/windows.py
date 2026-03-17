"""Windows hardware implementation using LibreHardwareMonitor.

This module provides Windows-specific hardware access via the
LibreHardwareMonitor library (LHM) loaded through pythonnet.
"""

from __future__ import annotations

import atexit
import logging
from typing import TYPE_CHECKING

from pysysfan.platforms.base import (
    BaseHardwareManager,
    ControlInfo,
    HardwareScanResult,
    SensorInfo,
    SensorKind,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WindowsHardwareManager(BaseHardwareManager):
    """Windows hardware manager wrapping LibreHardwareMonitor via pythonnet.

    Usage:
        with WindowsHardwareManager() as hw:
            result = hw.scan()
            for temp in result.temperatures:
                print(f"{temp.sensor_name}: {temp.value}°C")
    """

    def __init__(self):
        super().__init__()  # Initialize base class (sets up _off_mode_fans)
        self._computer = None
        self._lhm = None
        self._controls: dict[str, object] = {}  # identifier -> ISensor with IControl

    def open(self) -> None:
        """Initialize and open the LHM computer instance."""
        import time as time_module

        t0 = time_module.perf_counter()
        from pysysfan.lhm import load_lhm

        t1 = time_module.perf_counter()
        logger.debug(f"[TIMING] load_lhm(): {t1 - t0:.3f}s")

        self._lhm = load_lhm()

        t2 = time_module.perf_counter()
        logger.debug(f"[TIMING] After load_lhm: {t2 - t0:.3f}s")

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

        t3 = time_module.perf_counter()
        logger.debug(f"[TIMING] Computer config set: {t3 - t0:.3f}s")

        self._computer.Open()

        t4 = time_module.perf_counter()
        logger.debug(f"[TIMING] Computer.Open(): {t4 - t0:.3f}s")

        # Register cleanup
        atexit.register(self._emergency_cleanup)

        logger.info("WindowsHardwareManager opened successfully")

    def close(self) -> None:
        """Close the computer instance and restore default fan control."""
        if self._computer is not None:
            self.restore_defaults()
            try:
                self._computer.Close()
            except Exception as e:
                logger.warning(f"Error closing LHM computer: {e}")
            self._computer = None
            self._controls.clear()
            logger.info("WindowsHardwareManager closed")

    def _ensure_open(self) -> None:
        """Raise if not opened."""
        if self._computer is None:
            raise RuntimeError("WindowsHardwareManager is not open. Call open() first.")

    def _update_all(self) -> None:
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
        import time as time_module

        t0 = time_module.perf_counter()

        self._update_all()
        t1 = time_module.perf_counter()
        logger.debug(f"[TIMING] _update_all(): {t1 - t0:.3f}s")

        result = HardwareScanResult()
        self._controls.clear()

        t2 = time_module.perf_counter()
        logger.debug(f"[TIMING] scan() init: {t2 - t0:.3f}s")

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

    def get_controls(self) -> list[ControlInfo]:
        """Get all controllable fan outputs.

        Returns:
            List of ControlInfo objects for fan controls.
        """
        self._update_all()
        controls = []
        for hw, sensor in self._iter_sensors():
            if int(sensor.SensorType) == SensorKind.CONTROL:
                try:
                    current_val = None
                    if hasattr(sensor, "Control") and sensor.Control is not None:
                        if hasattr(sensor.Control, "SoftwareValue"):
                            current_val = float(sensor.Control.SoftwareValue)

                    controls.append(
                        ControlInfo(
                            hardware_name=str(hw.Name),
                            sensor_name=str(sensor.Name),
                            identifier=str(sensor.Identifier),
                            current_value=current_val,
                            has_control=True,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Error reading control {sensor.Identifier}: {e}")
        return controls

    def set_fan_speed(
        self, control_identifier: str, percent: float, force_zero: bool = True
    ) -> None:
        """Set a fan speed by its control sensor identifier.

        Args:
            control_identifier: The LHM identifier string for the control sensor.
            percent: Speed percentage (0-100). Values are clamped.
            force_zero: If True, use SetSoftware(0) to force 0% duty cycle.
                       If False, use SetDefault() to let BIOS control (may apply minimum).

        When percent is 0 and force_zero is True, actively sets 0% duty cycle
        while keeping software control. Note: motherboard may still enforce
        minimum PWM duty cycle (typically 20-30%).
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

        sensor = self._controls[control_identifier]

        if percent <= 0:
            # Turn fan off - use SetSoftware(0) to maintain control at 0%
            # rather than SetDefault() which lets BIOS take over
            try:
                if force_zero:
                    # Actively control at 0% (motherboard may still enforce minimum)
                    sensor.Control.SetSoftware(0.0)
                    logger.debug(
                        f"Set {control_identifier} to 0% (SetSoftware, force_zero=True)"
                    )
                else:
                    # Release to BIOS control
                    sensor.Control.SetDefault()
                    logger.debug(f"Released {control_identifier} to BIOS (SetDefault)")
                self._off_mode_fans.add(control_identifier)
            except Exception as e:
                logger.error(f"Failed to turn off {control_identifier}: {e}")
                raise
        else:
            # Set normal speed (clamp to valid range)
            percent = min(100.0, percent)
            try:
                sensor.Control.SetSoftware(percent)
                self._off_mode_fans.discard(control_identifier)
                logger.debug(f"Set {control_identifier} to {percent:.1f}%")
            except Exception as e:
                logger.error(f"Failed to set {control_identifier} to {percent}%: {e}")
                raise

    def restore_defaults(self) -> None:
        """Restore all fan controls to BIOS/default mode.

        This is critical for safety - allows the BIOS to resume automatic
        fan control when the daemon exits.
        """
        for identifier, sensor in self._controls.items():
            try:
                sensor.Control.SetDefault()
                logger.debug(f"Restored default control for {identifier}")
            except Exception as e:
                logger.warning(f"Failed to restore default for {identifier}: {e}")

    def get_hardware_fingerprint(self) -> str:
        """Get a fingerprint of the current hardware configuration.

        Uses hardware identifiers and control sensor identifiers to detect changes.
        Sensor values are ignored to ensure stable fingerprints.
        The LHM version marker file is included so replacing the DLL invalidates
        the cache even when the hardware layout is identical.
        """
        import hashlib
        import logging

        from pysysfan.lhm import LHM_DIR

        logger = logging.getLogger(__name__)
        self._ensure_open()

        hw_ids: set[str] = set()
        control_ids: set[str] = set()

        for hw in self._computer.Hardware:
            hw_ids.add(f"{hw.HardwareType}|{hw.Name}")
            for sub in hw.SubHardware:
                hw_ids.add(f"{sub.HardwareType}|{sub.Name}")

        for hw, sensor in self._iter_sensors():
            sensor_type_val = int(sensor.SensorType)
            if sensor_type_val == SensorKind.CONTROL:
                control_ids.add(str(sensor.Identifier))

        # Include the LHM version so the cache is invalidated when the DLL is
        # replaced even if the hardware layout remains identical.
        version_file = LHM_DIR / ".lhm_version"
        try:
            lhm_version = version_file.read_text(encoding="utf-8").strip()
        except OSError:
            lhm_version = ""

        fingerprint_parts = (
            sorted(hw_ids) + sorted(control_ids) + [f"lhm:{lhm_version}"]
        )
        fingerprint_data = ";".join(fingerprint_parts)

        logger.debug(
            f"Fingerprint: {hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]}... ({len(hw_ids)} hw, {len(control_ids)} controls)"
        )
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()

    def _emergency_cleanup(self) -> None:
        """atexit handler to restore fan defaults on unexpected exit."""
        try:
            self.restore_defaults()
        except Exception:
            pass  # Best effort - we're exiting anyway
