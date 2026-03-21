"""Tests for the G5 Tabbed Focus graphs page."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QFrame, QPushButton

from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.gui.desktop.data_provider import DashboardDataProvider
from pysysfan.gui.desktop.graphs_page import GraphsPage, LegendItem
from pysysfan.profiles import ProfileManager

import pyqtgraph as pg
from pysysfan.state_file import (
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


def _task_status(installed: bool = True):
    from types import SimpleNamespace

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
        description="Aggressive cooling",
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


def _make_page(qtbot, provider: DashboardDataProvider) -> GraphsPage:
    page = GraphsPage(provider=provider)
    qtbot.addWidget(page)
    return page


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_graphs_page_structure(qtbot, tmp_path) -> None:
    """Page has correct object name and structural widgets."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    assert page.objectName() == "graphsRoot"
    assert page.findChild(QFrame, "graphsHeader") is not None
    assert page.findChild(QFrame, "graphsDrawer") is not None
    assert page.findChild(QFrame, "graphsControlsRow") is not None
    assert page.findChild(QFrame, "graphsStatsRow") is not None
    assert page.findChild(QFrame, "graphsLegendBar") is not None
    assert page.findChild(QPushButton, "graphTab_temperature") is not None
    assert page.findChild(QPushButton, "graphTab_fan_rpm") is not None
    assert page.findChild(QPushButton, "historyBtn_60") is not None
    assert page.findChild(QPushButton, "historyBtn_300") is not None
    assert page.findChild(QPushButton, "historyBtn_900") is not None


def test_tab_switching_changes_active_tab(qtbot, tmp_path) -> None:
    """Clicking the Fan RPM tab changes the active graph type."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    assert page.active_tab == "temperature"

    fan_btn = page.findChild(QPushButton, "graphTab_fan_rpm")
    fan_btn.click()

    assert page.active_tab == "fan_rpm"
    assert fan_btn.isChecked()
    temp_btn = page.findChild(QPushButton, "graphTab_temperature")
    assert not temp_btn.isChecked()


def test_tab_switching_back_to_temperature(qtbot, tmp_path) -> None:
    """Switching to fan_rpm and back to temperature works."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    page.findChild(QPushButton, "graphTab_fan_rpm").click()
    assert page.active_tab == "fan_rpm"

    page.findChild(QPushButton, "graphTab_temperature").click()
    assert page.active_tab == "temperature"


def test_history_buttons_update_provider(qtbot, tmp_path) -> None:
    """Clicking a history button updates the provider's history window."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    assert provider.history_seconds == 60

    btn_300 = page.findChild(QPushButton, "historyBtn_300")
    btn_300.click()
    assert provider.history_seconds == 300
    assert btn_300.isChecked()
    assert not page.findChild(QPushButton, "historyBtn_60").isChecked()


def test_legend_items_for_temperature(qtbot, tmp_path) -> None:
    """Legend items are created for temperature series after data refresh."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    items = page._legend_items
    assert len(items) > 0
    assert all(isinstance(item, LegendItem) for item in items)

    # Should have labels for available temperature sensors
    labels = [item.text_label.text() for item in items]
    assert any("CPU" in label for label in labels)


def test_legend_toggle_changes_visibility(qtbot, tmp_path) -> None:
    """Clicking a legend item toggles between filled and outline circles."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    items = page._legend_items
    assert len(items) > 0

    item = items[0]
    assert item.visible is True
    assert item.color_label.text() == "\u25cf"

    # Simulate click
    item.mousePressEvent(None)

    assert item.visible is False
    assert item.color_label.text() == "\u25cb"
    assert item.series_id not in page.enabled_series["temperature"]


def test_legend_toggle_triggers_refresh(qtbot, tmp_path) -> None:
    """Toggling a legend item triggers a plot refresh."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    items = page._legend_items
    assert len(items) > 0

    refresh_calls = []
    original_refresh = page._refresh_plot

    def tracking_refresh():
        refresh_calls.append(True)
        original_refresh()

    page._refresh_plot = tracking_refresh

    items[0].mousePressEvent(None)
    assert len(refresh_calls) == 1


def test_default_temperature_selection(qtbot, tmp_path) -> None:
    """Default: first 5 temperature series enabled on first data."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    temp_enabled = page.enabled_series["temperature"]
    catalog = provider.build_temperature_catalog()
    expected = set(list(catalog.keys())[:5])
    assert temp_enabled == expected


def test_default_fan_rpm_selection_groups(qtbot, tmp_path) -> None:
    """Default: group:: entries selected for fan RPM tab."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    # Switch to fan_rpm tab to trigger initialization
    page.findChild(QPushButton, "graphTab_fan_rpm").click()

    fan_enabled = page.enabled_series["fan_rpm"]
    catalog = provider.build_fan_rpm_catalog()
    group_keys = {k for k in catalog if k.startswith("group::")}

    if group_keys:
        assert fan_enabled == group_keys
    else:
        assert len(fan_enabled) <= 3


def test_empty_state_handled_gracefully(qtbot, tmp_path) -> None:
    """Page works without errors when no data is available."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    # No data, no crash
    provider.refresh_data()

    assert page.active_tab == "temperature"
    assert len(page._legend_items) == 0


def test_tabs_maintain_independent_series(qtbot, tmp_path) -> None:
    """Each tab maintains its own set of enabled series."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    temp_enabled = set(page.enabled_series["temperature"])

    # Switch to fan_rpm
    page.findChild(QPushButton, "graphTab_fan_rpm").click()
    fan_enabled = set(page.enabled_series["fan_rpm"])

    # They should be different sets (different series IDs)
    assert temp_enabled != fan_enabled or (not temp_enabled and not fan_enabled)

    # Switch back — temperature selection should be preserved
    page.findChild(QPushButton, "graphTab_temperature").click()
    assert page.enabled_series["temperature"] == temp_enabled


def test_legend_rebuilds_on_tab_switch(qtbot, tmp_path) -> None:
    """Switching tabs rebuilds the legend with the new tab's series."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    temp_labels = [item.text_label.text() for item in page._legend_items]

    page.findChild(QPushButton, "graphTab_fan_rpm").click()

    fan_labels = [item.text_label.text() for item in page._legend_items]

    # The labels should differ between tabs
    assert temp_labels != fan_labels


def test_clicking_active_tab_stays_checked(qtbot, tmp_path) -> None:
    """Clicking the already-active tab should not uncheck its button."""
    provider = _make_provider(tmp_path)
    page = _make_page(qtbot, provider)

    temp_btn = page.findChild(QPushButton, "graphTab_temperature")
    assert temp_btn.isChecked()

    # Click the already-active temperature tab
    temp_btn.click()

    assert page.active_tab == "temperature"
    assert temp_btn.isChecked()


def test_legend_muted_color_from_theme(qtbot, tmp_path) -> None:
    """Hidden legend items use the theme's muted color, not a hardcoded value."""
    from pysysfan.gui.desktop.theme import desktop_colors

    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    items = page._legend_items
    assert len(items) > 0

    expected_muted = desktop_colors(page.palette())["muted"]
    item = items[0]
    item.mousePressEvent(None)
    assert expected_muted in item.text_label.styleSheet()


# ------------------------------------------------------------------
# DashboardPlotWidget series management
# ------------------------------------------------------------------


def test_plot_widget_update_series_creates_item(qtbot) -> None:
    """update_series creates a PlotDataItem on first call."""
    from pysysfan.gui.desktop.plotting import DashboardPlotWidget

    pw = DashboardPlotWidget()
    qtbot.addWidget(pw)

    pw.update_series("temp_0", [0, 1], [30, 40], pg.mkPen("r"))
    assert "temp_0" in pw._series_items
    assert len(pw._series_items) == 1


def test_plot_widget_update_series_reuses_item(qtbot) -> None:
    """update_series reuses the same PlotDataItem on subsequent calls."""
    from pysysfan.gui.desktop.plotting import DashboardPlotWidget

    pw = DashboardPlotWidget()
    qtbot.addWidget(pw)

    pw.update_series("temp_0", [0, 1], [30, 40], pg.mkPen("r"))
    first_item = pw._series_items["temp_0"]

    pw.update_series("temp_0", [0, 1, 2], [30, 40, 50], pg.mkPen("b"))
    assert pw._series_items["temp_0"] is first_item
    assert len(pw._series_items) == 1


def test_plot_widget_remove_stale_series(qtbot) -> None:
    """remove_stale_series removes items not in the active set."""
    from pysysfan.gui.desktop.plotting import DashboardPlotWidget

    pw = DashboardPlotWidget()
    qtbot.addWidget(pw)

    pw.update_series("a", [0], [1], pg.mkPen("r"))
    pw.update_series("b", [0], [2], pg.mkPen("g"))
    pw.update_series("c", [0], [3], pg.mkPen("b"))

    pw.remove_stale_series({"a", "c"})
    assert "b" not in pw._series_items
    assert set(pw._series_items.keys()) == {"a", "c"}


def test_plot_widget_clear_all_series(qtbot) -> None:
    """clear_all_series empties the series dict."""
    from pysysfan.gui.desktop.plotting import DashboardPlotWidget

    pw = DashboardPlotWidget()
    qtbot.addWidget(pw)

    pw.update_series("x", [0], [1], pg.mkPen("r"))
    pw.update_series("y", [0], [2], pg.mkPen("g"))
    assert len(pw._series_items) == 2

    pw.clear_all_series()
    assert len(pw._series_items) == 0


# ------------------------------------------------------------------
# GraphsPage series reuse integration
# ------------------------------------------------------------------


def test_refresh_reuses_series_items(qtbot, tmp_path) -> None:
    """Repeated _refresh_plot calls reuse the same PlotDataItem objects."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    if page._plot_widget is None:
        pytest.skip("pyqtgraph not available")

    # Capture items after first refresh
    first_items = dict(page._plot_widget._series_items)
    assert len(first_items) > 0

    # Refresh again — same objects should be reused
    page._refresh_plot()
    for sid, item in first_items.items():
        assert page._plot_widget._series_items.get(sid) is item


def test_stale_series_removed_on_disable(qtbot, tmp_path) -> None:
    """Disabling a series via legend removes its PlotDataItem."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    if page._plot_widget is None:
        pytest.skip("pyqtgraph not available")

    items_before = set(page._plot_widget._series_items.keys())
    assert len(items_before) > 0

    # Toggle off the first legend item
    legend_item = page._legend_items[0]
    disabled_sid = legend_item.series_id
    legend_item.mousePressEvent(None)

    assert disabled_sid not in page._plot_widget._series_items


def test_tab_switch_clears_series(qtbot, tmp_path) -> None:
    """Switching tabs clears old series from the plot widget."""
    profile_manager = _create_profile_manager(tmp_path)
    config_path = profile_manager.get_profile_config_path("gaming")
    state = _sample_state(config_path=str(config_path))
    provider = _make_provider(tmp_path, state=state, profile_manager=profile_manager)
    page = _make_page(qtbot, provider)

    provider.refresh_data()

    if page._plot_widget is None:
        pytest.skip("pyqtgraph not available")

    # Temperature tab has items
    assert len(page._plot_widget._series_items) > 0

    # Switch to fan_rpm — old items should be cleared
    page.findChild(QPushButton, "graphTab_fan_rpm").click()

    # After switch, only fan_rpm series should be present (or empty if no history)
    temp_ids = {
        sid
        for sid in page._plot_widget._series_items
        if not sid.startswith("group::") and not sid.startswith("series::")
    }
    # Temperature sensor IDs (plain paths) should not remain
    for sid in temp_ids:
        assert sid not in provider.build_temperature_catalog()
