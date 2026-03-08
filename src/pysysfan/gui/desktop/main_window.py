"""Main window for the PySide6 desktop GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

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

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("mainTabs")
        self.setCentralWidget(self.tab_widget)

        self.tab_widget.addTab(
            DashboardPage(parent=self),
            "Dashboard",
        )
        self.tab_widget.addTab(
            PlaceholderPage(
                "Curves",
                "Curve editing will move here using native Qt widgets backed by the "
                "existing daemon API.",
                self,
            ),
            "Curves",
        )
        self.tab_widget.addTab(
            ServicePage(parent=self),
            "Service",
        )

        self.statusBar().showMessage("PySide6 GUI migration scaffold ready")
