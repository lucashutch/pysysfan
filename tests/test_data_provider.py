"""Tests for the DashboardDataProvider."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")


from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.gui.desktop.data_provider import DashboardDataProvider
from pysysfan.history_file import HistorySample, append_history_sample
from pysysfan.profiles import ProfileManager
from pysysfan.state_file import (
    AlertState,
    DaemonStateFile,
    FanSpeedState,
    TemperatureState,
    write_state,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _sample_state(
    timestamp: float | None = None,
    *,
    running: bool = True,
    config_path: str = "C:/Users/test/.pysysfan/profiles/gaming.yaml",
) -> DaemonStateFile:
    timestamp = time.time() if timestamp is None else timestamp
    return DaemonStateFile(
        timestamp=timestamp,
        pid=4321,
        running=running,
        uptime_seconds=25.0,
        active_profile="gaming",
        poll_interval=1.0,
        config_path=config_path,
        fans_configured=2,
        curves_configured=3,
        temperatures=[
            TemperatureState(
                identifier="/cpu/temp/0",
                hardware_name="CPU",
                sensor_name="Package",
                value=61.5,
            )
        ],
        fan_speeds=[
            FanSpeedState(
                identifier="/mb/fan/0",
                control_identifier="/mb/control/0",
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                rpm=1325.0,
                current_control_pct=55.0,
                controllable=True,
            )
        ],
        fan_targets={"/mb/control/0": 60.0},
        recent_alerts=[
            AlertState(
                rule_id="/cpu/temp/0:high_temp",
                sensor_id="/cpu/temp/0",
                alert_type="high_temp",
                message="High temperature: 90.0Â°C",
                value=90.0,
                threshold=80.0,
                timestamp=timestamp or time.time(),
            )
        ],
    )


def _task_status(installed: bool = True):
    return SimpleNamespace(
        task_installed=installed,
        task_enabled=installed,
        task_status="Running" if installed else None,
        task_last_run=None,
        daemon_running=installed,
        daemon_pid=4321 if installed else None,
        daemon_healthy=installed,
    )


def _create_profile_manager(tmp_path) -> ProfileManager:
    manager = ProfileManager(config_dir=tmp_path)
    config = Config(
        poll_interval=1.0,
        fans={
            "cpu_fan": FanConfig(
                fan_id="/mb/control/0",
                curve="balanced",
                temp_ids=["/cpu/temp/0"],
                aggregation="max",
                header_name="CPU Fan",
                allow_fan_off=False,
            )
        },
        curves={
            "balanced": CurveConfig(
                points=[(30.0, 30.0), (60.0, 60.0), (85.0, 100.0)],
                hysteresis=2.0,
            )
        },
        update=UpdateConfig(auto_check=False),
    )
    manager.create_profile(
        "gaming",
        display_name="Gaming Mode",
        description="Aggressive cooling for high sustained load.",
        config=config,
    )
    manager.set_active_profile("gaming")
    return manager


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestStateUpdatedSignal:
    """Provider emits stateUpdated when state file exists."""

    def test_emits_state_updated_on_valid_state(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        signals_received: list[object] = []
        provider.stateUpdated.connect(signals_received.append)

        provider.refresh_data()

        assert len(signals_received) == 1
        assert isinstance(signals_received[0], DaemonStateFile)

    def test_daemon_state_property_set_after_refresh(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        assert provider.daemon_state is None
        provider.refresh_data()
        assert provider.daemon_state is not None
        assert provider.daemon_state.pid == 4321


class TestOfflineDetected:
    """Provider emits offlineDetected when state file missing."""

    def test_emits_offline_when_no_state_file(self, qtbot, tmp_path):
        provider = DashboardDataProvider(
            state_path=tmp_path / "missing.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(installed=True),
        )

        signals_received: list[object] = []
        provider.offlineDetected.connect(signals_received.append)

        provider.refresh_data()

        assert len(signals_received) == 1
        assert (
            provider._refresh_timer.interval() == provider.OFFLINE_REFRESH_INTERVAL_MS
        )

    def test_clears_history_on_offline(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()
        assert len(provider.temperature_history) > 0

        # Remove state file to trigger offline
        state_path.unlink()
        provider.refresh_data()

        assert len(provider.temperature_history) == 0
        assert provider.daemon_state is None


class TestHistoryTrimming:
    """History trimming respects window size."""

    def test_trim_removes_old_samples(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        now = time.time()

        # Write history with an old sample outside the 60s window
        append_history_sample(
            HistorySample(
                timestamp=now - 120,
                temperatures={"/cpu/temp/0": 50.0},
                fan_rpm={"/mb/control/0": 1000.0},
                fan_targets={"/mb/control/0": 40.0},
            ),
            history_path,
        )
        append_history_sample(
            HistorySample(
                timestamp=now - 10,
                temperatures={"/cpu/temp/0": 60.0},
                fan_rpm={"/mb/control/0": 1200.0},
                fan_targets={"/mb/control/0": 55.0},
            ),
            history_path,
        )
        write_state(
            _sample_state(timestamp=now, config_path=str(config_path)), state_path
        )

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()

        # Default window is 60s â€” the sample at now-120 should be trimmed
        assert len(provider.temperature_history["/cpu/temp/0"]) == 1

    def test_larger_window_retains_more_samples(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        now = time.time()

        append_history_sample(
            HistorySample(
                timestamp=now - 120,
                temperatures={"/cpu/temp/0": 50.0},
                fan_rpm={"/mb/control/0": 1000.0},
                fan_targets={"/mb/control/0": 40.0},
            ),
            history_path,
        )
        append_history_sample(
            HistorySample(
                timestamp=now - 10,
                temperatures={"/cpu/temp/0": 60.0},
                fan_rpm={"/mb/control/0": 1200.0},
                fan_targets={"/mb/control/0": 55.0},
            ),
            history_path,
        )
        write_state(
            _sample_state(timestamp=now, config_path=str(config_path)), state_path
        )

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.set_history_window(300)
        provider.refresh_data()

        # 5-min window â€” both samples should be retained
        assert len(provider.temperature_history["/cpu/temp/0"]) == 2


class TestSetHistoryWindow:
    """set_history_window updates internal state."""

    def test_updates_history_seconds(self, qtbot, tmp_path):
        provider = DashboardDataProvider(
            state_path=tmp_path / "missing.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(),
        )

        assert provider.history_seconds == 60
        provider.set_history_window(900)
        assert provider.history_seconds == 900

    def test_emits_history_updated_when_data_exists(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()

        signals_received: list[bool] = []
        provider.historyUpdated.connect(lambda: signals_received.append(True))

        provider.set_history_window(300)
        assert len(signals_received) == 1


class TestLabelRecording:
    """Label recording from state data."""

    def test_records_temperature_labels(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()

        assert "/cpu/temp/0" in provider.temperature_labels
        assert provider.temperature_labels["/cpu/temp/0"] == "CPU"

    def test_humanizes_model_specific_temperature_names(self, qtbot, tmp_path):
        provider = DashboardDataProvider(
            state_path=tmp_path / "daemon_state.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(),
        )

        assert (
            provider._display_sensor_name(
                "AMD Ryzen 7 7700X Core",
                "Core (Tctl/Tdie)",
                "/cpu/temp/0",
            )
            == "Ryzen 7 7700X CPU Core"
        )
        assert (
            provider._display_sensor_name(
                "Nvidia Geforce GTX 1070 GPU",
                "GPU Core",
                "/gpu/temp/0",
            )
            == "GTX 1070 GPU Core"
        )
        assert (
            provider._display_sensor_name(
                "Nuvoton NCT6799D",
                "Temperature #1",
                "/mb/temp/1",
            )
            == "Motherboard Temp #1"
        )
        assert (
            provider._display_sensor_name(
                "Samsung SSD 980",
                "Composite Temperature",
                "/ssd/temp/0",
            )
            == "Samsung SSD 980 composite temp"
        )

    def test_records_fan_labels_and_groups(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()

        assert "/mb/control/0" in provider.fan_labels
        assert "/mb/control/0" in provider.fan_groups
        assert provider.fan_groups["/mb/control/0"] == "cpu_fan"

    def test_filters_limit_temperatures(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        state = DaemonStateFile(
            timestamp=time.time(),
            pid=4321,
            running=True,
            uptime_seconds=25.0,
            active_profile="gaming",
            poll_interval=1.0,
            config_path=str(config_path),
            temperatures=[
                TemperatureState(
                    identifier="/cpu/temp/0",
                    hardware_name="CPU",
                    sensor_name="Package",
                    value=61.5,
                ),
                TemperatureState(
                    identifier="/cpu/temp/limit",
                    hardware_name="CPU",
                    sensor_name="Package Limit",
                    value=95.0,
                ),
            ],
            fan_speeds=[
                FanSpeedState(
                    identifier="/mb/fan/0",
                    control_identifier="/mb/control/0",
                    hardware_name="Motherboard",
                    sensor_name="CPU Fan",
                    rpm=1325.0,
                    current_control_pct=55.0,
                    controllable=True,
                )
            ],
            fan_targets={"/mb/control/0": 60.0},
        )
        write_state(state, state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()

        assert "/cpu/temp/0" in provider.temperature_labels
        assert "/cpu/temp/limit" not in provider.temperature_labels


class TestPollingControl:
    """Polling starts/stops correctly."""

    def test_start_polling_activates_timer(self, qtbot, tmp_path):
        provider = DashboardDataProvider(
            state_path=tmp_path / "missing.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(),
        )

        assert provider._refresh_timer.isActive() is False
        provider.start_polling()
        assert provider._refresh_timer.isActive() is True

    def test_stop_polling_deactivates_timer(self, qtbot, tmp_path):
        provider = DashboardDataProvider(
            state_path=tmp_path / "missing.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(),
        )

        provider.start_polling()
        assert provider._refresh_timer.isActive() is True

        provider.stop_polling()
        assert provider._refresh_timer.isActive() is False

    def test_idle_interval_on_daemon_not_running(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        state = _sample_state(config_path=str(config_path), running=False)
        write_state(state, state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()
        assert provider._refresh_timer.interval() == provider.IDLE_REFRESH_INTERVAL_MS


class TestConfigLoading:
    """Config loading from state file path."""

    def test_loads_config_from_state(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        assert provider.active_config is None
        provider.refresh_data()
        assert provider.active_config is not None
        assert "cpu_fan" in provider.active_config.fans

    def test_config_none_when_path_missing(self, qtbot, tmp_path):
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(
            _sample_state(config_path=str(tmp_path / "nonexistent.yaml")),
            state_path,
        )

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
        )

        provider.refresh_data()
        assert provider.active_config is None

    def test_daemon_tone_success_on_valid_state(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()
        assert provider.daemon_indicator_tone == "success"


class TestAlerts:
    """Alert signal emission."""

    def test_alerts_emitted_on_state_with_alerts(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        received: list[list[str]] = []
        provider.alertsChanged.connect(received.append)

        provider.refresh_data()

        assert len(received) == 1
        assert len(received[0]) == 1
        assert "high_temp" in received[0][0]
        assert provider.alerts_badge_tone == "critical"

    def test_empty_alerts_neutral_tone(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        state = _sample_state(config_path=str(config_path))
        state.recent_alerts = []
        write_state(state, state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()
        assert provider.alerts_badge_tone == "neutral"
        assert provider.recent_alerts == []


class TestStartService:
    """Start service delegates to runner."""

    def test_start_service_calls_runner(self, qtbot, tmp_path):
        calls: list[str] = []
        provider = DashboardDataProvider(
            state_path=tmp_path / "missing.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(installed=True),
            service_action_runner=lambda action: (
                calls.append(action) or True,
                "Started",
            ),
        )

        success, message = provider.start_service()

        assert calls == ["start"]
        assert message == "Started"


class TestCatalogs:
    """Catalog builders produce expected entries."""

    def test_temperature_catalog(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()

        catalog = provider.build_temperature_catalog()
        assert "/cpu/temp/0" in catalog
        assert catalog["/cpu/temp/0"] == "CPU"

    def test_fan_rpm_catalog_has_groups(self, qtbot, tmp_path):
        profile_manager = _create_profile_manager(tmp_path)
        config_path = profile_manager.get_profile_config_path("gaming")
        state_path = tmp_path / "daemon_state.json"
        history_path = tmp_path / "daemon_history.ndjson"
        write_state(_sample_state(config_path=str(config_path)), state_path)

        provider = DashboardDataProvider(
            state_path=state_path,
            history_path=history_path,
            service_status_getter=lambda: _task_status(),
            profile_manager=profile_manager,
        )

        provider.refresh_data()

        catalog = provider.build_fan_rpm_catalog()
        assert any(key.startswith("group::") for key in catalog)

    def test_grouped_history_averages(self, qtbot, tmp_path):
        from collections import deque

        provider = DashboardDataProvider(
            state_path=tmp_path / "missing.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(),
        )

        history_map = {
            "fan_a": deque([(1.0, 100.0), (2.0, 200.0)]),
            "fan_b": deque([(1.0, 300.0), (2.0, 400.0)]),
        }
        group_map = {"fan_a": "group1", "fan_b": "group1"}

        result = provider.build_grouped_history(history_map, group_map)
        assert "group1" in result
        # At timestamp 1.0: avg(100, 300) = 200
        assert result["group1"][0] == (1.0, 200.0)
        # At timestamp 2.0: avg(200, 400) = 300
        assert result["group1"][1] == (2.0, 300.0)

    def test_grouped_history_empty_input(self, qtbot, tmp_path):
        provider = DashboardDataProvider(
            state_path=tmp_path / "missing.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(),
        )

        result = provider.build_grouped_history({}, {})
        assert result == {}

    def test_grouped_history_unmapped_series_ignored(self, qtbot, tmp_path):
        from collections import deque

        provider = DashboardDataProvider(
            state_path=tmp_path / "missing.json",
            history_path=tmp_path / "daemon_history.ndjson",
            service_status_getter=lambda: _task_status(),
        )

        history_map = {"fan_a": deque([(1.0, 100.0)])}
        group_map = {}  # no mapping

        result = provider.build_grouped_history(history_map, group_map)
        assert result == {}


class TestCandidateFanIds:
    """Unit tests for _candidate_fan_ids static method."""

    def test_fan_to_control_cross_mapping(self, qtbot):
        from types import SimpleNamespace

        fan = SimpleNamespace(identifier="/mb/fan/0", control_identifier=None)
        ids = DashboardDataProvider._candidate_fan_ids(fan)
        assert "/mb/fan/0" in ids
        assert "/mb/control/0" in ids

    def test_control_to_fan_cross_mapping(self, qtbot):
        from types import SimpleNamespace

        fan = SimpleNamespace(identifier="/mb/control/0", control_identifier=None)
        ids = DashboardDataProvider._candidate_fan_ids(fan)
        assert "/mb/control/0" in ids
        assert "/mb/fan/0" in ids

    def test_both_identifiers_included(self, qtbot):
        from types import SimpleNamespace

        fan = SimpleNamespace(
            identifier="/mb/fan/0", control_identifier="/mb/control/0"
        )
        ids = DashboardDataProvider._candidate_fan_ids(fan)
        assert "/mb/fan/0" in ids
        assert "/mb/control/0" in ids

    def test_none_identifiers_skipped(self, qtbot):
        from types import SimpleNamespace

        fan = SimpleNamespace(identifier=None, control_identifier=None)
        ids = DashboardDataProvider._candidate_fan_ids(fan)
        assert ids == set()
