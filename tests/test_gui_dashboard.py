"""Tests for the PySide6 dashboard page."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from pysysfan.gui.desktop.dashboard_page import DashboardPage
from pysysfan.state_file import (
    AlertState,
    DaemonStateFile,
    FanSpeedState,
    TemperatureState,
    write_state,
)


def _sample_state(timestamp: float | None = None) -> DaemonStateFile:
    timestamp = time.time() if timestamp is None else timestamp
    return DaemonStateFile(
        timestamp=timestamp,
        pid=4321,
        running=True,
        uptime_seconds=25.0,
        active_profile="gaming",
        poll_interval=1.0,
        config_path="C:/Users/test/.pysysfan/profiles/gaming.yaml",
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
                message="High temperature: 90.0°C",
                value=90.0,
                threshold=80.0,
                timestamp=timestamp,
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


def test_dashboard_refresh_populates_snapshot(qtbot, tmp_path) -> None:
    """Refreshing the dashboard should populate status and sensor widgets."""
    state_path = tmp_path / "daemon_state.json"
    write_state(_sample_state(), state_path)
    page = DashboardPage(
        state_path=state_path,
        service_status_getter=lambda: _task_status(),
    )
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.connection_label.text() == "Daemon: Connected"
    assert page.active_profile_label.text() == "Active profile: gaming"
    assert page.uptime_label.text() == "Uptime: 25.0s"
    assert page.poll_interval_label.text() == "Poll interval: 1.0s"
    assert page.fans_configured_label.text() == "Configured fans: 2"
    assert page.curves_configured_label.text() == "Configured curves: 3"
    assert page.temperatures_table.rowCount() == 1
    assert page.temperatures_table.item(0, 1).text() == "Package"
    assert page.fans_table.rowCount() == 1
    assert page.fans_table.item(0, 2).text() == "1325"
    assert page.fans_table.item(0, 4).text() == "60.0%"
    assert page.alerts_list.item(0).text().startswith("/cpu/temp/0 [high_temp]")


def test_dashboard_shows_offline_message_without_state(qtbot, tmp_path) -> None:
    """Dashboard should report offline state when no state file exists."""
    page = DashboardPage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _task_status(installed=True),
    )
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.connection_label.text() == "Daemon: Not running"
    assert page.start_service_button.isEnabled() is True
    assert "Start the service" in page.message_label.text()


def test_dashboard_start_service_uses_runner(qtbot, tmp_path) -> None:
    """Starting the service from the dashboard should use the injected runner."""
    calls: list[str] = []
    page = DashboardPage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _task_status(installed=True),
        service_action_runner=lambda action: (calls.append(action) or True, "Started"),
    )
    qtbot.addWidget(page)

    page.start_service()

    assert calls == ["start"]
    assert page.message_label.text() == "Started"


def test_dashboard_history_selector_updates_window(qtbot, tmp_path) -> None:
    """Changing the history selector should update the active history window."""
    state_path = tmp_path / "daemon_state.json"
    write_state(_sample_state(), state_path)
    page = DashboardPage(
        state_path=state_path,
        service_status_getter=lambda: _task_status(),
    )
    qtbot.addWidget(page)

    page.refresh_data()
    page.history_selector.setCurrentText("15 min")

    assert page._history_seconds == 900
