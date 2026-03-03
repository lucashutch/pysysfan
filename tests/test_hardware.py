"""Tests for pysysfan.hardware — Data classes, enums, and manager validation."""

import pytest

from pysysfan.hardware import (
    SensorKind,
    SensorInfo,
    ControlInfo,
    HardwareScanResult,
    HardwareManager,
)


# ── SensorKind enum ──────────────────────────────────────────────────


class TestSensorKind:
    """Tests for the SensorKind enum."""

    def test_temperature_value(self):
        assert SensorKind.TEMPERATURE == 4

    def test_fan_value(self):
        assert SensorKind.FAN == 7

    def test_control_value(self):
        assert SensorKind.CONTROL == 9

    def test_voltage_value(self):
        assert SensorKind.VOLTAGE == 0

    def test_power_value(self):
        assert SensorKind.POWER == 2

    def test_all_values_unique(self):
        """All enum values should be unique."""
        values = [member.value for member in SensorKind]
        assert len(values) == len(set(values))


# ── Data classes ─────────────────────────────────────────────────────


class TestSensorInfo:
    """Tests for SensorInfo dataclass."""

    def test_creation(self):
        info = SensorInfo(
            hardware_name="CPU",
            hardware_type="Processor",
            sensor_name="Core #0",
            sensor_type="Temperature",
            identifier="/cpu/temperature/0",
            value=65.5,
        )
        assert info.hardware_name == "CPU"
        assert info.value == 65.5
        assert info.min_value is None
        assert info.max_value is None

    def test_with_min_max(self):
        info = SensorInfo(
            hardware_name="GPU",
            hardware_type="GpuNvidia",
            sensor_name="GPU Core",
            sensor_type="Temperature",
            identifier="/gpu/temperature/0",
            value=70.0,
            min_value=30.0,
            max_value=85.0,
        )
        assert info.min_value == 30.0
        assert info.max_value == 85.0


class TestControlInfo:
    """Tests for ControlInfo dataclass."""

    def test_creation(self):
        info = ControlInfo(
            hardware_name="Motherboard",
            sensor_name="Fan Control #1",
            identifier="/mb/control/0",
            current_value=75.0,
            has_control=True,
        )
        assert info.has_control is True
        assert info.current_value == 75.0

    def test_defaults(self):
        info = ControlInfo(
            hardware_name="MB",
            sensor_name="Fan",
            identifier="/mb/control/1",
            current_value=None,
        )
        assert info.has_control is False


class TestHardwareScanResult:
    """Tests for HardwareScanResult dataclass."""

    def test_empty_result(self):
        result = HardwareScanResult()
        assert result.temperatures == []
        assert result.fans == []
        assert result.controls == []
        assert result.all_sensors == []

    def test_with_data(self):
        temp = SensorInfo("CPU", "Processor", "Core", "Temp", "/cpu/t/0", 50.0)
        result = HardwareScanResult(temperatures=[temp])
        assert len(result.temperatures) == 1


# ── HardwareManager ──────────────────────────────────────────────────


class TestHardwareManager:
    """Tests for HardwareManager (non-LHM methods)."""

    def test_ensure_open_raises(self):
        """Should raise RuntimeError when hardware is not opened."""
        hw = HardwareManager()
        with pytest.raises(RuntimeError, match="not open"):
            hw._ensure_open()

    def test_context_manager_enter_exit(self):
        """Should support context manager protocol (open/close mocked)."""
        hw = HardwareManager()
        # Mock open/close to avoid LHM dependency
        hw.open = lambda: None
        hw.close = lambda: None
        hw._computer = True  # Prevent _ensure_open from raising
        with hw:
            pass  # Should not raise

    def test_sensor_type_name(self):
        """Should map enum values to human-readable names."""
        hw = HardwareManager()
        assert hw._sensor_type_name(SensorKind.TEMPERATURE) == "Temperature"
        assert hw._sensor_type_name(SensorKind.FAN) == "Fan"
        assert hw._sensor_type_name(SensorKind.CONTROL) == "Control"

    def test_sensor_type_name_unknown(self):
        """Should return 'Unknown(N)' for unmapped values."""
        hw = HardwareManager()
        result = hw._sensor_type_name(999)
        assert "999" in result or "Unknown" in result
