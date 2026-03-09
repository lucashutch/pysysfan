"""Tests for the daemon state-file helpers."""

from __future__ import annotations

import json

from pysysfan.state_file import (
    AlertState,
    DaemonStateFile,
    FanSpeedState,
    TemperatureState,
    delete_state,
    read_state,
    write_state,
)


def _sample_state() -> DaemonStateFile:
    return DaemonStateFile(
        timestamp=100.0,
        pid=1234,
        running=True,
        uptime_seconds=12.5,
        active_profile="balanced",
        poll_interval=1.0,
        config_path="C:/Users/test/.pysysfan/config.yaml",
        config_error=None,
        fans_configured=2,
        curves_configured=3,
        temperatures=[
            TemperatureState(
                identifier="/cpu/temp/0",
                hardware_name="CPU",
                sensor_name="Package",
                value=62.0,
            )
        ],
        fan_speeds=[
            FanSpeedState(
                identifier="/mb/control/0",
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                rpm=1200.0,
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
                message="High temperature",
                value=90.0,
                threshold=80.0,
                timestamp=95.0,
            )
        ],
    )


class TestWriteState:
    def test_write_creates_parent_directory(self, tmp_path):
        path = tmp_path / "nested" / "daemon_state.json"

        write_state(_sample_state(), path)

        assert path.exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["pid"] == 1234
        assert payload["fan_targets"]["/mb/control/0"] == 60.0

    def test_write_replaces_existing_file(self, tmp_path):
        path = tmp_path / "daemon_state.json"
        path.write_text("old", encoding="utf-8")

        write_state(_sample_state(), path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["running"] is True


class TestReadState:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "daemon_state.json"
        write_state(_sample_state(), path)

        state = read_state(path, now=101.0)

        assert state is not None
        assert state.active_profile == "balanced"
        assert state.temperatures[0].sensor_name == "Package"
        assert state.fan_speeds[0].rpm == 1200.0
        assert state.recent_alerts[0].alert_type == "high_temp"

    def test_missing_file_returns_none(self, tmp_path):
        state = read_state(tmp_path / "missing.json")
        assert state is None

    def test_corrupt_file_returns_none(self, tmp_path):
        path = tmp_path / "daemon_state.json"
        path.write_text("{invalid json", encoding="utf-8")

        state = read_state(path)

        assert state is None

    def test_stale_file_returns_none(self, tmp_path):
        path = tmp_path / "daemon_state.json"
        write_state(_sample_state(), path)

        state = read_state(path, max_age_seconds=10.0, now=111.0)

        assert state is None

    def test_negative_max_age_disables_staleness_check(self, tmp_path):
        path = tmp_path / "daemon_state.json"
        write_state(_sample_state(), path)

        state = read_state(path, max_age_seconds=-1, now=1000.0)

        assert state is not None


class TestDeleteState:
    def test_delete_existing_file(self, tmp_path):
        path = tmp_path / "daemon_state.json"
        write_state(_sample_state(), path)

        delete_state(path)

        assert not path.exists()

    def test_delete_missing_file_is_noop(self, tmp_path):
        delete_state(tmp_path / "missing.json")
