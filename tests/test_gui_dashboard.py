"""Tests for the PySide6 dashboard page."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QPushButton

from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.gui.desktop.dashboard_page import DashboardPage
from pysysfan.profiles import ProfileManager
from pysysfan.state_file import (
    AlertState,
    DaemonStateFile,
    FanSpeedState,
    TemperatureState,
    write_state,
)


def _sample_state(
    timestamp: float | None = None,
    *,
    config_path: str = "C:/Users/test/.pysysfan/profiles/gaming.yaml",
) -> DaemonStateFile:
    timestamp = time.time() if timestamp is None else timestamp
    return DaemonStateFile(
        timestamp=timestamp,
        pid=4321,
        running=True,
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


def _create_multi_fan_profile_manager(tmp_path) -> ProfileManager:
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
            ),
            "chassis_fan": FanConfig(
                fan_id="/mb/control/1",
                curve="balanced",
                temp_ids=["/gpu/temp/0"],
                aggregation="max",
                header_name="Chassis Fan",
                allow_fan_off=False,
            ),
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


def test_dashboard_refresh_populates_snapshot(qtbot, tmp_path) -> None:
    """Refreshing the dashboard should populate compact summary widgets."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state_path = tmp_path / "daemon_state.json"
    write_state(_sample_state(config_path=str(config_path)), state_path)
    page = DashboardPage(
        state_path=state_path,
        service_status_getter=lambda: _task_status(),
        profile_manager=profile_manager,
    )
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.scroll_area.widgetResizable() is True
    assert page.main_splitter.count() == 2
    assert page.daemon_indicator.text() == "●"
    assert page.alerts_button.text() == "⚠ 1"
    assert page.active_profile_label.text() == "Gaming Mode"
    assert page.profile_status_badge.text() == "Active"
    assert (
        page.active_profile_meta_label.text() == "1 fan mappings • 1 sensors • 3 curves"
    )
    assert "Aggressive cooling" in page.active_profile_description_label.text()
    assert "CPU Fan → CPU / Package" in page.profile_mapping_label.text()
    assert page.fan_summary_layout.count() == 1
    assert page.fan_summary_layout.itemAt(0).widget().objectName() == (
        "cpu_fanSummaryCard"
    )
    assert page.temperature_plot.minimumHeight() >= 320
    assert page.fan_rpm_plot.minimumHeight() >= 240
    assert page.fan_target_plot.minimumHeight() >= 240
    assert page.findChild(QPushButton, "refreshButton") is None


def test_dashboard_shows_offline_message_without_state(qtbot, tmp_path) -> None:
    """Dashboard should report offline state when no state file exists."""
    page = DashboardPage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _task_status(installed=True),
    )
    qtbot.addWidget(page)
    page.show()

    page.refresh_data()

    assert page.daemon_indicator.text() == "●"
    assert page.alerts_button.text() == "⚠ 0"
    assert page.profile_status_badge.text() == "Offline"
    assert page.active_profile_label.text() == "No active config"
    assert "state file" in page.message_label.text().lower()
    assert page.fan_summary_empty_label.isVisible() is True


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
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state_path = tmp_path / "daemon_state.json"
    write_state(_sample_state(config_path=str(config_path)), state_path)
    page = DashboardPage(
        state_path=state_path,
        service_status_getter=lambda: _task_status(),
        profile_manager=profile_manager,
    )
    qtbot.addWidget(page)

    page.refresh_data()
    page.history_selector.setCurrentText("15 min")

    assert page._history_seconds == 900


def test_dashboard_graphs_default_to_grouped_and_controlled_series(
    qtbot,
    tmp_path,
) -> None:
    """Dashboard graphs should default to grouped fans and configured sensors."""
    profile_manager = _create_multi_fan_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    timestamp = time.time()
    state = DaemonStateFile(
        timestamp=timestamp,
        pid=4321,
        running=True,
        uptime_seconds=25.0,
        active_profile="gaming",
        poll_interval=1.0,
        config_path=str(config_path),
        fans_configured=2,
        curves_configured=1,
        temperatures=[
            TemperatureState(
                identifier="/cpu/temp/0",
                hardware_name="CPU",
                sensor_name="Package",
                value=61.5,
            ),
            TemperatureState(
                identifier="/gpu/temp/0",
                hardware_name="GPU",
                sensor_name="Edge",
                value=58.0,
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
            ),
            FanSpeedState(
                identifier="/mb/fan/1",
                control_identifier="/mb/control/1",
                hardware_name="Motherboard",
                sensor_name="Chassis Fan",
                rpm=980.0,
                current_control_pct=42.0,
                controllable=True,
            ),
        ],
        fan_targets={
            "/mb/control/0": 60.0,
            "/mb/control/1": 45.0,
        },
        recent_alerts=[],
    )
    state_path = tmp_path / "daemon_state.json"
    write_state(state, state_path)
    page = DashboardPage(
        state_path=state_path,
        service_status_getter=lambda: _task_status(),
        profile_manager=profile_manager,
    )
    qtbot.addWidget(page)

    page.refresh_data()

    assert page._graph_enabled_series["temperature"] == {
        "/cpu/temp/0",
        "/gpu/temp/0",
    }
    assert page._graph_enabled_series["fan_rpm"] == {"group::Motherboard"}
    assert page._graph_enabled_series["fan_target"] == {"group::Motherboard"}

    temperature_menu = page._graph_controls["temperature"]["menu"]
    fan_menu = page._graph_controls["fan_rpm"]["menu"]
    temperature_actions = [action.text() for action in temperature_menu.actions()]
    fan_actions = [action.text() for action in fan_menu.actions()]

    assert "CPU / Package" in temperature_actions
    assert "GPU / Edge" in temperature_actions
    assert all("Limit" not in text for text in temperature_actions)
    assert "Motherboard" in fan_actions
    assert any(text.startswith("Fan · Motherboard / CPU Fan") for text in fan_actions)
    assert page._graph_controls["fan_rpm"]["button"].text() == "Series (1)"


def test_dashboard_graph_series_menu_toggles_visibility(qtbot, tmp_path) -> None:
    """Users should be able to enable and disable individual graph series."""
    profile_manager = _create_multi_fan_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state_path = tmp_path / "daemon_state.json"
    write_state(
        DaemonStateFile(
            timestamp=time.time(),
            pid=4321,
            running=True,
            uptime_seconds=25.0,
            active_profile="gaming",
            poll_interval=1.0,
            config_path=str(config_path),
            fans_configured=2,
            curves_configured=1,
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
                ),
                FanSpeedState(
                    identifier="/mb/fan/1",
                    control_identifier="/mb/control/1",
                    hardware_name="Motherboard",
                    sensor_name="Chassis Fan",
                    rpm=980.0,
                    current_control_pct=42.0,
                    controllable=True,
                ),
            ],
            fan_targets={
                "/mb/control/0": 60.0,
                "/mb/control/1": 45.0,
            },
            recent_alerts=[],
        ),
        state_path,
    )
    page = DashboardPage(
        state_path=state_path,
        service_status_getter=lambda: _task_status(),
        profile_manager=profile_manager,
    )
    qtbot.addWidget(page)

    page.refresh_data()

    fan_menu = page._graph_controls["fan_rpm"]["menu"]
    group_action = next(
        action for action in fan_menu.actions() if action.text() == "Motherboard"
    )
    cpu_fan_action = next(
        action
        for action in fan_menu.actions()
        if action.text().startswith("Fan · Motherboard / CPU Fan")
    )

    assert group_action.isChecked() is True
    assert cpu_fan_action.isChecked() is False

    cpu_fan_action.setChecked(True)
    fan_menu = page._graph_controls["fan_rpm"]["menu"]
    group_action = next(
        action for action in fan_menu.actions() if action.text() == "Motherboard"
    )
    group_action.setChecked(False)

    assert page._graph_enabled_series["fan_rpm"] == {"series::/mb/fan/0"}
    assert page._graph_controls["fan_rpm"]["button"].text() == "Series (1)"
