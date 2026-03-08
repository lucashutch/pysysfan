"""Application bootstrap for the PySide6 desktop GUI."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from pysysfan.gui.desktop.main_window import MainWindow


def get_or_create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Return the active QApplication, creating one if needed."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv is not None else sys.argv)
        app.setApplicationName("PySysFan")
        app.setOrganizationName("pysysfan")
    return app


def launch_gui(argv: Sequence[str] | None = None) -> int:
    """Create the application shell and enter the Qt event loop."""
    app = get_or_create_application(argv)
    window = MainWindow()
    window.show()
    return app.exec()
