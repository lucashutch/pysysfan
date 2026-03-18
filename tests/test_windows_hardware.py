"""Tests for pysysfan.platforms.windows — Windows hardware manager."""

from unittest.mock import MagicMock, patch

import pytest

from pysysfan.platforms.base import (
    HardwareScanResult,
    SensorKind,
)
from pysysfan.platforms.windows import WindowsHardwareManager


# ── Test Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def mock_lhm():
    """Create a mock LHM module."""
    with patch("pysysfan.lhm.load_lhm") as mock_load:
        mock_lhm_module = MagicMock()
        mock_computer = MagicMock()
        mock_lhm_module.Computer.return_value = mock_computer
        mock_load.return_value = mock_lhm_module
        yield mock_lhm_module, mock_computer


@pytest.fixture
def mock_hardware():
    """Create mock hardware objects."""
    hw = MagicMock()
    hw.Name = "Test CPU"
    hw.HardwareType = MagicMock()
    hw.HardwareType.__str__ = lambda self: "HardwareType.Cpu"
    hw.SubHardware = []
    return hw


@pytest.fixture
def mock_temp_sensor(mock_hardware):
    """Create a mock temperature sensor."""
    sensor = MagicMock()
    sensor.SensorType = SensorKind.TEMPERATURE
    sensor.Identifier = "/cpu/0/temp/0"
    sensor.Name = "Core 0"
    sensor.Value = 45.5
    sensor.Min = 30.0
    sensor.Max = 80.0
    return sensor


@pytest.fixture
def mock_fan_sensor(mock_hardware):
    """Create a mock fan sensor."""
    sensor = MagicMock()
    sensor.SensorType = SensorKind.FAN
    sensor.Identifier = "/mb/0/fan/0"
    sensor.Name = "Fan 1"
    sensor.Value = 1200.0
    sensor.Min = None
    sensor.Max = None
    return sensor


@pytest.fixture
def mock_control_sensor(mock_hardware):
    """Create a mock control sensor."""
    sensor = MagicMock()
    sensor.SensorType = SensorKind.CONTROL
    sensor.Identifier = "/mb/0/control/0"
    sensor.Name = "Fan Control 1"
    sensor.Value = 50.0
    sensor.Min = None
    sensor.Max = None
    sensor.Control = MagicMock()
    return sensor


# ── Initialization Tests ─────────────────────────────────────────────


class TestWindowsHardwareManagerInit:
    """Tests for WindowsHardwareManager initialization."""

    def test_init_creates_empty_controls(self):
        """Should initialize with empty controls dict."""
        hw = WindowsHardwareManager()
        assert hw._controls == {}
        assert hw._computer is None
        assert hw._lhm is None

    def test_inherits_off_mode_fans(self):
        """Should inherit _off_mode_fans from base class."""
        hw = WindowsHardwareManager()
        assert hasattr(hw, "_off_mode_fans")
        assert isinstance(hw._off_mode_fans, set)


# ── Open/Close Tests ─────────────────────────────────────────────────


class TestWindowsHardwareManagerOpen:
    """Tests for open() method."""

    def test_open_initializes_computer(self, mock_lhm):
        """Should initialize and open LHM computer."""
        mock_lhm_module, mock_computer = mock_lhm
        hw = WindowsHardwareManager()

        hw.open()

        assert hw._lhm is mock_lhm_module
        assert hw._computer is mock_computer
        mock_lhm_module.Computer.assert_called_once()
        mock_computer.Open.assert_called_once()

    def test_open_configures_hardware_types(self, mock_lhm):
        """Should enable required hardware types."""
        _, mock_computer = mock_lhm
        hw = WindowsHardwareManager()

        hw.open()

        assert mock_computer.IsMotherboardEnabled is True
        assert mock_computer.IsCpuEnabled is True
        assert mock_computer.IsGpuEnabled is True
        assert mock_computer.IsStorageEnabled is True
        assert mock_computer.IsMemoryEnabled is True
        assert mock_computer.IsControllerEnabled is True
        assert mock_computer.IsNetworkEnabled is False
        assert mock_computer.IsPsuEnabled is False
        assert mock_computer.IsBatteryEnabled is False

    def test_open_registers_atexit(self, mock_lhm):
        """Should register emergency cleanup on atexit."""
        with patch("atexit.register") as mock_register:
            hw = WindowsHardwareManager()
            hw.open()

            mock_register.assert_called_once_with(hw._emergency_cleanup)


class TestWindowsHardwareManagerClose:
    """Tests for close() method."""

    def test_close_restores_defaults(self, mock_lhm):
        """Should restore fan defaults before closing."""
        _, mock_computer = mock_lhm
        hw = WindowsHardwareManager()
        hw.open()

        with patch.object(hw, "restore_defaults") as mock_restore:
            hw.close()
            mock_restore.assert_called_once()

    def test_close_clears_controls(self, mock_lhm):
        """Should clear controls dict on close."""
        _, mock_computer = mock_lhm
        hw = WindowsHardwareManager()
        hw.open()
        hw._controls = {"/test": MagicMock()}

        with patch.object(hw, "restore_defaults"):
            hw.close()

        assert hw._controls == {}

    def test_close_handles_computer_close_error(self, mock_lhm):
        """Should handle errors when closing computer."""
        _, mock_computer = mock_lhm
        mock_computer.Close.side_effect = Exception("Close failed")

        hw = WindowsHardwareManager()
        hw.open()

        with patch.object(hw, "restore_defaults"):
            # Should not raise
            hw.close()

    def test_close_when_not_opened(self):
        """Should handle close when computer was never opened."""
        hw = WindowsHardwareManager()
        # Should not raise
        hw.close()


# ── Helper Method Tests ──────────────────────────────────────────────


class TestWindowsHardwareManagerEnsureOpen:
    """Tests for _ensure_open() method."""

    def test_raises_when_not_opened(self):
        """Should raise RuntimeError when not opened."""
        hw = WindowsHardwareManager()
        with pytest.raises(RuntimeError, match="not open"):
            hw._ensure_open()

    def test_passes_when_opened(self, mock_lhm):
        """Should not raise when opened."""
        _, mock_computer = mock_lhm
        hw = WindowsHardwareManager()
        hw.open()

        # Should not raise
        hw._ensure_open()


class TestWindowsHardwareManagerUpdateAll:
    """Tests for _update_all() method."""

    def test_updates_all_hardware(self, mock_lhm):
        """Should update all hardware and sub-hardware."""
        _, mock_computer = mock_lhm
        hw1 = MagicMock()
        hw2 = MagicMock()
        sub_hw = MagicMock()
        hw1.SubHardware = [sub_hw]
        hw2.SubHardware = []
        mock_computer.Hardware = [hw1, hw2]

        hw = WindowsHardwareManager()
        hw.open()
        hw._update_all()

        hw1.Update.assert_called_once()
        hw2.Update.assert_called_once()
        sub_hw.Update.assert_called_once()

    def test_refresh_updates_only_required_hardware(self, mock_lhm):
        """Configured sensor scope should limit per-poll Update() calls."""
        _, mock_computer = mock_lhm

        hw1 = MagicMock()
        hw2 = MagicMock()
        hw1.SubHardware = []
        hw2.SubHardware = []

        sensor1 = MagicMock()
        sensor1.Identifier = "/cpu/0/temp/0"
        sensor2 = MagicMock()
        sensor2.Identifier = "/gpu/0/temp/0"
        hw1.Sensors = [sensor1]
        hw2.Sensors = [sensor2]
        mock_computer.Hardware = [hw1, hw2]

        hw = WindowsHardwareManager()
        hw.open()
        hw.set_required_sensor_ids({"/cpu/0/temp/0"})

        hw.refresh()

        hw1.Update.assert_called_once()
        hw2.Update.assert_not_called()

    def test_refresh_without_scope_updates_all_hardware(self, mock_lhm):
        """Without configured scope, refresh should behave like full update."""
        _, mock_computer = mock_lhm

        hw1 = MagicMock()
        hw2 = MagicMock()
        hw1.SubHardware = []
        hw2.SubHardware = []
        hw1.Sensors = []
        hw2.Sensors = []
        mock_computer.Hardware = [hw1, hw2]

        hw = WindowsHardwareManager()
        hw.open()

        hw.refresh()

        hw1.Update.assert_called_once()
        hw2.Update.assert_called_once()


class TestWindowsHardwareManagerIterSensors:
    """Tests for _iter_sensors() method."""

    def test_iterates_all_sensors(self, mock_lhm):
        """Should yield all sensors from hardware and sub-hardware."""
        _, mock_computer = mock_lhm
        hw1 = MagicMock()
        hw2 = MagicMock()
        sub_hw = MagicMock()

        sensor1 = MagicMock()
        sensor2 = MagicMock()
        sensor3 = MagicMock()

        hw1.Sensors = [sensor1]
        hw1.SubHardware = [sub_hw]
        sub_hw.Sensors = [sensor2]
        hw2.Sensors = [sensor3]
        hw2.SubHardware = []

        mock_computer.Hardware = [hw1, hw2]

        hw = WindowsHardwareManager()
        hw.open()
        sensors = list(hw._iter_sensors())

        assert len(sensors) == 3
        assert sensors[0] == (hw1, sensor1)
        assert sensors[1] == (sub_hw, sensor2)
        assert sensors[2] == (hw2, sensor3)


class TestWindowsHardwareManagerSensorTypeName:
    """Tests for _sensor_type_name() method."""

    def test_known_sensor_types(self, mock_lhm):
        """Should return human-readable names for known types."""
        _, _ = mock_lhm
        hw = WindowsHardwareManager()
        hw.open()

        assert hw._sensor_type_name(SensorKind.TEMPERATURE) == "Temperature"
        assert hw._sensor_type_name(SensorKind.FAN) == "Fan"
        assert hw._sensor_type_name(SensorKind.CONTROL) == "Control"
        assert hw._sensor_type_name(SensorKind.VOLTAGE) == "Voltage"

    def test_unknown_sensor_type(self, mock_lhm):
        """Should return Unknown(N) for unknown types."""
        _, _ = mock_lhm
        hw = WindowsHardwareManager()
        hw.open()

        result = hw._sensor_type_name(999)
        assert "999" in result
        assert "Unknown" in result


class TestWindowsHardwareManagerHardwareTypeName:
    """Tests for _hardware_type_name() method."""

    def test_valid_hardware_type(self, mock_lhm):
        """Should extract type name from HardwareType."""
        _, _ = mock_lhm
        hw = MagicMock()
        hw.HardwareType.__str__ = lambda self: "HardwareType.Cpu"

        manager = WindowsHardwareManager()
        manager.open()

        result = manager._hardware_type_name(hw)
        assert result == "Cpu"

    def test_invalid_hardware_type(self, mock_lhm):
        """Should return Unknown for errors."""
        _, _ = mock_lhm
        hw = MagicMock()
        hw.HardwareType.__str__ = lambda self: 1 / 0  # Raises exception

        manager = WindowsHardwareManager()
        manager.open()

        result = manager._hardware_type_name(hw)
        assert result == "Unknown"


# ── Scan Tests ───────────────────────────────────────────────────────


class TestWindowsHardwareManagerScan:
    """Tests for scan() method."""

    def test_scan_returns_result(self, mock_lhm, mock_hardware, mock_temp_sensor):
        """Should return HardwareScanResult with sensors."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_temp_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        result = hw.scan()

        assert isinstance(result, HardwareScanResult)
        assert len(result.temperatures) == 1
        assert len(result.all_sensors) == 1

    def test_scan_categorizes_sensors(
        self,
        mock_lhm,
        mock_hardware,
        mock_temp_sensor,
        mock_fan_sensor,
        mock_control_sensor,
    ):
        """Should categorize sensors by type."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_temp_sensor, mock_fan_sensor, mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        result = hw.scan()

        assert len(result.temperatures) == 1
        assert len(result.fans) == 1
        assert len(result.controls) == 1
        assert len(result.all_sensors) == 3

    def test_scan_populates_control_dict(
        self, mock_lhm, mock_hardware, mock_control_sensor
    ):
        """Should populate _controls dict for sensors with Control."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        hw.scan()

        assert "/mb/0/control/0" in hw._controls
        assert hw._controls["/mb/0/control/0"] is mock_control_sensor

    def test_scan_handles_none_values(self, mock_lhm, mock_hardware):
        """Should handle None sensor values gracefully."""
        _, mock_computer = mock_lhm
        sensor = MagicMock()
        sensor.SensorType = SensorKind.TEMPERATURE
        sensor.Identifier = "/test"
        sensor.Name = "Test"
        sensor.Value = None
        sensor.Min = None
        sensor.Max = None
        mock_hardware.Sensors = [sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        result = hw.scan()

        assert len(result.temperatures) == 1
        assert result.temperatures[0].value is None

    def test_scan_clears_existing_controls(
        self, mock_lhm, mock_hardware, mock_control_sensor
    ):
        """Should clear _controls before populating."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        hw._controls = {"/old": MagicMock()}
        hw.scan()

        assert "/old" not in hw._controls
        assert "/mb/0/control/0" in hw._controls


# ── Get Temperatures Tests ───────────────────────────────────────────


class TestWindowsHardwareManagerGetTemperatures:
    """Tests for get_temperatures() method."""

    def test_returns_temperature_sensors(
        self, mock_lhm, mock_hardware, mock_temp_sensor
    ):
        """Should return only temperature sensors."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_temp_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        temps = hw.get_temperatures()

        assert len(temps) == 1
        assert temps[0].sensor_type == "Temperature"

    def test_ignores_other_sensor_types(self, mock_lhm, mock_hardware, mock_fan_sensor):
        """Should ignore non-temperature sensors."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_fan_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        temps = hw.get_temperatures()

        assert len(temps) == 0


# ── Get Fan Speeds Tests ─────────────────────────────────────────────


class TestWindowsHardwareManagerGetFanSpeeds:
    """Tests for get_fan_speeds() method."""

    def test_returns_fan_sensors(self, mock_lhm, mock_hardware, mock_fan_sensor):
        """Should return only fan sensors."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_fan_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        fans = hw.get_fan_speeds()

        assert len(fans) == 1
        assert fans[0].sensor_type == "Fan"

    def test_ignores_other_sensor_types(
        self, mock_lhm, mock_hardware, mock_temp_sensor
    ):
        """Should ignore non-fan sensors."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_temp_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        fans = hw.get_fan_speeds()

        assert len(fans) == 0


# ── Set Fan Speed Tests ──────────────────────────────────────────────


class TestWindowsHardwareManagerSetFanSpeed:
    """Tests for set_fan_speed() method."""

    def test_set_zero_with_force_zero(
        self, mock_lhm, mock_hardware, mock_control_sensor
    ):
        """Should use SetSoftware(0) when force_zero=True."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        hw.scan()

        hw.set_fan_speed("/mb/0/control/0", 0, force_zero=True)

        mock_control_sensor.Control.SetSoftware.assert_called_once_with(0.0)
        assert "/mb/0/control/0" in hw._off_mode_fans

    def test_set_zero_without_force_zero(
        self, mock_lhm, mock_hardware, mock_control_sensor
    ):
        """Should use SetDefault() when force_zero=False."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        hw.scan()

        hw.set_fan_speed("/mb/0/control/0", 0, force_zero=False)

        mock_control_sensor.Control.SetDefault.assert_called_once()
        assert "/mb/0/control/0" in hw._off_mode_fans

    def test_set_positive_speed(self, mock_lhm, mock_hardware, mock_control_sensor):
        """Should set positive speed with SetSoftware."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        hw.scan()

        hw.set_fan_speed("/mb/0/control/0", 75.0)

        mock_control_sensor.Control.SetSoftware.assert_called_once_with(75.0)
        assert "/mb/0/control/0" not in hw._off_mode_fans

    def test_clamps_to_100(self, mock_lhm, mock_hardware, mock_control_sensor):
        """Should clamp values above 100 to 100."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        hw.scan()

        hw.set_fan_speed("/mb/0/control/0", 150.0)

        mock_control_sensor.Control.SetSoftware.assert_called_once_with(100.0)

    def test_triggers_scan_if_control_not_found(
        self, mock_lhm, mock_hardware, mock_control_sensor
    ):
        """Should scan if control identifier not in _controls."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        # Don't scan initially

        with patch.object(hw, "scan") as mock_scan:
            mock_scan.return_value = HardwareScanResult()
            with pytest.raises(ValueError, match="not found"):
                hw.set_fan_speed("/nonexistent", 50)

            mock_scan.assert_called_once()

    def test_raises_if_control_still_not_found(
        self, mock_lhm, mock_hardware, mock_control_sensor
    ):
        """Should raise ValueError if control not found after scan."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()

        with pytest.raises(ValueError, match="not found"):
            hw.set_fan_speed("/nonexistent", 50)

    def test_handles_set_error(self, mock_lhm, mock_hardware, mock_control_sensor):
        """Should raise exception on set failure."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]
        mock_control_sensor.Control.SetSoftware.side_effect = Exception("Set failed")

        hw = WindowsHardwareManager()
        hw.open()
        hw.scan()

        with pytest.raises(Exception, match="Set failed"):
            hw.set_fan_speed("/mb/0/control/0", 50)


# ── Restore Defaults Tests ───────────────────────────────────────────


class TestWindowsHardwareManagerRestoreDefaults:
    """Tests for restore_defaults() method."""

    def test_restores_all_controls(self, mock_lhm, mock_hardware, mock_control_sensor):
        """Should call SetDefault on all controls."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        hw.scan()

        hw.restore_defaults()

        mock_control_sensor.Control.SetDefault.assert_called_once()

    def test_handles_restore_error(self, mock_lhm, mock_hardware, mock_control_sensor):
        """Should handle errors when restoring defaults."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]
        mock_control_sensor.Control.SetDefault.side_effect = Exception("Restore failed")

        hw = WindowsHardwareManager()
        hw.open()
        hw.scan()

        # Should not raise
        hw.restore_defaults()

    def test_empty_controls(self, mock_lhm):
        """Should handle empty controls dict."""
        _, _ = mock_lhm
        hw = WindowsHardwareManager()
        hw.open()

        # Should not raise
        hw.restore_defaults()


# ── Hardware Fingerprint Tests ───────────────────────────────────────


class TestWindowsHardwareManagerGetHardwareFingerprint:
    """Tests for get_hardware_fingerprint() method."""

    def test_returns_fingerprint_string(self, mock_lhm, mock_hardware):
        """Should return a hex string fingerprint."""
        _, mock_computer = mock_lhm
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        fingerprint = hw.get_hardware_fingerprint()

        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64  # SHA256 hex

    def test_includes_hardware_info(self, mock_lhm):
        """Should include hardware type and name."""
        _, mock_computer = mock_lhm
        hw1 = MagicMock()
        hw1.HardwareType = "Cpu"
        hw1.Name = "Intel CPU"
        hw1.SubHardware = []
        mock_computer.Hardware = [hw1]

        hw = WindowsHardwareManager()
        hw.open()
        fingerprint1 = hw.get_hardware_fingerprint()

        # Same hardware should give same fingerprint
        fingerprint2 = hw.get_hardware_fingerprint()
        assert fingerprint1 == fingerprint2

    def test_includes_control_identifiers(
        self, mock_lhm, mock_hardware, mock_control_sensor
    ):
        """Should include control sensor identifiers."""
        _, mock_computer = mock_lhm
        mock_hardware.Sensors = [mock_control_sensor]
        mock_computer.Hardware = [mock_hardware]

        hw = WindowsHardwareManager()
        hw.open()
        fp1 = hw.get_hardware_fingerprint()

        # Add another control
        control2 = MagicMock()
        control2.SensorType = SensorKind.CONTROL
        control2.Identifier = "/mb/0/control/1"
        mock_hardware.Sensors = [mock_control_sensor, control2]

        fp2 = hw.get_hardware_fingerprint()

        # Different controls should give different fingerprint
        assert fp1 != fp2

    def test_raises_when_not_opened(self):
        """Should raise when not opened."""
        hw = WindowsHardwareManager()
        with pytest.raises(RuntimeError, match="not open"):
            hw.get_hardware_fingerprint()


# ── Emergency Cleanup Tests ──────────────────────────────────────────


class TestWindowsHardwareManagerEmergencyCleanup:
    """Tests for _emergency_cleanup() method."""

    def test_calls_restore_defaults(self, mock_lhm):
        """Should call restore_defaults."""
        _, _ = mock_lhm
        hw = WindowsHardwareManager()
        hw.open()

        with patch.object(hw, "restore_defaults") as mock_restore:
            hw._emergency_cleanup()
            mock_restore.assert_called_once()

    def test_handles_errors_silently(self, mock_lhm):
        """Should silently handle any errors."""
        _, _ = mock_lhm
        hw = WindowsHardwareManager()
        hw.open()

        with patch.object(
            hw, "restore_defaults", side_effect=Exception("Cleanup failed")
        ):
            # Should not raise
            hw._emergency_cleanup()


# ── Context Manager Tests ────────────────────────────────────────────


class TestWindowsHardwareManagerContextManager:
    """Tests for context manager protocol."""

    def test_enters_and_exits(self, mock_lhm):
        """Should support with statement."""
        _, mock_computer = mock_lhm
        hw = WindowsHardwareManager()

        with (
            patch.object(hw, "open") as mock_open,
            patch.object(hw, "close") as mock_close,
        ):
            with hw:
                mock_open.assert_called_once()
            mock_close.assert_called_once()

    def test_exception_propagates(self, mock_lhm):
        """Should propagate exceptions and still close."""
        _, mock_computer = mock_lhm
        hw = WindowsHardwareManager()

        with patch.object(hw, "open"), patch.object(hw, "close") as mock_close:
            with pytest.raises(ValueError, match="test error"):
                with hw:
                    raise ValueError("test error")
            mock_close.assert_called_once()
