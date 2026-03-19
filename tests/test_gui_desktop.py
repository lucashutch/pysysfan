"""Tests for the PySide6 desktop GUI scaffold."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")

from pysysfan.gui.desktop.app import get_or_create_application
from pysysfan.gui.desktop.main_window import MainWindow


def test_get_or_create_application_reuses_instance() -> None:
    """The desktop bootstrap should reuse an existing QApplication."""
    app_one = get_or_create_application([])
    app_two = get_or_create_application([])

    assert app_one is app_two
    assert app_one.applicationName() == "PySysFan"
    assert app_one.windowIcon().isNull() is False


def test_main_window_uses_sidebar_stack_navigation(qtbot) -> None:
    """The desktop shell should expose a shared sidebar and stacked pages."""
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "PySysFan"
    assert window.sidebar.objectName() == "sidebar"
    assert window.page_stack.count() == 4
    assert window.page_stack.currentIndex() == 0
    assert window.sidebar._nav_buttons[0].isChecked() is True
    assert window.sidebar._nav_buttons[1].text() == "Graphs"
    assert window.sidebar._nav_buttons[2].text() == "Config"
    assert window.sidebar._nav_buttons[3].text() == "Service"
    assert window.windowIcon().isNull() is False
    assert "QFrame#sidebar" in window.sidebar.styleSheet()


def test_main_window_hides_to_tray_when_minimized_preference_enabled(qtbot) -> None:
    """A minimize action should hide the window when tray mode is enabled."""
    window = MainWindow()
    qtbot.addWidget(window)
    tray_icon = MagicMock()
    tray_icon.isVisible.return_value = True
    window._tray_icon = tray_icon

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "pysysfan.gui.desktop.main_window.get_minimize_to_tray",
            lambda: True,
        )
        window.show()
        window.showMinimized()
        qtbot.waitUntil(lambda: not window.isVisible())

    tray_icon.showMessage.assert_called_once()
