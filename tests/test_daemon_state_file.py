"""Focused tests for daemon state-file persistence."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.daemon import FanDaemon
from pysysfan.history_file import read_history
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
        history_path = tmp_path / "daemon_history.ndjson"
        daemon = FanDaemon(
            config_path=tmp_path / "config.yaml",
            state_path=state_path,
            history_path=history_path,
        )
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

        history = read_history(history_path, now=110.0)
        assert len(history) == 1
        assert history[0].fan_rpm == {"/mb/control/0": 1325.0}
        assert history[0].fan_targets == {"/mb/control/0": 60.0}

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

    def test_update_state_matches_gpu_controls_by_device_path(self, tmp_path):
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        daemon = FanDaemon(
            config_path=tmp_path / "config.yaml",
            state_path=state_path,
            history_path=history_path,
        )
        daemon._cfg = _sample_config()
        daemon._start_time = 100.0
        daemon._running = True
        daemon._current_targets = {
            "/lpc/nct6799d/0/control/0": 40.0,
            "/gpu-nvidia/0/control/0": 30.0,
        }
        daemon._latest_temperatures = []
        daemon._latest_fan_speeds = [
            SensorInfo(
                hardware_name="Nuvoton NCT6799D",
                hardware_type="SuperIO",
                sensor_name="Fan #1",
                sensor_type="Fan",
                identifier="/lpc/nct6799d/0/fan/0",
                value=800.0,
            ),
            SensorInfo(
                hardware_name="NVIDIA GeForce GTX 1070",
                hardware_type="GpuNvidia",
                sensor_name="GPU",
                sensor_type="Fan",
                identifier="/gpu-nvidia/0/fan/1",
                value=1200.0,
            ),
        ]
        daemon._latest_controls = [
            ControlInfo(
                hardware_name="Nuvoton NCT6799D",
                sensor_name="Fan #1 Control",
                identifier="/lpc/nct6799d/0/control/0",
                current_value=40.0,
                has_control=True,
            ),
            ControlInfo(
                hardware_name="NVIDIA GeForce GTX 1070",
                sensor_name="GPU Fan Control",
                identifier="/gpu-nvidia/0/control/0",
                current_value=30.0,
                has_control=True,
            ),
        ]

        with patch("pysysfan.daemon.time.time", return_value=110.0):
            daemon._update_state()

        state = read_state(state_path, now=110.0)
        assert state is not None
        assert {fan.identifier: fan.control_identifier for fan in state.fan_speeds} == {
            "/lpc/nct6799d/0/fan/0": "/lpc/nct6799d/0/control/0",
            "/gpu-nvidia/0/fan/1": "/gpu-nvidia/0/control/0",
        }

    def test_update_state_skips_unchanged_snapshot_writes(self, tmp_path):
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        daemon = FanDaemon(
            config_path=tmp_path / "config.yaml",
            state_path=state_path,
            history_path=history_path,
        )
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

        with (
            patch("pysysfan.daemon.write_state") as mock_write_state,
            patch("pysysfan.daemon.append_history_sample") as mock_append_history,
            patch("pysysfan.daemon.time.time", side_effect=[110.0, 111.0]),
        ):
            daemon._update_state()
            daemon._update_state()

        assert mock_write_state.call_count == 1
        assert mock_append_history.call_count == 2

    def test_update_state_skips_state_signature_on_write_failure(self, tmp_path):
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        daemon = FanDaemon(
            config_path=tmp_path / "config.yaml",
            state_path=state_path,
            history_path=history_path,
        )
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
        daemon._last_state_signature = "previous"

        with (
            patch("pysysfan.daemon.write_state", return_value=False) as mock_ws,
            patch("pysysfan.daemon.append_history_sample") as _mock_append,
            patch("pysysfan.daemon.compact_history") as _mock_compact,
            patch("pysysfan.daemon.ProfileManager") as mock_pm,
            patch("pysysfan.daemon.time.time", return_value=110.0),
        ):
            mock_pm.return_value.get_active_profile.return_value = "gaming"
            daemon._update_state()

        assert mock_ws.call_count == 1
        assert daemon._last_state_signature == "previous"
