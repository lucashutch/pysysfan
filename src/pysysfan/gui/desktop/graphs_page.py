"""Graphs page for the PySide6 desktop GUI (placeholder)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GraphsPage(QWidget):
    """Placeholder for the full graphs page (Phase 3)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("graphsRoot")
        layout = QVBoxLayout(self)
        label = QLabel("Graphs page — coming in Phase 3")
        label.setStyleSheet("font-size: 16px; color: grey;")
        layout.addWidget(label)
