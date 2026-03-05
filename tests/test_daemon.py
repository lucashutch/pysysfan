"""Tests for pysysfan.daemon — Fan control loop logic."""

from unittest.mock import patch, MagicMock


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
        mock_hw.set_fan_speed.side_effect = RuntimeError("hardware error")
        daemon._hw = mock_hw

        speeds = daemon._run_once(cfg)
        assert speeds == {}  # Failed, so not in applied


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
