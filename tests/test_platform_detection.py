"""Tests for platform exports and hardware abstraction layer."""

from pysysfan.platforms import (
    WindowsHardwareManager,
    windows_service,
    BaseHardwareManager,
    SensorKind,
    SensorInfo,
    ControlInfo,
    HardwareScanResult,
)


class TestPlatformExports:
    """Tests that platform exports work correctly."""

    def test_windows_hardware_manager_exported(self):
        """Should export WindowsHardwareManager class."""
        assert WindowsHardwareManager is not None
        assert issubclass(WindowsHardwareManager, BaseHardwareManager)

    def test_windows_service_exported(self):
        """Should export windows_service module."""
        assert windows_service is not None
        assert hasattr(windows_service, "install_task")
        assert hasattr(windows_service, "uninstall_task")
        assert hasattr(windows_service, "get_task_status")


class TestBaseHardwareManager:
    """Tests for abstract base class."""

    def test_is_abstract(self):
        """BaseHardwareManager should be abstract."""
        import pytest

        with pytest.raises(TypeError):
            BaseHardwareManager()

    def test_subclass_must_implement_methods(self):
        """Subclasses must implement all abstract methods."""
        import pytest

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

    def test_hardware_manager_export(self):
        """Should export HardwareManager from hardware module."""
        from pysysfan.hardware import HardwareManager
        from pysysfan.platforms import WindowsHardwareManager

        assert HardwareManager is WindowsHardwareManager
