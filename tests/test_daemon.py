"""Tests for pysysfan.daemon — Fan control loop logic."""

import os
from unittest.mock import patch, MagicMock

import pytest

from pysysfan.config import Config, FanConfig, CurveConfig, UpdateConfig
from pysysfan.curves import FanCurve
from pysysfan.daemon import FanDaemon


# ── Fixtures ──────────────────────────────────────────────────────────


def _sample_config() -> Config:
    """Build a minimal Config for testing."""
    return Config(
        poll_interval=1.0,
        fans={
            "cpu_fan": FanConfig(
                fan_id="/mb/control/0",
                curve="balanced",
                temp_ids=["/cpu/temp/0"],
                aggregation="max",
            ),
        },
        curves={
            "balanced": CurveConfig(
                points=[(30, 30), (60, 60), (85, 100)],
                hysteresis=3.0,
            ),
        },
        update=UpdateConfig(auto_check=False),
    )


# ── __init__ ──────────────────────────────────────────────────────────


class TestFanDaemonInit:
    """Tests for FanDaemon initialisation."""

    def test_stores_config_path(self, tmp_path):
        """Should store the provided config path."""
        cfg_path = tmp_path / "config.yaml"
        daemon = FanDaemon(config_path=cfg_path)
        assert daemon.config_path == cfg_path

    def test_initial_state(self, tmp_path):
        """Should initialize with expected defaults."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        assert daemon._running is False
        assert daemon._hw is None
        assert daemon._curves == {}


# ── _load_config ──────────────────────────────────────────────────────


class TestLoadConfig:
    """Tests for _load_config()."""

    def test_loads_config_from_path(self, tmp_path):
        """Should load config from the stored path."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 5\nfans: {}\ncurves: {}\n")
        daemon = FanDaemon(config_path=cfg_file)
        cfg = daemon._load_config()
        assert cfg.poll_interval == 5.0


# ── Config Reload ─────────────────────────────────────────────────────


class TestConfigReload:
    """Tests for config reload functionality."""

    def test_reload_config_success(self, tmp_path):
        """Should reload config successfully when valid."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("""\
general:
  poll_interval: 3
fans:
  cpu:
    fan_id: "/test/fan/0"
    curve: "balanced"
    temp_id: "/test/temp/0"
curves:
  balanced:
    hysteresis: 2
    points:
      - [30, 30]
      - [60, 60]
""")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=False)
        result = daemon.reload_config()
        assert result is True
        assert daemon._cfg is not None
        assert daemon._cfg.poll_interval == 3.0
        assert "cpu" in daemon._cfg.fans
        assert "balanced" in daemon._curves

    def test_reload_config_invalid_yaml(self, tmp_path):
        """Should return False when config has invalid YAML."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("invalid: [yaml: syntax")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=False)
        result = daemon.reload_config()
        assert result is False
        assert daemon._cfg is None
        assert daemon._config_error is not None

    def test_reload_config_missing_curve(self, tmp_path):
        """Should return False when fan references missing curve."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("""\
general:
  poll_interval: 2
fans:
  cpu:
    fan_id: "/test/fan/0"
    curve: "nonexistent"
    temp_id: "/test/temp/0"
curves:
  balanced:
    hysteresis: 2
    points:
      - [30, 30]
""")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=False)
        result = daemon.reload_config()
        assert result is False
        assert daemon._config_error is not None

    def test_reload_config_invalid_poll_interval(self, tmp_path):
        """Should return False when poll_interval is invalid."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("""\
general:
  poll_interval: 0
fans: {}
curves: {}
""")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=False)
        result = daemon.reload_config()
        assert result is False
        assert daemon._config_error is not None

    def test_reload_preserves_old_config_on_failure(self, tmp_path):
        """Should keep old config when new config fails validation."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("""\
general:
  poll_interval: 2
fans:
  cpu:
    fan_id: "/test/fan/0"
    curve: "balanced"
    temp_id: "/test/temp/0"
curves:
  balanced:
    hysteresis: 2
    points:
      - [30, 30]
""")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=False)
        daemon.reload_config()

        # Now write invalid config
        cfg_file.write_text("""\
general:
  poll_interval: 2
fans:
  cpu:
    fan_id: "/test/fan/0"
    curve: "nonexistent"
    temp_id: "/test/temp/0"
curves: {}
""")

        # Reload should fail but keep old config
        result = daemon.reload_config()
        assert result is False
        assert daemon._cfg is not None
        assert "cpu" in daemon._cfg.fans
        assert daemon._cfg.fans["cpu"].curve == "balanced"


# ── _build_curves ─────────────────────────────────────────────────────


class TestBuildCurves:
    """Tests for _build_curves()."""

    def test_creates_fan_curves(self, tmp_path):
        """Should create FanCurve objects from the config."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        curves = daemon._build_curves(cfg)
        assert "balanced" in curves
        assert isinstance(curves["balanced"], FanCurve)
        assert curves["balanced"].hysteresis == 3.0


# ── _register_safety_handlers ────────────────────────────────────────


class TestRegisterSafetyHandlers:
    """Tests for _register_safety_handlers()."""

    def test_registers_atexit_and_signals(self, tmp_path):
        """Should register atexit and signal handlers without error."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._register_safety_handlers()
        # Should not raise

    def test_signal_handler_sets_running_false(self, tmp_path):
        """Signal handler should set _running to False."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._running = True
        daemon._signal_handler(2, None)
        assert daemon._running is False


# ── _emergency_restore ────────────────────────────────────────────────


class TestEmergencyRestore:
    """Tests for _emergency_restore()."""

    def test_restores_when_hw_open(self, tmp_path):
        """Should call restore_defaults when hardware is open."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._hw = MagicMock()
        daemon._emergency_restore()
        daemon._hw.restore_defaults.assert_called_once()

    def test_noop_when_hw_none(self, tmp_path):
        """Should do nothing when hardware is None."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._hw = None
        daemon._emergency_restore()  # Should not raise

    def test_handles_restore_error(self, tmp_path):
        """Should not raise when restore_defaults fails."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._hw = MagicMock()
        daemon._hw.restore_defaults.side_effect = RuntimeError("fail")
        daemon._emergency_restore()  # Should not raise


# ── _get_temperature ──────────────────────────────────────────────────


class TestGetTemperature:
    """Tests for _get_temperature()."""

    def test_finds_matching_sensor(self, tmp_path):
        """Should return the value of the matching temperature sensor."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")

        sensor = MagicMock()
        sensor.identifier = "/cpu/temp/0"
        sensor.value = 55.0

        result = daemon._get_temperature("/cpu/temp/0", [sensor])
        assert result == 55.0

    def test_returns_none_for_missing_sensor(self, tmp_path):
        """Should return None when no sensor matches."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        result = daemon._get_temperature("/cpu/temp/99", [])
        assert result is None


# ── _check_for_updates ────────────────────────────────────────────────


class TestCheckForUpdates:
    """Tests for _check_for_updates()."""

    def test_skips_when_disabled(self, tmp_path):
        """Should not check when auto_check is False."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.update.auto_check = False
        daemon._check_for_updates(cfg)

    @patch("pysysfan.updater.check_for_update")
    def test_logs_when_update_available_notify_only(self, mock_check, tmp_path):
        """Should log available update when notify_only is True."""
        mock_info = MagicMock()
        mock_info.available = True
        mock_info.current_version = "0.1.0"
        mock_info.latest_version = "0.2.0"
        mock_check.return_value = mock_info

        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.update.auto_check = True
        cfg.update.notify_only = True
        daemon._check_for_updates(cfg)

    @patch("pysysfan.updater.perform_update")
    @patch("pysysfan.updater.check_for_update")
    def test_auto_update_when_apply_enabled(self, mock_check, mock_update, tmp_path):
        """Should perform update when notify_only is False."""
        mock_info = MagicMock()
        mock_info.available = True
        mock_info.current_version = "0.1.0"
        mock_info.latest_version = "0.2.0"
        mock_check.return_value = mock_info

        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.update.auto_check = True
        cfg.update.notify_only = False
        daemon._check_for_updates(cfg)

        mock_update.assert_called_once_with("0.2.0")

    @patch("pysysfan.updater.check_for_update")
    def test_no_update_available(self, mock_check, tmp_path):
        """Should return silently when already up-to-date."""
        mock_info = MagicMock()
        mock_info.available = False
        mock_info.current_version = "1.0.0"
        mock_check.return_value = mock_info

        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.update.auto_check = True
        daemon._check_for_updates(cfg)

    @patch("pysysfan.updater.check_for_update", side_effect=ConnectionError("offline"))
    def test_handles_network_error(self, mock_check, tmp_path):
        """Should log warning and continue on network errors."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.update.auto_check = True
        daemon._check_for_updates(cfg)  # Should not raise


# ── _run_once ─────────────────────────────────────────────────────────


class TestRunOnce:
    """Tests for _run_once()."""

    def test_evaluates_fans(self, tmp_path):
        """Should evaluate each fan and return speeds dict."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        curves = daemon._build_curves(cfg)
        daemon._curves = curves

        mock_hw = MagicMock()
        temp_sensor = MagicMock()
        temp_sensor.identifier = "/cpu/temp/0"
        temp_sensor.value = 45.0
        mock_hw.get_temperatures.return_value = [temp_sensor]
        mock_hw.get_fans.return_value = []
        mock_hw.set_fan_speed = MagicMock()
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert "cpu_fan" in speeds
        assert 40 <= speeds["cpu_fan"] <= 50
        mock_hw.set_fan_speed.assert_called_once()

    def test_skips_missing_curve(self, tmp_path):
        """Should skip fans with unknown curves."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._curves = {}  # Empty curves

        mock_hw = MagicMock()
        mock_hw.get_temperatures.return_value = []
        mock_hw.get_fans.return_value = []
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert speeds == {}

    def test_skips_missing_temp_source(self, tmp_path):
        """Should skip when temperature source not found."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._curves = daemon._build_curves(cfg)

        mock_hw = MagicMock()
        mock_hw.get_temperatures.return_value = []  # No sensors
        mock_hw.get_fans.return_value = []
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert speeds == {}

    def test_skips_zero_temp(self, tmp_path):
        """Should skip when temperature is 0.0 (likely unavailable)."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._curves = daemon._build_curves(cfg)

        mock_hw = MagicMock()
        temp_sensor = MagicMock()
        temp_sensor.identifier = "/cpu/temp/0"
        temp_sensor.value = 0.0
        mock_hw.get_temperatures.return_value = [temp_sensor]
        mock_hw.get_fans.return_value = []
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert speeds == {}

    def test_handles_set_fan_speed_error(self, tmp_path):
        """Should continue when set_fan_speed raises."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._curves = daemon._build_curves(cfg)

        mock_hw = MagicMock()
        temp_sensor = MagicMock()
        temp_sensor.identifier = "/cpu/temp/0"
        temp_sensor.value = 50.0
        mock_hw.get_temperatures.return_value = [temp_sensor]
        mock_hw.get_fans.return_value = []
        mock_hw.set_fan_speed.side_effect = RuntimeError("hardware error")
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert speeds == {}  # Failed, so not in applied

    def test_fan_off_mode_logs_info(self, tmp_path):
        """Should log info when turning fan off (0% target)."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        # Use "off" curve which always returns 0
        cfg.fans["cpu_fan"].curve = "off"
        daemon._curves = daemon._build_curves(cfg)

        mock_hw = MagicMock()
        temp_sensor = MagicMock()
        temp_sensor.identifier = "/cpu/temp/0"
        temp_sensor.value = 30.0
        mock_hw.get_temperatures.return_value = [temp_sensor]
        mock_hw.get_fans.return_value = []
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert "cpu_fan" in speeds
        assert speeds["cpu_fan"] == 0.0

    def test_fan_off_disabled_uses_minimum_speed(self, tmp_path):
        """When allow_fan_off is False, 0% should become minimum speed (1%)."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.fans["cpu_fan"].curve = "off"
        cfg.fans["cpu_fan"].allow_fan_off = False
        daemon._curves = daemon._build_curves(cfg)

        mock_hw = MagicMock()
        temp_sensor = MagicMock()
        temp_sensor.identifier = "/cpu/temp/0"
        temp_sensor.value = 30.0
        mock_hw.get_temperatures.return_value = [temp_sensor]
        mock_hw.get_fans.return_value = []
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert "cpu_fan" in speeds
        # Should be set to minimum speed (1%) instead of 0%
        assert speeds["cpu_fan"] == 1.0


# ── _open_hardware ──────────────────────────────────────────────────


class TestOpenHardware:
    """Tests for _open_hardware()."""

    @patch("pysysfan.hardware.HardwareManager")
    def test_opens_hardware(self, mock_manager_class, tmp_path):
        """Should create and open HardwareManager."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        hw = daemon._open_hardware()

        mock_manager_class.assert_called_once()
        mock_manager.open.assert_called_once()
        assert hw is mock_manager


class TestPublicRunOnce:
    """Tests for the public run_once() method."""

    @patch("pysysfan.daemon.FanDaemon._load_config")
    @patch("pysysfan.daemon.FanDaemon._open_hardware")
    def test_run_once_opens_hw_and_runs(self, mock_open, mock_load_cfg, tmp_path):
        """Should open hardware, run once, and close."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        mock_load_cfg.return_value = _sample_config()

        mock_hw = MagicMock()
        temp_sensor = MagicMock()
        temp_sensor.identifier = "/cpu/temp/0"
        temp_sensor.value = 45.0
        mock_hw.scan.return_value = MagicMock(
            temperatures=[temp_sensor], fans=[], controls=[]
        )
        mock_hw.get_temperatures.return_value = [temp_sensor]
        mock_hw.set_fan_speed = MagicMock()
        mock_open.return_value = mock_hw

        result = daemon.run_once()

        mock_hw.scan.assert_called_once()
        mock_hw.restore_defaults.assert_called()
        mock_hw.close.assert_called()
        assert daemon._hw is None  # _hw should be cleared
        assert isinstance(result, dict)


class TestWatcherMethods:
    """Tests for config watcher start/stop methods."""

    @patch("pysysfan.daemon.ConfigWatcher")
    def test_start_watcher_when_disabled(self, mock_watcher_class, tmp_path):
        """Should not start watcher when auto_reload is False."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml", auto_reload=False)
        daemon._start_watcher()
        mock_watcher_class.assert_not_called()

    @patch("pysysfan.daemon.ConfigWatcher.is_available", return_value=False)
    def test_start_watcher_not_available(self, mock_available, tmp_path):
        """Should not start watcher when watchdog not available."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml", auto_reload=True)
        daemon._start_watcher()
        assert daemon._watcher is None

    @patch("pysysfan.daemon.ConfigWatcher")
    def test_start_watcher_success(self, mock_watcher_class, tmp_path):
        """Should start watcher when available and enabled."""
        mock_watcher = MagicMock()
        mock_watcher.start.return_value = True
        mock_watcher_class.return_value = mock_watcher
        mock_watcher_class.is_available.return_value = True

        daemon = FanDaemon(config_path=tmp_path / "c.yaml", auto_reload=True)
        daemon._start_watcher()

        assert daemon._watcher is mock_watcher
        mock_watcher.start.assert_called_once()

    @patch("pysysfan.daemon.ConfigWatcher")
    def test_start_watcher_failure(self, mock_watcher_class, tmp_path):
        """Should handle watcher start failure."""
        mock_watcher = MagicMock()
        mock_watcher.start.return_value = False
        mock_watcher_class.return_value = mock_watcher
        mock_watcher_class.is_available.return_value = True

        daemon = FanDaemon(config_path=tmp_path / "c.yaml", auto_reload=True)
        daemon._start_watcher()

        assert daemon._watcher is None

    def test_stop_watcher_when_none(self, tmp_path):
        """Should handle stop when watcher is None."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._watcher = None
        daemon._stop_watcher()  # Should not raise

    def test_stop_watcher_success(self, tmp_path):
        """Should stop and clear watcher."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        mock_watcher = MagicMock()
        daemon._watcher = mock_watcher

        daemon._stop_watcher()

        mock_watcher.stop.assert_called_once()
        assert daemon._watcher is None


class TestDaemonLifecycle:
    """Tests for daemon lifecycle methods."""

    @patch("pysysfan.daemon.FanDaemon._load_config")
    @patch("pysysfan.daemon.FanDaemon._open_hardware")
    def test_run_loop_initialization(self, mock_open_hw, mock_load_cfg, tmp_path):
        """Run loop should initialize components."""
        mock_load_cfg.return_value = _sample_config()
        mock_hw = MagicMock()
        mock_open_hw.return_value = mock_hw

        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        # Just verify initialization works, not full run loop
        assert daemon._cfg is None
        daemon._cfg = daemon._load_config()
        assert daemon._cfg is not None

    def test_emergency_restore_with_none_hardware(self, tmp_path):
        """Should handle restore when hardware is None."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._hw = None
        daemon._emergency_restore()  # Should not raise

    def test_emergency_restore_with_error(self, tmp_path):
        """Should handle restore errors gracefully."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        mock_hw = MagicMock()
        mock_hw.restore_defaults.side_effect = RuntimeError("Failed")
        daemon._hw = mock_hw
        daemon._emergency_restore()  # Should not raise


class TestHardwareErrors:
    """Tests for hardware error handling."""

    def test_run_once_with_no_temperatures(self, tmp_path):
        """Should handle when no temperature sensors found."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._curves = daemon._build_curves(cfg)

        mock_hw = MagicMock()
        mock_hw.get_temperatures.return_value = []
        mock_hw.get_fans.return_value = []
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert speeds == {}

    def test_run_once_with_no_matching_temp(self, tmp_path):
        """Should handle when configured temp sensor not found."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._curves = daemon._build_curves(cfg)

        mock_hw = MagicMock()
        temp_sensor = MagicMock()
        temp_sensor.identifier = "/different/temp"
        temp_sensor.value = 50.0
        mock_hw.get_temperatures.return_value = [temp_sensor]
        mock_hw.get_fans.return_value = []
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        # Should use fallback or skip
        assert isinstance(speeds, dict)


# ── Additional tests for coverage ────────────────────────────────────


class TestDaemonInitOptions:
    """Tests for FanDaemon initialization options."""

    def test_init_with_custom_cache_manager(self, tmp_path):
        """Should accept custom cache manager."""
        from pysysfan.cache import HardwareCacheManager

        cache_mgr = HardwareCacheManager()
        daemon = FanDaemon(
            config_path=tmp_path / "c.yaml",
            cache_manager=cache_mgr,
            api_enabled=False,
            api_host="0.0.0.0",
            api_port=9000,
        )
        assert daemon._cache_manager is cache_mgr
        assert daemon._api_enabled is False
        assert daemon._api_host == "0.0.0.0"
        assert daemon._api_port == 9000

    def test_init_uses_default_cache_manager(self, tmp_path):
        """Should use default cache manager when not provided."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        assert daemon._cache_manager is not None


class TestValidateConfig:
    """Tests for _validate_config method."""

    def test_validate_config_no_temp_ids(self, tmp_path):
        """Should error when fan has no temp_ids."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.fans["cpu_fan"].temp_ids = []
        errors = daemon._validate_config(cfg)
        assert any("no temperature sensors" in e.lower() for e in errors)

    def test_validate_config_poll_interval_too_short(self, tmp_path):
        """Should error when poll_interval is too short."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.poll_interval = 0.05
        errors = daemon._validate_config(cfg)
        assert any("too short" in e.lower() for e in errors)

    def test_validate_config_invalid_aggregation(self, tmp_path):
        """Should error when aggregation method is invalid."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.fans["cpu_fan"].aggregation = "invalid_method"
        errors = daemon._validate_config(cfg)
        assert any("invalid aggregation" in e.lower() for e in errors)

    def test_validate_config_invalid_curve_error(self, tmp_path):
        """Should handle InvalidCurveError during validation."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.fans["cpu_fan"].curve = "invalid!!!"
        errors = daemon._validate_config(cfg)
        assert len(errors) > 0


class TestBuildCurvesEdgeCases:
    """Tests for _build_curves edge cases."""

    def test_build_curves_empty_config(self, tmp_path):
        """Should handle empty curves dict."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        cfg.curves = {}
        curves = daemon._build_curves(cfg)
        assert curves == {}


class TestDaemonStatePopulation:
    """Tests for daemon runtime state snapshots."""

    def test_run_once_populates_runtime_state_maps(self, tmp_path):
        """A control pass should update temperatures, fan speeds, and targets."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._curves = daemon._build_curves(cfg)

        mock_hw = MagicMock()
        mock_hw.get_temperatures.return_value = [
            MagicMock(identifier="/cpu/temp/0", value=60.0)
        ]
        mock_hw.get_fans.return_value = [
            MagicMock(identifier="/fan/0/rpm", value=1350.0)
        ]
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)

        assert speeds == {"cpu_fan": 60.0}
        assert daemon._current_temps == {"/cpu/temp/0": 60.0}
        assert daemon._current_fan_speeds == {"/fan/0/rpm": 1350.0}
        assert daemon._current_targets == {"/mb/control/0": 60.0}

    def test_update_state_uses_runtime_state_maps(self, tmp_path):
        """State snapshots should include the latest runtime maps."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._cfg = _sample_config()
        daemon._start_time = 100.0
        daemon._running = True
        daemon._current_temps = {"/cpu/temp/0": 55.0}
        daemon._current_fan_speeds = {"/fan/0/rpm": 1200.0}
        daemon._current_targets = {"/mb/control/0": 50.0}

        daemon._update_state()
        snapshot = daemon._state_manager.get_snapshot()

        assert snapshot is not None
        assert snapshot.current_temps == {"/cpu/temp/0": 55.0}
        assert snapshot.current_fan_speeds == {"/fan/0/rpm": 1200.0}
        assert snapshot.current_targets == {"/mb/control/0": 50.0}


class TestGetCurve:
    """Tests for _get_curve method."""

    def test_get_curve_special_off(self, tmp_path):
        """Should return StaticCurve for 'off' special curve."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        curve = daemon._get_curve("off")
        assert curve is not None
        assert curve.evaluate(50) == 0.0

    def test_get_curve_special_on(self, tmp_path):
        """Should return StaticCurve for 'on' special curve."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        curve = daemon._get_curve("on")
        assert curve is not None
        assert curve.evaluate(50) == 100.0

    def test_get_curve_percentage(self, tmp_path):
        """Should return StaticCurve for percentage curves."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        curve = daemon._get_curve("50%")
        assert curve is not None
        assert curve.evaluate(50) == 50.0

    def test_get_curve_invalid(self, tmp_path):
        """Should return None for invalid curve names."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        curve = daemon._get_curve("invalid!!!")
        assert curve is None

    def test_get_curve_from_config(self, tmp_path):
        """Should return curve from config curves."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._curves = daemon._build_curves(cfg)
        curve = daemon._get_curve("balanced")
        assert curve is not None
        assert isinstance(curve, FanCurve)

    def test_get_curve_missing(self, tmp_path):
        """Should return None for missing curve."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._curves = {}
        curve = daemon._get_curve("nonexistent")
        assert curve is None


class TestUseCachedScan:
    """Tests for _use_cached_scan method."""

    @patch("pysysfan.cache.HardwareCacheManager")
    def test_cache_hit(self, mock_cache_mgr_class, tmp_path):
        """Should use cached scan when valid."""
        mock_cache_mgr = MagicMock()
        mock_cache_mgr_class.return_value = mock_cache_mgr
        mock_cache_mgr.is_valid.return_value = True
        cached_result = MagicMock()
        mock_cache_mgr.get_cached_scan_result.return_value = cached_result

        daemon = FanDaemon(
            config_path=tmp_path / "c.yaml", cache_manager=mock_cache_mgr
        )
        daemon._hw = MagicMock()
        daemon._hw.get_hardware_fingerprint.return_value = "test_fp"

        result = daemon._use_cached_scan()
        assert result is cached_result

    @patch("pysysfan.cache.HardwareCacheManager")
    def test_cache_miss(self, mock_cache_mgr_class, tmp_path):
        """Should perform new scan when cache invalid."""
        mock_cache_mgr = MagicMock()
        mock_cache_mgr_class.return_value = mock_cache_mgr
        mock_cache_mgr.is_valid.return_value = False

        daemon = FanDaemon(
            config_path=tmp_path / "c.yaml", cache_manager=mock_cache_mgr
        )
        daemon._hw = MagicMock()
        daemon._hw.get_hardware_fingerprint.return_value = "test_fp"
        scan_result = MagicMock()
        daemon._hw.scan.return_value = scan_result

        result = daemon._use_cached_scan()
        assert result is scan_result
        daemon._hw.scan.assert_called_once()


class TestInitializeUnconfiguredFans:
    """Tests for _initialize_unconfigured_fans method."""

    def test_no_unconfigured_fans(self, tmp_path):
        """Should do nothing when all fans configured."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._cfg = cfg
        daemon._hw = MagicMock()
        scan_result = MagicMock()
        scan_result.controls = [MagicMock(identifier="/mb/control/0", has_control=True)]

        daemon._initialize_unconfigured_fans(scan_result)
        daemon._hw.set_fan_speed.assert_not_called()

    def test_sets_unconfigured_to_zero(self, tmp_path):
        """Should set unconfigured fans to 0%."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._cfg = cfg
        daemon._hw = MagicMock()
        scan_result = MagicMock()
        scan_result.controls = [
            MagicMock(identifier="/mb/control/0", has_control=True),
            MagicMock(identifier="/mb/control/1", has_control=True),
        ]

        daemon._initialize_unconfigured_fans(scan_result)
        daemon._hw.set_fan_speed.assert_called_once_with("/mb/control/1", 0.0)

    def test_no_cfg_set(self, tmp_path):
        """Should do nothing when _cfg is None."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._cfg = None
        daemon._hw = MagicMock()
        scan_result = MagicMock()

        daemon._initialize_unconfigured_fans(scan_result)
        daemon._hw.set_fan_speed.assert_not_called()

    def test_handles_set_fan_error(self, tmp_path):
        """Should handle errors when setting fan speed."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._cfg = cfg
        daemon._hw = MagicMock()
        daemon._hw.set_fan_speed.side_effect = RuntimeError("Failed")
        scan_result = MagicMock()
        scan_result.controls = [
            MagicMock(identifier="/mb/control/0", has_control=True),
            MagicMock(identifier="/mb/control/1", has_control=True),
        ]

        daemon._initialize_unconfigured_fans(scan_result)
        # Should not raise


class TestUpdateState:
    """Tests for _update_state method."""

    def test_updates_all_fields(self, tmp_path):
        """Should update all state fields."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        cfg = _sample_config()
        daemon._cfg = cfg
        daemon._start_time = 1000.0
        daemon._running = True

        with patch.object(daemon._state_manager, "update_state") as mock_update:
            daemon._update_state()
            mock_update.assert_called_once()
            call_kwargs = mock_update.call_args.kwargs
            assert call_kwargs["pid"] == os.getpid()
            assert call_kwargs["config_path"] == str(daemon.config_path)
            assert call_kwargs["running"] is True
            assert call_kwargs["fans_configured"] == 1
            assert call_kwargs["curves_configured"] == 1

    def test_with_no_config(self, tmp_path):
        """Should handle when _cfg is None."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._cfg = None
        daemon._start_time = 1000.0

        with patch.object(daemon._state_manager, "update_state") as mock_update:
            daemon._update_state()
            call_kwargs = mock_update.call_args.kwargs
            assert call_kwargs["fans_configured"] == 0
            assert call_kwargs["curves_configured"] == 0
            assert call_kwargs["poll_interval"] == 2.0

    def test_with_config_error(self, tmp_path):
        """Should include config error in state."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._config_error = ValueError("Test error")

        with patch.object(daemon._state_manager, "update_state") as mock_update:
            daemon._update_state()
            call_kwargs = mock_update.call_args.kwargs
            assert "Test error" in call_kwargs["last_error"]


class TestAPIServer:
    """Tests for API server methods."""

    def test_start_api_server_disabled(self, tmp_path):
        """Should not start API server when disabled."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml", api_enabled=False)
        daemon._start_api_server()
        assert daemon._api_server is None

    def test_stop_api_server_when_none(self, tmp_path):
        """Should handle stop when server is None."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._api_server = None
        daemon._stop_api_server()  # Should not raise

    def test_stop_api_server(self, tmp_path):
        """Should stop API server gracefully."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        mock_server = MagicMock()
        mock_thread = MagicMock()
        daemon._api_server = mock_server
        daemon._api_thread = mock_thread

        daemon._stop_api_server()

        assert mock_server.should_exit is True
        mock_thread.join.assert_called_once_with(timeout=5.0)
        assert daemon._api_server is None
        assert daemon._api_thread is None

    def test_api_server_enabled_by_default(self, tmp_path):
        """Should have API enabled by default."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        assert daemon._api_enabled is True
        assert daemon._api_port == 8765


class TestReloadConfigEdgeCases:
    """Tests for reload_config edge cases."""

    def test_apply_config_failure(self, tmp_path):
        """Should handle failure when applying config."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("""\
general:
  poll_interval: 2
fans:
  cpu:
    fan_id: "/test/fan/0"
    curve: "balanced"
    temp_id: "/test/temp/0"
curves:
  balanced:
    hysteresis: 2
    points:
      - [30, 30]
""")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=False)

        with patch.object(
            daemon, "_build_curves", side_effect=RuntimeError("Build failed")
        ):
            result = daemon.reload_config()
            assert result is False
            assert daemon._config_error is not None


class TestWatcherCallbacks:
    """Tests for watcher callback functionality."""

    @patch("pysysfan.daemon.ConfigWatcher")
    def test_watcher_on_reload_callback(self, mock_watcher_class, tmp_path):
        """Should call reload_config on watcher reload."""
        mock_watcher = MagicMock()
        mock_watcher.start.return_value = True
        mock_watcher_class.return_value = mock_watcher
        mock_watcher_class.is_available.return_value = True

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=True)

        with patch.object(daemon, "reload_config") as mock_reload:
            daemon._start_watcher()
            # Simulate reload callback
            callback = mock_watcher_class.call_args.kwargs["on_reload"]
            callback()
            mock_reload.assert_called_once()

    @patch("pysysfan.daemon.ConfigWatcher")
    def test_watcher_on_error_callback(self, mock_watcher_class, tmp_path):
        """Should handle watcher errors."""
        mock_watcher = MagicMock()
        mock_watcher.start.return_value = True
        mock_watcher_class.return_value = mock_watcher
        mock_watcher_class.is_available.return_value = True

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=True)

        daemon._start_watcher()
        # Simulate error callback
        error_callback = mock_watcher_class.call_args.kwargs["on_error"]
        error_callback(Exception("Watcher error"))
        # Should not raise


class TestSignalHandler:
    """Tests for signal handler."""

    def test_signal_handler_logs_shutdown(self, tmp_path, caplog):
        """Should log shutdown message."""
        import logging

        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        daemon._running = True

        with caplog.at_level(logging.INFO):
            daemon._signal_handler(2, None)
            assert "shutting down" in caplog.text.lower()


class TestRunOnceErrorHandling:
    """Tests for run_once error handling."""

    @patch("pysysfan.daemon.FanDaemon._load_config")
    @patch("pysysfan.daemon.FanDaemon._open_hardware")
    def test_run_once_with_error_in_loop(self, mock_open, mock_load_cfg, tmp_path):
        """Should handle errors in control loop and still cleanup."""
        daemon = FanDaemon(config_path=tmp_path / "c.yaml")
        mock_load_cfg.return_value = _sample_config()

        mock_hw = MagicMock()
        mock_hw.scan.side_effect = RuntimeError("Scan failed")
        mock_open.return_value = mock_hw

        with pytest.raises(RuntimeError):
            daemon.run_once()

        mock_hw.restore_defaults.assert_called_once()
        mock_hw.close.assert_called_once()


class TestReloadConfigSuccessLogging:
    """Tests for reload_config success logging."""

    def test_reload_config_logs_success(self, tmp_path, caplog):
        """Should log success message with config details."""
        import logging

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("""\
general:
  poll_interval: 3
fans:
  cpu:
    fan_id: "/test/fan/0"
    curve: "balanced"
    temp_ids: ["/test/temp/0"]
curves:
  balanced:
    hysteresis: 2
    points:
      - [30, 30]
""")
        daemon = FanDaemon(config_path=cfg_file, auto_reload=False)

        with caplog.at_level(logging.INFO):
            result = daemon.reload_config()
            assert result is True
            assert "reloaded successfully" in caplog.text.lower()
            assert "fans:" in caplog.text.lower()
            assert "curves:" in caplog.text.lower()
