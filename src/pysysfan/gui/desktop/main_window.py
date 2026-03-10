"""Main window for the PySide6 desktop GUI."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QSystemTrayIcon, QTabWidget, QWidget

from pysysfan.gui.desktop.curves_page import CurvesPage
from pysysfan.gui.desktop.dashboard_page import DashboardPage
from pysysfan.gui.desktop.icons import app_icon
from pysysfan.gui.desktop.preferences import get_minimize_to_tray
from pysysfan.gui.desktop.service_page import ServicePage
from pysysfan.gui.desktop.theme import main_window_stylesheet


class MainWindow(QMainWindow):
    """Native desktop shell for local PySysFan management."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("mainWindow")
        self.setWindowTitle("PySysFan")
        self.setWindowIcon(app_icon())
        self.resize(1520, 980)
        self._allow_close = False
        self._tray_notice_shown = False
        self._tray_icon: QSystemTrayIcon | None = None

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("mainTabs")
        self.tab_widget.setDocumentMode(True)
        self.setCentralWidget(self.tab_widget)

        self.dashboard_page = DashboardPage(parent=self)
        self.curves_page = CurvesPage(parent=self)
        self.service_page = ServicePage(parent=self)

        self.tab_widget.addTab(self.dashboard_page, "Dashboard")
        self.tab_widget.addTab(self.curves_page, "Config")
        self.tab_widget.addTab(self.service_page, "Service")
        self.tab_widget.setCornerWidget(
            self.dashboard_page.status_corner_widget,
            Qt.Corner.TopRightCorner,
        )

        self.statusBar().showMessage("Local desktop GUI ready")
        self._first_show_done = False
        self.setStyleSheet(main_window_stylesheet(self.palette()))

    def enable_tray_integration(self, tray_icon: QSystemTrayIcon) -> None:
        """Enable minimize-to-tray behavior for the main window."""
        self._tray_icon = tray_icon

    def show_from_tray(self) -> None:
        """Restore and focus the window from the tray icon."""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def minimize_to_tray_enabled(self) -> bool:
        """Return whether title-bar minimize should hide the window to the tray."""
        return get_minimize_to_tray()

    def request_exit(self) -> None:
        """Allow the window to close and terminate the application."""
        self._allow_close = True
        self.close()

    def showEvent(self, event) -> None:  # noqa: N802
        """Refresh pages once when the window is first shown."""
        super().showEvent(event)
        if self._first_show_done:
            return

        self._first_show_done = True
        for page in (self.dashboard_page, self.curves_page, self.service_page):
            refresh = getattr(page, "refresh_data", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    continue

    def changeEvent(self, event) -> None:  # noqa: N802
        """Optionally minimize to the tray instead of the taskbar."""
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        if not self.isMinimized() or not self.minimize_to_tray_enabled():
            return

        QTimer.singleShot(0, self._hide_to_tray_on_minimize)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Hide to the tray when available unless the user explicitly quits."""
        if self._tray_available() and not self._allow_close:
            event.ignore()
            self._hide_to_tray(
                status_message="PySysFan is still running in the notification area.",
                tray_message="PySysFan is still running in the Windows notification area.",
            )
            return

        super().closeEvent(event)

    def _hide_to_tray_on_minimize(self) -> None:
        """Hide the window to the tray after a minimize action."""
        if not self.isMinimized() or not self._tray_available():
            return

        self._hide_to_tray(
            status_message="PySysFan was minimized to the notification area.",
            tray_message="PySysFan was minimized to the Windows notification area.",
        )

    def _hide_to_tray(self, *, status_message: str, tray_message: str) -> None:
        """Hide the window and optionally show a one-time tray notification."""
        self.hide()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.statusBar().showMessage(status_message, 5000)
        if self._tray_icon is None or self._tray_notice_shown:
            return

        self._tray_notice_shown = True
        self._tray_icon.showMessage(
            "PySysFan",
            tray_message,
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _tray_available(self) -> bool:
        """Return whether tray integration is active and visible."""
        return self._tray_icon is not None and self._tray_icon.isVisible()
