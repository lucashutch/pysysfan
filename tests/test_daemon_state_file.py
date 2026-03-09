"""Focused tests for daemon state-file persistence."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.daemon import FanDaemon
from pysysfan.platforms.base import ControlInfo, HardwareScanResult, SensorInfo
from pysysfan.state_file import read_state


def _sample_config() -> Config:
    return Config(
        poll_interval=1.0,
        fans={
            "cpu_fan": FanConfig(
                fan_id="/mb/control/0",
                curve="balanced",
                temp_ids=["/cpu/temp/0"],
            )
        },
        curves={
            "balanced": CurveConfig(
                points=[(30, 30), (60, 60), (80, 100)],
                hysteresis=3.0,
            )
        },
        update=UpdateConfig(auto_check=False),
    )


class TestDaemonStateSnapshots:
    def test_update_state_writes_snapshot_file(self, tmp_path):
        state_path = tmp_path / "daemon_state.json"
        daemon = FanDaemon(config_path=tmp_path / "config.yaml", state_path=state_path)
        daemon._cfg = _sample_config()
        daemon._start_time = 100.0
        daemon._running = True
        daemon._current_targets = {"/mb/control/0": 60.0}
        daemon._latest_temperatures = [
            SensorInfo(
                hardware_name="CPU",
                hardware_type="CPU",
                sensor_name="Package",
                sensor_type="Temperature",
                identifier="/cpu/temp/0",
                value=61.5,
            )
        ]
        daemon._latest_fan_speeds = [
            SensorInfo(
                hardware_name="Motherboard",
                hardware_type="SuperIO",
                sensor_name="CPU Fan",
                sensor_type="Fan",
                identifier="/mb/fan/0",
                value=1325.0,
            )
        ]
        daemon._latest_controls = [
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="CPU Fan Control",
                identifier="/mb/control/0",
                current_value=55.0,
                has_control=True,
            )
        ]

        with patch("pysysfan.daemon.time.time", return_value=110.0):
            with patch("pysysfan.daemon.ProfileManager") as mock_pm:
                mock_pm.return_value.get_active_profile.return_value = "gaming"
                daemon._update_state()

        state = read_state(state_path, now=110.0)
        assert state is not None
        assert state.active_profile == "gaming"
        assert state.fans_configured == 1
        assert state.curves_configured == 1
        assert state.fan_targets == {"/mb/control/0": 60.0}
        assert state.temperatures[0].value == 61.5
        assert state.fan_speeds[0].control_identifier == "/mb/control/0"
        assert state.fan_speeds[0].current_control_pct == 55.0
        assert state.fan_speeds[0].controllable is True

    def test_run_deletes_state_file_on_shutdown(self, tmp_path):
        state_path = tmp_path / "daemon_state.json"
        daemon = FanDaemon(config_path=tmp_path / "config.yaml", state_path=state_path)
        daemon._cfg = _sample_config()
        daemon.reload_config = MagicMock(return_value=True)
        daemon._register_safety_handlers = MagicMock()
        daemon._start_watcher = MagicMock()
        daemon._start_api_server = MagicMock()
        daemon._check_for_updates = MagicMock()
        hw = MagicMock()
        daemon._open_hardware = MagicMock(return_value=hw)
        daemon._hw = hw
        daemon._use_cached_scan = MagicMock(return_value=HardwareScanResult())
        daemon._initialize_unconfigured_fans = MagicMock()

        def run_once_side_effect(_cfg):
            daemon._latest_temperatures = []
            daemon._latest_fan_speeds = []
            daemon._latest_controls = []
            daemon._current_targets = {}
            daemon._running = False
            return {}

        daemon._run_once = MagicMock(side_effect=run_once_side_effect)

        daemon.run()

        assert not state_path.exists()
        hw.restore_defaults.assert_called_once()
        hw.close.assert_called_once()
