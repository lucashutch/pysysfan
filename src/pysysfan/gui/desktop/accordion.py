"""Reusable accordion widgets for the desktop GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class _AccordionHeader(QWidget):
    """Clickable header container for an accordion section."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class AccordionSection(QFrame):
    """Single collapsible section used by flatter management pages."""

    toggled = Signal(bool)

    def __init__(self, title: str, summary: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("accordionSection")
        self.setProperty("accordionSection", True)
        self._title = title
        self._summary = summary
        self._is_open = False

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        header = _AccordionHeader(self)
        header.setObjectName("accordionHeaderContainer")
        header.setProperty("accordionHeaderContainer", True)
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(0)

        self.indicator_label = QLabel("+", header)
        self.indicator_label.setObjectName("accordionIndicator")
        self.indicator_label.setProperty("accordionIndicator", True)
        self.indicator_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.indicator_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.indicator_label.setFixedWidth(20)
        self.indicator_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        header_layout.addWidget(self.indicator_label)

        self.header_label = QLabel(title, header)
        self.header_label.setObjectName("accordionHeader")
        self.header_label.setProperty("accordionHeader", True)
        self.header_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.header_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        header_layout.addWidget(self.header_label, stretch=1)

        self.summary_label = QLabel(summary, header)
        self.summary_label.setObjectName("accordionSummary")
        self.summary_label.setProperty("accordionSummary", True)
        self.summary_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.summary_label.setWordWrap(False)
        self.summary_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        header_layout.addWidget(self.summary_label)

        header.clicked.connect(self._on_header_clicked)

        self.body_widget = QWidget(self)
        self.body_widget.setObjectName("accordionBody")
        self.body_widget.setProperty("accordionBody", True)
        self.body_layout = QVBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(12, 12, 12, 12)
        self.body_layout.setSpacing(10)

        outer_layout.addWidget(header)
        outer_layout.addWidget(self.body_widget)

        self.set_open(False)

    @property
    def title(self) -> str:
        return self._title

    def set_summary(self, summary: str) -> None:
        self._summary = summary
        self.summary_label.setText(summary)
        self.summary_label.setVisible(not self.is_open())

    def is_open(self) -> bool:
        return self._is_open

    def set_open(self, open_: bool) -> None:
        self._is_open = open_
        self._apply_state(open_)

    def add_widget(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.body_layout.addLayout(layout)

    def add_stretch(self, stretch: int = 1) -> None:
        self.body_layout.addStretch(stretch)

    def _on_header_clicked(self) -> None:
        self._is_open = not self._is_open
        self._apply_state(self._is_open)
        self.toggled.emit(self._is_open)

    def _apply_state(self, open_: bool) -> None:
        self.indicator_label.setText("−" if open_ else "+")
        self.header_label.setText(self._title)
        self.body_widget.setVisible(open_)
        self.summary_label.setVisible(not open_)


class AccordionWidget(QWidget):
    """Accordion container that allows sections to stay open independently."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("accordionWidget")
        self._sections: list[AccordionSection] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

    @property
    def sections(self) -> list[AccordionSection]:
        return self._sections

    def add_section(
        self,
        title: str,
        *,
        summary: str = "",
        open_: bool = False,
    ) -> AccordionSection:
        section = AccordionSection(title, summary=summary, parent=self)
        section.toggled.connect(
            lambda checked, current=section: self._on_toggled(current, checked)
        )
        self.layout().addWidget(section)
        self._sections.append(section)
        if open_:
            section.set_open(True)
        return section

    def set_open_section(self, section: AccordionSection) -> None:
        if section in self._sections:
            section.set_open(True)

    def _on_toggled(self, section: AccordionSection, checked: bool) -> None:
        section.set_open(checked)
