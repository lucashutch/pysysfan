"""Tests for the PySide6 dashboard page (V2 row-based layout)."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QFrame, QLabel

from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.gui.desktop.dashboard_page import DashboardPage
from pysysfan.gui.desktop.data_provider import DashboardDataProvider
from pysysfan.profiles import ProfileManager
from pysysfan.state_file import (
    AlertState,
    DaemonStateFile,
    FanSpeedState,
    TemperatureState,
    write_state,
)


# ------------------------------------------------------------------
# Fixtures / helpers
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
                message="High temperature: 90.0°C",
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


def _make_provider(
    tmp_path,
    *,
    state: DaemonStateFile | None = None,
    profile_manager: ProfileManager | None = None,
    installed: bool = True,
) -> DashboardDataProvider:
    """Build a ``DashboardDataProvider`` with mocked backends."""
    state_path = tmp_path / "daemon_state.json"
    history_path = tmp_path / "daemon_history.ndjson"
    if state is not None:
        write_state(state, state_path)
    return DashboardDataProvider(
        state_path=state_path,
        history_path=history_path,
        service_status_getter=lambda: _task_status(installed=installed),
        profile_manager=profile_manager or ProfileManager(config_dir=tmp_path),
    )


def _make_page(qtbot, provider: DashboardDataProvider) -> DashboardPage:
    """Create a DashboardPage wired to the given provider."""
    page = DashboardPage(provider=provider)
    qtbot.addWidget(page)
    return page


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_dashboard_creates_v2_layout_structure(qtbot, tmp_path) -> None:
    """The V2 dashboard should have sidebar, table header, fan rows."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    assert page.objectName() == "dashboardRoot"
    assert page.scroll_area.widgetResizable() is True
    assert page.sidebar is not None
    assert page.sidebar.objectName() == "sidebar"
    assert page.findChild(QFrame, "tableHeader") is not None
    assert page.fan_rows_container is not None
    assert page.sidebar._alerts_label.text() == "⚠ 0"


def test_dashboard_populates_rows_from_state(qtbot, tmp_path) -> None:
    """Refreshing the provider should populate fan rows in the page."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    assert len(page._fan_rows) == 1
    row = page._fan_rows[0]
    assert row.objectName() == "cpuFanRow"

    # Check cells in the row
    group_label = row.findChild(QLabel, "fanRowGroup")
    assert group_label is not None
    assert group_label.text() == "CPU Fan"

    curve_label = row.findChild(QLabel, "fanRowCurve")
    assert curve_label is not None
    assert curve_label.text() == "balanced"

    target_label = row.findChild(QLabel, "fanRowTarget")
    assert target_label is not None
    assert target_label.text() == "60%"

    actual_label = row.findChild(QLabel, "fanRowActual")
    assert actual_label is not None
    assert actual_label.text() == "55.0%"

    rpm_label = row.findChild(QLabel, "fanRowRpm")
    assert rpm_label is not None
    assert rpm_label.text() == "1325 RPM"

    sensors_label = row.findChild(QLabel, "fanRowSensors")
    assert sensors_label is not None
    assert "CPU / Package · 61.5°C" in sensors_label.text()


def test_dashboard_header_bar_populated_from_state(qtbot, tmp_path) -> None:
    """The sidebar should show profile, uptime, and poll info from state."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    assert "Gaming Mode" in page.sidebar._profile_label.text()
    assert "Poll:" in page.sidebar._poll_label.text()


def test_dashboard_health_summary_shows_hottest_and_max_speed(qtbot, tmp_path) -> None:
    """Sidebar should display temperature and max fan info."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    # Sidebar shows CPU temp gauge and max fan
    cpu_temp_label = page.sidebar._cpu_temp.findChild(QLabel, "sidebarTempCPU")
    assert cpu_temp_label is not None
    assert "62" in cpu_temp_label.text() or "—" not in cpu_temp_label.text()
    assert (
        "1325" in page.sidebar._max_fan_label.text()
        or "1,325" in page.sidebar._max_fan_label.text()
    )


def test_dashboard_alerts_button_shows_count(qtbot, tmp_path) -> None:
    """The sidebar notifications control should reflect the number of recent alerts."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    assert page.sidebar._alerts_label.text() == "⚠ 1"
    assert "1" in page.sidebar._alerts_label.text()


def test_dashboard_shows_offline_message_without_state(qtbot, tmp_path) -> None:
    """Dashboard should report offline state when no state file exists."""
    provider = _make_provider(tmp_path, installed=True)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    assert page.sidebar._alerts_label.text() == "⚠ 0"
    assert "state file" in page.message_label.text().lower()
    assert page.message_label.isHidden() is False


def test_dashboard_offline_clears_rows(qtbot, tmp_path) -> None:
    """Going offline should remove all fan rows."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()
    assert len(page._fan_rows) == 1

    # Remove state file to trigger offline
    state_path = provider._state_path
    state_path.unlink()
    provider.refresh_data()

    assert len(page._fan_rows) == 0


def test_dashboard_multi_fan_creates_multiple_rows(qtbot, tmp_path) -> None:
    """Multiple fan groups should result in multiple rows."""
    profile_manager = _create_multi_fan_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = DaemonStateFile(
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
            ),
            TemperatureState(
                identifier="/gpu/temp/0",
                hardware_name="GPU",
                sensor_name="Edge",
                value=58.0,
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
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    assert len(page._fan_rows) == 2
    group_names = [
        row.findChild(QLabel, "fanRowGroup").text() for row in page._fan_rows
    ]
    assert "Chassis Fan" in group_names
    assert "CPU Fan" in group_names


def test_dashboard_start_service_uses_provider(qtbot, tmp_path) -> None:
    """Starting the service from the dashboard should delegate to the provider."""
    calls: list[str] = []
    provider = DashboardDataProvider(
        state_path=tmp_path / "missing.json",
        history_path=tmp_path / "daemon_history.ndjson",
        service_status_getter=lambda: _task_status(installed=True),
        service_action_runner=lambda action: (calls.append(action) or True, "Started"),
    )
    page = _make_page(qtbot, provider)

    page.start_service()

    assert calls == ["start"]
    assert page.message_label.text() == "Started"


def test_dashboard_polling_controlled_by_show_hide(qtbot, tmp_path) -> None:
    """The dashboard page itself should not control polling.

    Polling is owned by the main window (it keeps graphs + sidebar updating
    while switching tabs, and pauses while the main window is minimized/hidden).
    """
    provider = _make_provider(tmp_path, installed=True)
    page = _make_page(qtbot, provider)

    assert provider._refresh_timer.isActive() is False

    page.show()
    qtbot.waitUntil(lambda: not provider._refresh_timer.isActive())

    page.hide()
    qtbot.waitUntil(lambda: not provider._refresh_timer.isActive())


def test_dashboard_temperature_color_thresholds(qtbot, tmp_path) -> None:
    """Temperature color should follow the green/amber/red thresholds."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    assert page._temperature_color(59.9) == "#22c55e"
    assert page._temperature_color(60.0) == "#f59e0b"
    assert page._temperature_color(79.9) == "#f59e0b"
    assert page._temperature_color(80.0) == "#ef4444"


def test_dashboard_display_group_name_formatting(qtbot, tmp_path) -> None:
    """Group names should be title-cased with known acronyms uppercased."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    assert page._display_group_name("cpu_fan") == "CPU Fan"
    assert page._display_group_name("gpu_pump") == "GPU Pump"
    assert page._display_group_name("chassis_fan") == "Chassis Fan"


def test_dashboard_format_uptime(qtbot, tmp_path) -> None:
    """Uptime formatter should produce human-readable strings."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    assert page._format_uptime(25.0) == "0m"
    assert page._format_uptime(3600.0 + 120.0) == "1h 02m"
    assert page._format_uptime(2 * 3600.0 + 14 * 60.0) == "2h 14m"


def test_dashboard_health_alerts_count_zero_when_no_alerts(qtbot, tmp_path) -> None:
    """With no alerts, the sidebar should show 'Alerts: 0'."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = DaemonStateFile(
        timestamp=time.time(),
        pid=4321,
        running=True,
        uptime_seconds=60.0,
        active_profile="gaming",
        poll_interval=1.0,
        config_path=str(config_path),
        fans_configured=1,
        curves_configured=1,
        temperatures=[
            TemperatureState(
                identifier="/cpu/temp/0",
                hardware_name="CPU",
                sensor_name="Package",
                value=55.0,
            )
        ],
        fan_speeds=[
            FanSpeedState(
                identifier="/mb/fan/0",
                control_identifier="/mb/control/0",
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                rpm=900.0,
                current_control_pct=40.0,
                controllable=True,
            )
        ],
        fan_targets={"/mb/control/0": 40.0},
        recent_alerts=[],
    )
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    assert page.sidebar._alerts_label.text() == "⚠ 0"
    assert "0" in page.sidebar._alerts_label.text()


def test_dashboard_empty_fan_config_shows_empty_label(qtbot, tmp_path) -> None:
    """When the config has no fans, an empty-state label should appear."""
    state = DaemonStateFile(
        timestamp=time.time(),
        pid=4321,
        running=True,
        uptime_seconds=5.0,
        active_profile="default",
        poll_interval=1.0,
        config_path="nonexistent.yaml",
        fans_configured=0,
        curves_configured=0,
        temperatures=[],
        fan_speeds=[],
        fan_targets={},
        recent_alerts=[],
    )
    provider = _make_provider(tmp_path, state=state)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    assert len(page._fan_rows) == 0
    empty_label = page.fan_rows_container.findChild(QLabel, "fanRowsEmpty")
    assert empty_label is not None
    assert "No active fan mappings" in empty_label.text()
