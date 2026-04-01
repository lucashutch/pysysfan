"""Application bootstrap for the PySide6 desktop GUI."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QFont, QFontInfo
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from pysysfan import __version__  # type: ignore[unresolved-attribute]
from pysysfan.gui.desktop.icons import app_icon, configure_windows_app_id
from pysysfan.gui.desktop.main_window import MainWindow


def _preferred_ui_font() -> QFont:
    """Return the preferred application font for the desktop shell."""
    preferred_families = [
        "IBM Plex Mono",
        "Inter",
        "Segoe UI Variable Text",
        "Segoe UI Variable",
        "Segoe UI",
    ]
    font = QFont()
    font.setPointSize(10)
    font.setWeight(QFont.Weight.Medium)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    for family in preferred_families:
        candidate = QFont(family, 10)
        if QFontInfo(candidate).family().lower() == family.lower():
            candidate.setWeight(QFont.Weight.Medium)
            candidate.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            return candidate
    return font


class TrayController(QObject):
    """Manage the optional system tray integration for the desktop GUI."""

    def __init__(self, app: QApplication, window: MainWindow) -> None:
        super().__init__(window)
        self._app = app
        self._window = window
        self._tray_icon: QSystemTrayIcon | None = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        tray_icon = QSystemTrayIcon(app_icon(), window)
        tray_icon.setToolTip("PySysFan")
        tray_icon.setContextMenu(self._build_menu())
        tray_icon.activated.connect(self._handle_activation)
        tray_icon.show()

        self._tray_icon = tray_icon
        self._app.setQuitOnLastWindowClosed(False)
        self._window.enable_tray_integration(tray_icon)

    def _build_menu(self) -> QMenu:
        """Create the tray icon context menu."""
        menu = QMenu(self._window)

        show_action = QAction("Show PySysFan", menu)
        show_action.triggered.connect(self._window.show_from_tray)
        menu.addAction(show_action)

        hide_action = QAction("Hide Window", menu)
        hide_action.triggered.connect(self._window.hide)
        menu.addAction(hide_action)

        refresh_action = QAction("Refresh Data", menu)
        refresh_action.triggered.connect(self.refresh_window)
        menu.addAction(refresh_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)
        return menu

    def refresh_window(self) -> None:
        """Ask each top-level page to refresh its local data."""
        for page in (
            self._window.dashboard_page,
            self._window.curves_page,
            self._window.service_page,
        ):
            refresh = getattr(page, "refresh_data", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    continue

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Restore or hide the window when the tray icon is activated."""
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            if self._window.isVisible() and not self._window.isMinimized():
                self._window.hide()
            else:
                self._window.show_from_tray()

    def quit_application(self) -> None:
        """Exit the application from the tray menu."""
        self._window.request_exit()
        self._app.quit()


def get_or_create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Return the active QApplication, creating one if needed."""
    app = QApplication.instance()
    if app is None:
        configure_windows_app_id()
        app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName("PySysFan")
    app.setApplicationDisplayName("PySysFan")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("pysysfan")
    app.setOrganizationDomain("github.com/lucashutch/pysysfan")
    app.setWindowIcon(app_icon())
    app.setFont(_preferred_ui_font())
    return app


def launch_gui(argv: Sequence[str] | None = None) -> int:
    """Create the application shell and enter the Qt event loop."""
    app = get_or_create_application(argv)
    window = MainWindow()
    setattr(app, "_pysysfan_tray_controller", TrayController(app, window))
    window.show()
    return app.exec()
