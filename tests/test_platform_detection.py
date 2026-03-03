"""Tests for platform detection and hardware abstraction layer."""

from unittest.mock import patch

import pytest

from pysysfan.platforms import (
    detect_platform,
    get_hardware_manager,
    get_service_manager,
    PlatformNotSupportedError,
)
from pysysfan.platforms.base import (
    BaseHardwareManager,
    ControlInfo,
    HardwareScanResult,
    SensorInfo,
    SensorKind,
)


class TestDetectPlatform:
    """Tests for platform detection."""

    def test_detects_windows(self):
        """Should detect Windows platform."""
        with patch("sys.platform", "win32"):
            assert detect_platform() == "windows"

    def test_detects_windows_with_suffix(self):
        """Should detect Windows even with platform suffix."""
        with patch("sys.platform", "win64"):
            assert detect_platform() == "windows"

    def test_detects_linux(self):
        """Should detect Linux platform."""
        with patch("sys.platform", "linux"):
            assert detect_platform() == "linux"

    def test_detects_linux_with_suffix(self):
        """Should detect Linux even with platform suffix."""
        with patch("sys.platform", "linux2"):
            assert detect_platform() == "linux"

    def test_raises_on_unsupported_platform(self):
        """Should raise on unsupported platforms like macOS."""
        with patch("sys.platform", "darwin"):
            with pytest.raises(PlatformNotSupportedError) as exc_info:
                detect_platform()
            assert "darwin" in str(exc_info.value).lower()


class TestGetHardwareManager:
    """Tests for hardware manager factory."""

    def test_returns_windows_manager_on_windows(self):
        """Should return WindowsHardwareManager on Windows."""
        with patch("sys.platform", "win32"):
            manager_class = get_hardware_manager()
            from pysysfan.platforms.windows import WindowsHardwareManager

            assert manager_class is WindowsHardwareManager

    def test_returns_linux_manager_on_linux(self):
        """Should return LinuxHardwareManager on Linux."""
        with patch("sys.platform", "linux"):
            manager_class = get_hardware_manager()
            from pysysfan.platforms.linux import LinuxHardwareManager

            assert manager_class is LinuxHardwareManager

    def test_raises_on_unsupported_platform(self):
        """Should raise on unsupported platforms."""
        with patch("sys.platform", "darwin"):
            with pytest.raises(PlatformNotSupportedError):
                get_hardware_manager()


class TestGetServiceManager:
    """Tests for service manager factory."""

    def test_returns_windows_service_on_windows(self):
        """Should return Windows service module on Windows."""
        with patch("sys.platform", "win32"):
            service_module = get_service_manager()
            from pysysfan.platforms import windows_service

            assert service_module is windows_service

    def test_returns_linux_service_on_linux(self):
        """Should return Linux service module on Linux."""
        with patch("sys.platform", "linux"):
            service_module = get_service_manager()
            from pysysfan.platforms import linux_service

            assert service_module is linux_service


class TestBaseHardwareManager:
    """Tests for abstract base class."""

    def test_is_abstract(self):
        """BaseHardwareManager should be abstract."""
        with pytest.raises(TypeError):
            BaseHardwareManager()

    def test_subclass_must_implement_methods(self):
        """Subclasses must implement all abstract methods."""

        class IncompleteManager(BaseHardwareManager):
            pass

        with pytest.raises(TypeError) as exc_info:
            IncompleteManager()

        # Should mention missing abstract methods
        error_msg = str(exc_info.value)
        assert "abstract" in error_msg.lower()


class TestSensorKind:
    """Tests for SensorKind enum."""

    def test_temperature_value(self):
        """TEMPERATURE should have value 4."""
        assert SensorKind.TEMPERATURE == 4

    def test_fan_value(self):
        """FAN should have value 7."""
        assert SensorKind.FAN == 7

    def test_control_value(self):
        """CONTROL should have value 9."""
        assert SensorKind.CONTROL == 9


class TestSensorInfo:
    """Tests for SensorInfo dataclass."""

    def test_creation(self):
        """Should create SensorInfo with required fields."""
        sensor = SensorInfo(
            hardware_name="CPU",
            hardware_type="Cpu",
            sensor_name="Core 1",
            sensor_type="Temperature",
            identifier="/cpu/0/temp/0",
            value=45.5,
        )
        assert sensor.hardware_name == "CPU"
        assert sensor.value == 45.5
        assert sensor.min_value is None  # Optional
        assert sensor.max_value is None  # Optional

    def test_with_optional_fields(self):
        """Should accept optional min/max values."""
        sensor = SensorInfo(
            hardware_name="CPU",
            hardware_type="Cpu",
            sensor_name="Core 1",
            sensor_type="Temperature",
            identifier="/cpu/0/temp/0",
            value=45.5,
            min_value=30.0,
            max_value=80.0,
        )
        assert sensor.min_value == 30.0
        assert sensor.max_value == 80.0


class TestControlInfo:
    """Tests for ControlInfo dataclass."""

    def test_creation(self):
        """Should create ControlInfo with required fields."""
        control = ControlInfo(
            hardware_name="Motherboard",
            sensor_name="Fan 1",
            identifier="/motherboard/control/0",
            current_value=50.0,
            has_control=True,
        )
        assert control.has_control is True
        assert control.current_value == 50.0

    def test_default_has_control(self):
        """has_control should default to False."""
        control = ControlInfo(
            hardware_name="Motherboard",
            sensor_name="Fan 1",
            identifier="/motherboard/control/0",
            current_value=None,
        )
        assert control.has_control is False


class TestHardwareScanResult:
    """Tests for HardwareScanResult dataclass."""

    def test_default_empty_lists(self):
        """Should have empty lists by default."""
        result = HardwareScanResult()
        assert result.temperatures == []
        assert result.fans == []
        assert result.controls == []
        assert result.all_sensors == []

    def test_can_add_sensors(self):
        """Should be able to add sensors to lists."""
        result = HardwareScanResult()
        sensor = SensorInfo(
            hardware_name="CPU",
            hardware_type="Cpu",
            sensor_name="Core 1",
            sensor_type="Temperature",
            identifier="/cpu/0/temp/0",
            value=45.5,
        )
        result.temperatures.append(sensor)
        assert len(result.temperatures) == 1
        assert result.temperatures[0] == sensor


class TestHardwareModuleBackwardCompatibility:
    """Tests that hardware.py re-exports work correctly."""

    def test_types_export(self):
        """Should be able to import types from hardware module."""
        from pysysfan.hardware import (
            SensorKind,
            SensorInfo,
        )

        # Just verify they're the same as platforms.base
        from pysysfan.platforms.base import (
            SensorKind as BaseSensorKind,
            SensorInfo as BaseSensorInfo,
        )

        assert SensorKind is BaseSensorKind
        assert SensorInfo is BaseSensorInfo

    def test_get_hardware_manager_export(self):
        """Should export get_hardware_manager function."""
        from pysysfan.hardware import get_hardware_manager
        from pysysfan.platforms import get_hardware_manager as platforms_getter

        assert get_hardware_manager is platforms_getter
