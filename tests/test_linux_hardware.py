"""Tests for Linux hardware implementation.

These tests mock the pysensors library and sysfs interface to test
LinuxHardwareManager without requiring actual hardware.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from pysysfan.platforms.base import (
    HardwareScanResult,
    SensorKind,
)
from pysysfan.platforms.linux import LinuxHardwareManager


@pytest.fixture
def mock_sensors_module():
    """Create a mock sensors module."""
    mock = MagicMock()
    mock.init = MagicMock()
    mock.cleanup = MagicMock()
    return mock


@pytest.fixture
def mock_chip():
    """Create a mock sensors chip."""
    chip = MagicMock()
    chip.__str__ = Mock(return_value="coretemp-isa-0000")
    return chip


@pytest.fixture
def mock_subfeature():
    """Create a mock sensors subfeature."""
    subfeature = MagicMock()
    subfeature.name = "temp1_input"
    subfeature.get_value = Mock(return_value=45000.0)  # 45°C in millidegrees
    return subfeature


@pytest.fixture
def mock_feature(mock_subfeature):
    """Create a mock sensors feature."""
    feature = MagicMock()
    feature.name = "Core 0"
    feature.__iter__ = Mock(return_value=iter([mock_subfeature]))
    return feature


class TestLinuxHardwareManagerInitialization:
    """Tests for hardware manager initialization."""

    def test_initializes_sensors_library(self, mock_sensors_module):
        """Should initialize pysensors on open."""
        with patch.dict("sys.modules", {"sensors": mock_sensors_module}):
            hw = LinuxHardwareManager()
            hw.open()
            mock_sensors_module.init.assert_called_once()

    def test_raises_on_missing_pysensors(self):
        """Should raise RuntimeError if pysensors not installed."""
        with patch.dict("sys.modules", {"sensors": None}):
            hw = LinuxHardwareManager()
            with pytest.raises(RuntimeError) as exc_info:
                hw.open()
            assert "pysensors" in str(exc_info.value).lower()

    def test_cleans_up_on_close(self, mock_sensors_module):
        """Should cleanup sensors on close."""
        with patch.dict("sys.modules", {"sensors": mock_sensors_module}):
            hw = LinuxHardwareManager()
            hw.open()
            hw.close()
            mock_sensors_module.cleanup.assert_called_once()


class TestLinuxHardwareManagerScanning:
    """Tests for hardware scanning."""

    def test_scan_finds_temperatures(
        self, mock_sensors_module, mock_chip, mock_feature
    ):
        """Should find temperature sensors during scan."""
        mock_chip.__iter__ = Mock(return_value=iter([mock_feature]))
        mock_sensors_module.iter_detected_chips = Mock(return_value=[mock_chip])

        with patch.dict("sys.modules", {"sensors": mock_sensors_module}):
            hw = LinuxHardwareManager()
            hw.open()

            # Mock hwmon path discovery
            hw._chips = {"coretemp-isa-0000": {"chip": mock_chip, "hwmon_path": None}}

            result = hw.scan()
            assert isinstance(result, HardwareScanResult)

    def test_classify_sensor_temperature(self):
        """Should classify temperature sensors correctly."""
        hw = LinuxHardwareManager()
        type_name, kind = hw._classify_sensor("temp1_input")
        assert type_name == "Temperature"
        assert kind == SensorKind.TEMPERATURE

    def test_classify_sensor_fan(self):
        """Should classify fan sensors correctly."""
        hw = LinuxHardwareManager()
        type_name, kind = hw._classify_sensor("fan1_input")
        assert type_name == "Fan"
        assert kind == SensorKind.FAN

    def test_classify_sensor_voltage(self):
        """Should classify voltage sensors correctly."""
        hw = LinuxHardwareManager()
        type_name, kind = hw._classify_sensor("in0_input")
        assert type_name == "Voltage"
        assert kind == SensorKind.VOLTAGE


class TestLinuxHardwareManagerThinkPad:
    """Tests for ThinkPad-specific functionality."""

    def test_detects_thinkpad_from_dmi(self):
        """Should detect ThinkPad from DMI product name."""
        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("pathlib.Path.read_text") as mock_read,
        ):
            mock_exists.return_value = True
            mock_read.return_value = "ThinkPad P14s Gen 3"

            hw = LinuxHardwareManager()
            is_thinkpad = hw._detect_thinkpad()
            assert is_thinkpad is True

    def test_does_not_detect_non_thinkpad(self):
        """Should not detect non-ThinkPad systems."""
        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("pathlib.Path.read_text") as mock_read,
        ):
            mock_exists.return_value = True
            mock_read.return_value = "Dell XPS 13"

            hw = LinuxHardwareManager()
            is_thinkpad = hw._detect_thinkpad()
            assert is_thinkpad is False

    def test_thinkpad_control_added_when_available(self, mock_sensors_module, tmp_path):
        """Should add ThinkPad control when /proc/acpi/ibm/fan exists."""
        with (
            patch.dict("sys.modules", {"sensors": mock_sensors_module}),
            patch("pysysfan.platforms.linux.THINKPAD_FAN_PATH") as mock_path,
        ):
            mock_path.exists = Mock(return_value=True)

            hw = LinuxHardwareManager()
            hw._is_thinkpad = True
            hw._sensors = mock_sensors_module
            hw._discover_hardware()

            assert "thinkpad/fan" in hw._controls


class TestLinuxHardwareManagerPWMControl:
    """Tests for PWM fan control."""

    def test_pwm_control_discovery(self, tmp_path):
        """Should discover PWM controls in hwmon directory."""
        hw = LinuxHardwareManager()

        # Create mock hwmon structure
        hwmon_dir = tmp_path / "hwmon0"
        hwmon_dir.mkdir()
        (hwmon_dir / "name").write_text("nct6775")
        (hwmon_dir / "pwm1").write_text("128")
        (hwmon_dir / "pwm1_enable").write_text("0")

        hw._discover_pwm_controls(hwmon_dir, "nct6775")

        assert "hwmon0/pwm1" in hw._controls
        assert hw._controls["hwmon0/pwm1"]["type"] == "pwm"

    def test_set_pwm_speed(self, tmp_path):
        """Should write PWM value to sysfs."""
        hw = LinuxHardwareManager()

        pwm_path = tmp_path / "pwm1"
        pwm_path.write_text("0")
        enable_path = tmp_path / "pwm1_enable"
        enable_path.write_text("0")

        hw._controls = {
            "hwmon0/pwm1": {
                "type": "pwm",
                "path": pwm_path,
                "enable_path": enable_path,
            }
        }

        hw.set_fan_speed("hwmon0/pwm1", 50.0)

        # 50% = 128 (0-255 range)
        assert pwm_path.read_text() == "128"
        assert enable_path.read_text() == "1"

    def test_restore_pwm_default(self, tmp_path):
        """Should restore PWM to BIOS control."""
        hw = LinuxHardwareManager()

        enable_path = tmp_path / "pwm1_enable"
        enable_path.write_text("1")

        control_info = {
            "type": "pwm",
            "enable_path": enable_path,
        }

        hw._restore_pwm_default(control_info)
        assert enable_path.read_text() == "0"


class TestLinuxHardwareManagerThinkPadControl:
    """Tests for ThinkPad fan control."""

    def test_set_thinkpad_speed_mapping(self, tmp_path):
        """Should map percentage to ThinkPad levels."""
        hw = LinuxHardwareManager()

        fan_path = tmp_path / "fan"
        fan_path.write_text("status:\t\t0\n")

        with patch("pysysfan.platforms.linux.THINKPAD_FAN_PATH", fan_path):
            hw._set_thinkpad_speed(0)
            assert "level 0" in fan_path.read_text()

    def test_restore_thinkpad_default(self, tmp_path):
        """Should restore ThinkPad to auto control."""
        hw = LinuxHardwareManager()

        fan_path = tmp_path / "fan"
        fan_path.write_text("status:\t\t0\n")

        with patch("pysysfan.platforms.linux.THINKPAD_FAN_PATH", fan_path):
            hw._restore_thinkpad_default()
            assert "level auto" in fan_path.read_text()


class TestLinuxHardwareManagerErrors:
    """Tests for error handling."""

    def test_set_fan_speed_unknown_control(self):
        """Should raise ValueError for unknown control."""
        hw = LinuxHardwareManager()
        hw._controls = {}

        with pytest.raises(ValueError) as exc_info:
            hw.set_fan_speed("unknown/control", 50.0)
        assert "not found" in str(exc_info.value)

    def test_set_pwm_speed_permission_denied(self, tmp_path):
        """Should raise PermissionError on permission denied."""
        hw = LinuxHardwareManager()

        pwm_path = tmp_path / "pwm1"
        pwm_path.write_text("0")
        # Make file read-only
        pwm_path.chmod(0o444)

        enable_path = tmp_path / "pwm1_enable"
        enable_path.write_text("1")

        hw._controls = {
            "hwmon0/pwm1": {
                "type": "pwm",
                "path": pwm_path,
                "enable_path": enable_path,
            }
        }

        with pytest.raises(PermissionError):
            hw.set_fan_speed("hwmon0/pwm1", 50.0)

        # Cleanup
        pwm_path.chmod(0o644)
