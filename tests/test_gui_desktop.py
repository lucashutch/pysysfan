"""Tests for the PySide6 desktop GUI scaffold."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from pysysfan.gui.desktop.app import get_or_create_application
from pysysfan.gui.desktop.main_window import MainWindow


def test_get_or_create_application_reuses_instance() -> None:
    """The desktop bootstrap should reuse an existing QApplication."""
    app_one = get_or_create_application([])
    app_two = get_or_create_application([])

    assert app_one is app_two
    assert app_one.applicationName() == "PySysFan"
    assert app_one.windowIcon().isNull() is False


def test_main_window_has_expected_tabs(qtbot) -> None:
    """The initial desktop shell should expose the core top-level tabs."""
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "PySysFan"
    assert window.tab_widget.count() == 3
    assert [window.tab_widget.tabText(index) for index in range(3)] == [
        "Dashboard",
        "Config",
        "Service",
    ]
    assert window.windowIcon().isNull() is False
    assert (
        window.tab_widget.cornerWidget(Qt.Corner.TopRightCorner)
        is window.dashboard_page.status_corner_widget
    )
    assert "QTabBar::tab" in window.styleSheet()
