"""Reusable plot helpers for the PySide6 desktop GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent

try:  # pragma: no cover - optional GUI dependency
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional GUI dependency
    pg = None


class DashboardPlotWidget(pg.PlotWidget if pg is not None else object):
    """Plot widget with interaction disabled for dashboard-style charts."""

    def __init__(self, *args, **kwargs) -> None:
        if pg is None:  # pragma: no cover - protected by callers
            raise RuntimeError("pyqtgraph is required for DashboardPlotWidget")
        super().__init__(*args, **kwargs)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.setMouseEnabled(x=False, y=False)
        self.getPlotItem().vb.setMouseEnabled(x=False, y=False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Ignore wheel events so charts do not zoom unexpectedly."""
        event.ignore()
