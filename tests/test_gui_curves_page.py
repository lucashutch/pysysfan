"""Tests for the PySide6 curves page."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMessageBox

from pysysfan.gui.desktop.curves_page import CurvesPage


class FakeCurvesClient:
    """Small fake daemon client for curve page tests."""

    def __init__(self):
        self.curves = {
            "balanced": {
                "name": "balanced",
                "points": [[30, 30], [60, 60], [85, 100]],
                "hysteresis": 3.0,
            },
            "silent": {
                "name": "silent",
                "points": [[30, 20], [60, 40], [85, 80]],
                "hysteresis": 4.0,
            },
        }
        self.fans = {
            "cpu_fan": {
                "fan_id": "/fan/0",
                "curve": "balanced",
                "temp_ids": ["/cpu/0"],
                "aggregation": "max",
                "allow_fan_off": False,
            }
        }
        self.saved_curve: tuple[str, list[list[float]], float] | None = None
        self.assigned_curve: tuple[str, str] | None = None

    def list_curves(self):
        return {"curves": self.curves}

    def list_fans(self):
        return {"fans": self.fans}

    def validate_curve(self, points, hysteresis=3.0):
        return {"valid": True, "errors": []}

    def create_curve(self, name, points, hysteresis=3.0):
        self.saved_curve = (name, points, hysteresis)
        self.curves[name] = {
            "name": name,
            "points": points,
            "hysteresis": hysteresis,
        }
        return {"success": True, "name": name}

    def delete_curve(self, name):
        self.curves.pop(name, None)
        return {"success": True, "deleted": name}

    def preview_curve(self, points, temperature, hysteresis=3.0):
        return {"speed_percent": 72.5}

    def update_fan(
        self,
        name,
        fan_id=None,
        curve=None,
        temp_ids=None,
        aggregation=None,
        allow_fan_off=None,
    ):
        self.assigned_curve = (name, curve)
        self.fans[name]["curve"] = curve
        return {"success": True, "name": name}


def test_curves_page_refresh_populates_curve_and_fan_data(qtbot) -> None:
    """Refreshing should populate the selector, table, and fan assignment widgets."""
    fake_client = FakeCurvesClient()
    page = CurvesPage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.connection_label.text() == "Connection: Connected"
    assert page.curve_selector.count() == 2
    assert page.points_table.rowCount() == 3
    assert page.hysteresis_spin.value() == 3.0
    assert page.fan_selector.count() == 1
    assert page.fan_assignment_label.text() == "Fan assignment: cpu_fan -> balanced"


def test_curves_page_save_uses_validation_and_persists_curve(qtbot) -> None:
    """Saving should validate and persist the edited curve."""
    fake_client = FakeCurvesClient()
    page = CurvesPage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)
    page.refresh_data()

    page.points_table.item(0, 1).setText("35")
    page.hysteresis_spin.setValue(5.0)
    page.save_curve()

    assert fake_client.saved_curve == (
        "balanced",
        [[30.0, 35.0], [60.0, 60.0], [85.0, 100.0]],
        5.0,
    )
    assert page.message_label.text() == "Curve 'balanced' saved"


def test_curves_page_assigns_selected_curve_to_fan(qtbot) -> None:
    """Assigning should update the selected fan with the selected curve."""
    fake_client = FakeCurvesClient()
    page = CurvesPage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)
    page.refresh_data()

    page.curve_selector.setCurrentText("silent")
    page.assign_curve_to_fan()

    assert fake_client.assigned_curve == ("cpu_fan", "silent")
    assert page.message_label.text() == "Assigned curve 'silent' to fan 'cpu_fan'"


def test_curves_page_deletes_selected_curve(qtbot) -> None:
    """Deleting should remove the selected curve after confirmation."""
    fake_client = FakeCurvesClient()
    page = CurvesPage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)
    page.refresh_data()

    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        page.delete_curve()

    assert "balanced" not in fake_client.curves
