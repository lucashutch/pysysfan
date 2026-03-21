"""Tests for the PySide6 curves page."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMessageBox

from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.gui.desktop.curves_page import CurvesPage
from pysysfan.profiles import DEFAULT_PROFILE_NAME, ProfileManager


def _write_profile_config(
    profile_manager: ProfileManager, profile_name: str, curve_name: str
) -> None:
    config = Config(
        poll_interval=1.0,
        fans={
            "cpu_fan": FanConfig(
                fan_id="/mb/control/0",
                curve=curve_name,
                temp_ids=["/cpu/temp/0"],
                aggregation="max",
                allow_fan_off=False,
            )
        },
        curves={
            curve_name: CurveConfig(
                points=[(30, 30), (60, 60), (85, 100)],
                hysteresis=3.0,
            ),
            "silent": CurveConfig(
                points=[(30, 20), (60, 40), (85, 80)],
                hysteresis=4.0,
            ),
        },
        update=UpdateConfig(auto_check=False),
    )
    config.save(profile_manager.get_profile_config_path(profile_name))


def test_curves_page_refresh_populates_curve_and_fan_data(qtbot, tmp_path) -> None:
    """Refreshing should populate selectors and current config values."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.profile_selector.currentText() == "default"
    assert page.curve_selector.count() >= 2
    assert page.points_table.rowCount() == 3
    assert page.hysteresis_spin.value() == 3.0
    assert page.fan_selector.count() == 1
    assert page.fan_curve_selector.currentText() == "balanced"
    assert page.temp_ids_edit.text() == "/cpu/temp/0"
    assert page.preview_plot.minimumWidth() >= 300
    assert page.preview_plot.minimumHeight() >= 400
    assert page.points_table.columnWidth(0) >= 180
    assert getattr(page, "allow_fan_off_checkbox", None) is None


def test_curves_accordion_sections_can_stay_open_independently(qtbot, tmp_path) -> None:
    """Accordion sections should no longer force each other closed."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)
    page.refresh_data()

    first, second = page.accordion.sections[:2]
    first.set_open(True)
    second.set_open(True)

    assert first.is_open() is True
    assert second.is_open() is True

    first.header_button.click()

    assert first.is_open() is False
    assert second.is_open() is True


def test_curves_page_save_persists_curve_to_yaml(qtbot, tmp_path) -> None:
    """Saving should write curve changes directly to the YAML config."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)
    page.refresh_data()

    page.points_table.item(0, 1).setText("35.0")
    page.hysteresis_spin.setValue(5.0)
    page.save_curve()

    _, config_path, reloaded = (
        "default",
        profile_manager.get_profile_config_path(DEFAULT_PROFILE_NAME),
        Config.load(profile_manager.get_profile_config_path(DEFAULT_PROFILE_NAME)),
    )
    assert config_path.exists()
    assert reloaded.curves["balanced"].points[0] == (30.0, 35.0)
    assert reloaded.curves["balanced"].hysteresis == 5.0
    assert "daemon will reload" in page.message_label.text().lower()


def test_curves_page_save_general_settings_persists_poll_interval(
    qtbot,
    tmp_path,
) -> None:
    """Saving general settings should persist the poll interval independently."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)
    page.refresh_data()

    page.poll_interval_spin.setValue(1.0)
    page.save_general_settings()

    reloaded = Config.load(
        profile_manager.get_profile_config_path(DEFAULT_PROFILE_NAME)
    )
    assert reloaded.poll_interval == 1.0
    assert "saved general settings" in page.message_label.text().lower()


def test_curves_page_saves_selected_fan_settings(qtbot, tmp_path) -> None:
    """Saving fan settings should update the selected fan block in YAML."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)
    page.refresh_data()

    page.fan_curve_selector.setCurrentText("silent")
    page.temp_ids_edit.setText("/cpu/temp/0, /gpu/temp/0")
    page.aggregation_selector.setCurrentText("average")
    page.save_fan_settings()

    reloaded = Config.load(
        profile_manager.get_profile_config_path(DEFAULT_PROFILE_NAME)
    )
    fan = reloaded.fans["cpu_fan"]
    assert fan.curve == "silent"
    assert fan.temp_ids == ["/cpu/temp/0", "/gpu/temp/0"]
    assert fan.aggregation == "average"
    assert fan.allow_fan_off is True


def test_curves_page_deletes_unused_curve(qtbot, tmp_path) -> None:
    """Deleting an unused curve should remove it from the YAML config."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    config_path = profile_manager.get_profile_config_path(DEFAULT_PROFILE_NAME)
    config = Config.load(config_path)
    config.curves["custom"] = CurveConfig(
        points=[(35, 25), (65, 55), (85, 90)],
        hysteresis=2.0,
    )
    config.save(config_path)
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)
    page.refresh_data()
    page.curve_selector.setCurrentText("custom")

    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        page.delete_curve()

    reloaded = Config.load(
        profile_manager.get_profile_config_path(DEFAULT_PROFILE_NAME)
    )
    assert "custom" not in reloaded.curves


def test_curves_page_switch_profile_updates_editor(qtbot, tmp_path) -> None:
    """Switching profiles should reload the curve editor from the selected YAML file."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    _write_profile_config(profile_manager, "gaming", "silent")
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)
    page.refresh_data()

    page.profile_selector.setCurrentText("gaming")
    page.switch_profile()

    assert profile_manager.get_active_profile() == "gaming"
    assert page.curve_selector.currentText() == "silent"


def test_curves_page_can_create_profile(qtbot, tmp_path) -> None:
    """Users should be able to create a new profile from the Config tab."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)
    page.refresh_data()

    with patch("pysysfan.gui.desktop.curves_page.QInputDialog.getText") as get_text:
        get_text.return_value = ("Gaming Mode", True)
        page.create_profile()

    assert profile_manager.get_active_profile() == "gaming_mode"
    assert profile_manager.get_profile_config_path("gaming_mode").exists()
    assert "created and switched" in page.message_label.text().lower()


def test_curves_page_can_rename_profile_display_name(qtbot, tmp_path) -> None:
    """Users should be able to rename the visible profile name from the Config tab."""
    profile_manager = ProfileManager(config_dir=tmp_path)
    _write_profile_config(profile_manager, DEFAULT_PROFILE_NAME, "balanced")
    page = CurvesPage(profile_manager=profile_manager)
    qtbot.addWidget(page)
    page.refresh_data()

    with patch("pysysfan.gui.desktop.curves_page.QInputDialog.getText") as get_text:
        get_text.return_value = ("Quiet Everyday", True)
        page.rename_profile()

    default_profile = profile_manager.get_profile(DEFAULT_PROFILE_NAME)
    assert default_profile.metadata.display_name == "Quiet Everyday"
    assert page.profile_selector.currentText() == "Quiet Everyday (default)"
    assert "renamed profile" in page.message_label.text().lower()
