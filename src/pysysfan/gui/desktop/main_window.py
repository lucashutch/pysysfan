"""Main window for the PySide6 desktop GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from pysysfan.gui.desktop.curves_page import CurvesPage
from pysysfan.gui.desktop.dashboard_page import DashboardPage
from pysysfan.gui.desktop.service_page import ServicePage


class PlaceholderPage(QWidget):
    """Simple placeholder page used while porting UI features to Qt."""

    def __init__(self, title: str, message: str, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        heading = QLabel(title, self)
        heading.setObjectName("pageTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")

        description = QLabel(message, self)
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addStretch(1)


class MainWindow(QMainWindow):
    """Initial PySide6 application shell for the GUI migration."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("mainWindow")
        self.setWindowTitle("PySysFan")
        self.resize(1100, 720)

        # Create shared API client for all pages
        from pysysfan.api.client import PySysFanClient

        self._shared_client = PySysFanClient

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("mainTabs")
        self.setCentralWidget(self.tab_widget)

        self.dashboard_page = DashboardPage(
            client_factory=self._shared_client, parent=self
        )
        self.curves_page = CurvesPage(client_factory=self._shared_client, parent=self)
        self.service_page = ServicePage(client_factory=self._shared_client, parent=self)

        self.tab_widget.addTab(
            self.dashboard_page,
            "Dashboard",
        )
        self.tab_widget.addTab(
            self.curves_page,
            "Curves",
        )
        self.tab_widget.addTab(
            self.service_page,
            "Service",
        )

        self.statusBar().showMessage("PySide6 GUI migration scaffold ready")

    def showEvent(self, event) -> None:  # noqa: N802
        """Auto-connect and refresh dashboard when window is first shown."""
        super().showEvent(event) if event else None
        # Only do this once on first show
        if hasattr(self, "_first_show_done"):
            return
        self._first_show_done = True
        # Auto-connect dashboard on startup
        try:
            self.dashboard_page.refresh_data()
        except Exception:
            pass  # Connection failed, user can try manually
