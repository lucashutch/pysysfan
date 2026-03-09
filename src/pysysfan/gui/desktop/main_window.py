"""Main window for the PySide6 desktop GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget

from pysysfan.gui.desktop.curves_page import CurvesPage
from pysysfan.gui.desktop.dashboard_page import DashboardPage
from pysysfan.gui.desktop.service_page import ServicePage


class MainWindow(QMainWindow):
    """Native desktop shell for local PySysFan management."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("mainWindow")
        self.setWindowTitle("PySysFan")
        self.resize(1520, 980)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("mainTabs")
        self.setCentralWidget(self.tab_widget)

        self.dashboard_page = DashboardPage(parent=self)
        self.curves_page = CurvesPage(parent=self)
        self.service_page = ServicePage(parent=self)

        self.tab_widget.addTab(self.dashboard_page, "Dashboard")
        self.tab_widget.addTab(self.curves_page, "Curves")
        self.tab_widget.addTab(self.service_page, "Service")

        self.statusBar().showMessage("Local desktop GUI ready")
        self._first_show_done = False

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
