"""Main window for the PySide6 desktop GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QSystemTrayIcon, QTabWidget, QWidget

from pysysfan.gui.desktop.curves_page import CurvesPage
from pysysfan.gui.desktop.dashboard_page import DashboardPage
from pysysfan.gui.desktop.icons import app_icon
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

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Hide to the tray when available unless the user explicitly quits."""
        if (
            self._tray_icon is not None
            and self._tray_icon.isVisible()
            and not self._allow_close
        ):
            event.ignore()
            self.hide()
            self.statusBar().showMessage(
                "PySysFan is still running in the notification area.",
                5000,
            )
            if not self._tray_notice_shown:
                self._tray_notice_shown = True
                self._tray_icon.showMessage(
                    "PySysFan",
                    "PySysFan is still running in the Windows notification area.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
            return

        super().closeEvent(event)
