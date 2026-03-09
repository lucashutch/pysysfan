"""Curve management page for the PySide6 desktop GUI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pysysfan.api.client import PySysFanClient


class CurvesPage(QWidget):
    """Desktop curve editor backed by the Python API client."""

    def __init__(
        self,
        client_factory: Callable[[], PySysFanClient] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._client_factory = client_factory or PySysFanClient
        self._client: PySysFanClient | None = None
        self._curves: dict[str, dict[str, Any]] = {}
        self._fans: dict[str, dict[str, Any]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Curves", self)
        heading.setObjectName("curvesTitle")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(heading)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.connection_label = QLabel("Connection: Disconnected", self)
        self.connection_label.setObjectName("curvesConnectionLabel")
        toolbar.addWidget(self.connection_label)

        toolbar.addWidget(QLabel("Curve", self))
        self.curve_selector = QComboBox(self)
        self.curve_selector.setObjectName("curveSelector")
        self.curve_selector.currentTextChanged.connect(self._load_selected_curve)
        toolbar.addWidget(self.curve_selector)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.refresh_button)

        self.new_curve_button = QPushButton("New Curve", self)
        self.new_curve_button.clicked.connect(self.create_curve)
        toolbar.addWidget(self.new_curve_button)

        self.save_button = QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_curve)
        toolbar.addWidget(self.save_button)

        self.delete_button = QPushButton("Delete", self)
        self.delete_button.clicked.connect(self.delete_curve)
        toolbar.addWidget(self.delete_button)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("curvesMessageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)

        editor_layout = QGridLayout()
        editor_layout.setHorizontalSpacing(24)
        editor_layout.setVerticalSpacing(12)

        editor_layout.addWidget(QLabel("Points", self), 0, 0)
        self.points_table = QTableWidget(0, 2, self)
        self.points_table.setObjectName("pointsTable")
        self.points_table.setHorizontalHeaderLabels(
            ["Temperature (C)", "Fan Speed (%)"]
        )
        self.points_table.horizontalHeader().setStretchLastSection(True)
        editor_layout.addWidget(self.points_table, 1, 0, 4, 1)

        points_buttons = QHBoxLayout()
        self.add_point_button = QPushButton("Add Point", self)
        self.add_point_button.clicked.connect(self.add_point)
        points_buttons.addWidget(self.add_point_button)
        self.remove_point_button = QPushButton("Remove Point", self)
        self.remove_point_button.clicked.connect(self.remove_selected_point)
        points_buttons.addWidget(self.remove_point_button)
        points_buttons.addStretch(1)
        editor_layout.addLayout(points_buttons, 5, 0)

        preview_column = QVBoxLayout()
        preview_column.setSpacing(12)

        hysteresis_row = QHBoxLayout()
        hysteresis_row.addWidget(QLabel("Hysteresis (C)", self))
        self.hysteresis_spin = QDoubleSpinBox(self)
        self.hysteresis_spin.setObjectName("hysteresisSpin")
        self.hysteresis_spin.setRange(0.0, 20.0)
        self.hysteresis_spin.setSingleStep(0.5)
        self.hysteresis_spin.setValue(3.0)
        hysteresis_row.addWidget(self.hysteresis_spin)
        hysteresis_row.addStretch(1)
        preview_column.addLayout(hysteresis_row)

        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("Preview temp (C)", self))
        self.preview_temp_spin = QSpinBox(self)
        self.preview_temp_spin.setObjectName("previewTempSpin")
        self.preview_temp_spin.setRange(20, 100)
        self.preview_temp_spin.setValue(60)
        preview_row.addWidget(self.preview_temp_spin)
        self.preview_button = QPushButton("Preview", self)
        self.preview_button.clicked.connect(self.preview_curve)
        preview_row.addWidget(self.preview_button)
        preview_row.addStretch(1)
        preview_column.addLayout(preview_row)

        self.preview_result_label = QLabel("Preview speed: N/A", self)
        self.preview_result_label.setObjectName("previewResultLabel")
        preview_column.addWidget(self.preview_result_label)

        fan_row = QHBoxLayout()
        fan_row.addWidget(QLabel("Assign selected curve to fan", self))
        self.fan_selector = QComboBox(self)
        self.fan_selector.setObjectName("fanSelector")
        fan_row.addWidget(self.fan_selector)
        self.assign_button = QPushButton("Assign", self)
        self.assign_button.clicked.connect(self.assign_curve_to_fan)
        fan_row.addWidget(self.assign_button)
        fan_row.addStretch(1)
        preview_column.addLayout(fan_row)

        self.fan_assignment_label = QLabel("Fan assignment: N/A", self)
        self.fan_assignment_label.setObjectName("fanAssignmentLabel")
        self.fan_assignment_label.setWordWrap(True)
        preview_column.addWidget(self.fan_assignment_label)
        preview_column.addStretch(1)

        editor_layout.addLayout(preview_column, 1, 1, 5, 1)
        layout.addLayout(editor_layout)
        layout.addStretch(1)

    def refresh_data(self) -> None:
        """Refresh curves and fan assignments."""
        try:
            client = self._get_client()
            curves = client.list_curves().get("curves", {})
            fans = client.list_fans().get("fans", {})
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_message(str(exc), is_error=True)
            return

        self.connection_label.setText("Connection: Connected")
        self._curves = curves
        self._fans = fans
        self._populate_curve_selector()
        self._populate_fan_selector()
        self._show_message("", is_error=False)

    def create_curve(self) -> None:
        """Create a new curve with a prompted name."""
        name, accepted = QInputDialog.getText(
            self,
            "Create Curve",
            "Curve name:",
        )
        if not accepted or not name.strip():
            return

        curve_name = name.strip()
        if curve_name in self._curves:
            self._show_message(f"Curve '{curve_name}' already exists", is_error=True)
            return

        self._curves[curve_name] = {
            "name": curve_name,
            "points": [[30, 30], [60, 60], [85, 100]],
            "hysteresis": 3.0,
        }
        self._populate_curve_selector(selected=curve_name)
        self._show_message(
            f"Curve '{curve_name}' created locally. Save to persist.",
            is_error=False,
        )

    def save_curve(self) -> None:
        """Validate and save the selected curve."""
        curve_name = self.curve_selector.currentText().strip()
        if not curve_name:
            self._show_message("Select a curve before saving", is_error=True)
            return

        points = self._collect_points()
        hysteresis = self.hysteresis_spin.value()

        try:
            client = self._get_client()
            validation = client.validate_curve(points, hysteresis)
            if not validation.get("valid", False):
                errors = (
                    "; ".join(validation.get("errors", [])) or "Curve validation failed"
                )
                self._show_message(errors, is_error=True)
                return

            client.create_curve(curve_name, points, hysteresis)
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_message(str(exc), is_error=True)
            return

        self.connection_label.setText("Connection: Connected")
        self.refresh_data()
        self.curve_selector.setCurrentText(curve_name)
        self._show_message(f"Curve '{curve_name}' saved", is_error=False)

    def delete_curve(self) -> None:
        """Delete the selected curve after confirmation."""
        curve_name = self.curve_selector.currentText().strip()
        if not curve_name:
            return

        if not self._confirm(f"Delete curve '{curve_name}'?"):
            return

        try:
            self._get_client().delete_curve(curve_name)
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_message(str(exc), is_error=True)
            return

        self.connection_label.setText("Connection: Connected")
        self.refresh_data()
        self._show_message(f"Curve '{curve_name}' deleted", is_error=False)

    def preview_curve(self) -> None:
        """Preview the selected curve at the configured temperature."""
        try:
            result = self._get_client().preview_curve(
                self._collect_points(),
                float(self.preview_temp_spin.value()),
                self.hysteresis_spin.value(),
            )
        except Exception as exc:
            self._show_message(str(exc), is_error=True)
            return

        self.connection_label.setText("Connection: Connected")
        self.preview_result_label.setText(
            f"Preview speed: {result.get('speed_percent', 'N/A')}%"
        )
        self._show_message("", is_error=False)

    def assign_curve_to_fan(self) -> None:
        """Assign the selected curve to the selected fan."""
        fan_name = self.fan_selector.currentText().strip()
        curve_name = self.curve_selector.currentText().strip()
        if not fan_name or not curve_name or fan_name not in self._fans:
            self._show_message("Select both a fan and a curve", is_error=True)
            return

        fan = self._fans[fan_name]

        try:
            self._get_client().update_fan(
                fan_name,
                fan_id=fan.get("fan_id"),
                curve=curve_name,
                temp_ids=fan.get("temp_ids"),
                aggregation=fan.get("aggregation"),
                allow_fan_off=fan.get("allow_fan_off"),
            )
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_message(str(exc), is_error=True)
            return

        self.connection_label.setText("Connection: Connected")
        self.refresh_data()
        self.curve_selector.setCurrentText(curve_name)
        self._show_message(
            f"Assigned curve '{curve_name}' to fan '{fan_name}'",
            is_error=False,
        )

    def add_point(self) -> None:
        """Add a new point to the current table."""
        row_count = self.points_table.rowCount()
        last_temp = 30
        if row_count > 0:
            last_temp_item = self.points_table.item(row_count - 1, 0)
            if last_temp_item is not None:
                last_temp = int(float(last_temp_item.text()))

        new_temp = min(last_temp + 10, 100)
        self._append_point_row(new_temp, 50)

    def remove_selected_point(self) -> None:
        """Remove the selected point if enough points remain."""
        if self.points_table.rowCount() <= 2:
            self._show_message("A curve needs at least two points", is_error=True)
            return

        row = self.points_table.currentRow()
        if row < 0:
            self._show_message("Select a point to remove", is_error=True)
            return
        self.points_table.removeRow(row)

    def _populate_curve_selector(self, selected: str | None = None) -> None:
        current = selected or self.curve_selector.currentText()
        self.curve_selector.blockSignals(True)
        self.curve_selector.clear()
        self.curve_selector.addItems(sorted(self._curves))
        self.curve_selector.blockSignals(False)

        if self.curve_selector.count() == 0:
            self._load_curve_points([])
            self.delete_button.setEnabled(False)
            return

        target = current if current in self._curves else self.curve_selector.itemText(0)
        self.curve_selector.setCurrentText(target)
        self._load_selected_curve(target)

    def _populate_fan_selector(self) -> None:
        current = self.fan_selector.currentText()
        self.fan_selector.clear()
        self.fan_selector.addItems(sorted(self._fans))
        if self.fan_selector.count() > 0:
            target = current if current in self._fans else self.fan_selector.itemText(0)
            self.fan_selector.setCurrentText(target)
            fan = self._fans[target]
            self.fan_assignment_label.setText(
                f"Fan assignment: {target} -> {fan.get('curve', 'N/A')}"
            )
        else:
            self.fan_assignment_label.setText("Fan assignment: No configured fans")

    def _load_selected_curve(self, curve_name: str) -> None:
        if not curve_name or curve_name not in self._curves:
            self._load_curve_points([])
            self.delete_button.setEnabled(False)
            return

        curve = self._curves[curve_name]
        self._load_curve_points(curve.get("points", []))
        self.hysteresis_spin.setValue(float(curve.get("hysteresis", 3.0)))
        self.delete_button.setEnabled(True)
        self.preview_result_label.setText("Preview speed: N/A")

    def _load_curve_points(
        self, points: list[list[float]] | list[tuple[float, float]]
    ) -> None:
        self.points_table.setRowCount(0)
        for temp, speed in points:
            self._append_point_row(int(temp), int(speed))

    def _append_point_row(self, temperature: int, speed: int) -> None:
        row = self.points_table.rowCount()
        self.points_table.insertRow(row)
        self.points_table.setItem(row, 0, QTableWidgetItem(str(temperature)))
        self.points_table.setItem(row, 1, QTableWidgetItem(str(speed)))

    def _collect_points(self) -> list[list[float]]:
        points: list[list[float]] = []
        for row in range(self.points_table.rowCount()):
            temp_item = self.points_table.item(row, 0)
            speed_item = self.points_table.item(row, 1)
            if temp_item is None or speed_item is None:
                continue
            points.append([float(temp_item.text()), float(speed_item.text())])
        return sorted(points, key=lambda point: point[0])

    def _confirm(self, message: str) -> bool:
        return (
            QMessageBox.question(
                self,
                "Confirm Curve Action",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _get_client(self) -> PySysFanClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _show_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.message_label.clear()
            self.message_label.hide()
            return

        color = "#b00020" if is_error else "#1d6f42"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(message)
        self.message_label.show()
