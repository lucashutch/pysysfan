"""Curve and config management page for the PySide6 desktop GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pysysfan.config import Config, CurveConfig, FanConfig
from pysysfan.gui.desktop.local_backend import (
    build_curve_preview_series,
    get_profile_names,
    load_profile_config,
    read_daemon_state,
    validate_config_model,
)
from pysysfan.profiles import ProfileManager
from pysysfan.state_file import DEFAULT_STATE_PATH
from pysysfan.temperature import get_valid_aggregation_methods

try:  # pragma: no cover - exercised indirectly when installed
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - fallback path when optional dep missing
    pg = None


class CurvesPage(QWidget):
    """Desktop curve editor backed by direct YAML config access."""

    PRESET_CURVES = {"silent", "balanced", "performance"}

    def __init__(
        self,
        profile_manager: ProfileManager | None = None,
        state_path: Path = DEFAULT_STATE_PATH,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._profile_manager = profile_manager or ProfileManager()
        self._state_path = Path(state_path)
        self._active_profile = ""
        self._config_path: Path | None = None
        self._config: Config | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Curves", self)
        heading.setObjectName("curvesTitle")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(heading)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(12)
        profile_row.addWidget(QLabel("Profile", self))

        self.profile_selector = QComboBox(self)
        self.profile_selector.setObjectName("profileSelector")
        profile_row.addWidget(self.profile_selector)

        self.switch_profile_button = QPushButton("Switch Profile", self)
        self.switch_profile_button.clicked.connect(self.switch_profile)
        profile_row.addWidget(self.switch_profile_button)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh_data)
        profile_row.addWidget(self.refresh_button)

        profile_row.addStretch(1)
        layout.addLayout(profile_row)

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("curvesMessageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)

        self.config_path_label = QLabel("Config path: N/A", self)
        self.config_path_label.setWordWrap(True)
        layout.addWidget(self.config_path_label)

        options_group = QGroupBox("General Settings", self)
        options_layout = QHBoxLayout(options_group)
        options_layout.addWidget(QLabel("Poll interval (s)", self))
        self.poll_interval_spin = QDoubleSpinBox(self)
        self.poll_interval_spin.setRange(0.1, 60.0)
        self.poll_interval_spin.setSingleStep(0.1)
        options_layout.addWidget(self.poll_interval_spin)
        options_layout.addStretch(1)
        layout.addWidget(options_group)

        editor_layout = QGridLayout()
        editor_layout.setHorizontalSpacing(24)
        editor_layout.setVerticalSpacing(16)

        curve_group = QGroupBox("Curve Editor", self)
        curve_layout = QVBoxLayout(curve_group)

        curve_toolbar = QHBoxLayout()
        curve_toolbar.addWidget(QLabel("Curve", self))
        self.curve_selector = QComboBox(self)
        self.curve_selector.currentTextChanged.connect(self._load_selected_curve)
        curve_toolbar.addWidget(self.curve_selector)
        self.new_curve_button = QPushButton("New Curve", self)
        self.new_curve_button.clicked.connect(self.create_curve)
        curve_toolbar.addWidget(self.new_curve_button)
        self.save_curve_button = QPushButton("Save Curve", self)
        self.save_curve_button.clicked.connect(self.save_curve)
        curve_toolbar.addWidget(self.save_curve_button)
        self.delete_curve_button = QPushButton("Delete Curve", self)
        self.delete_curve_button.clicked.connect(self.delete_curve)
        curve_toolbar.addWidget(self.delete_curve_button)
        curve_toolbar.addStretch(1)
        curve_layout.addLayout(curve_toolbar)

        self.points_table = QTableWidget(0, 2, self)
        self.points_table.setObjectName("pointsTable")
        self.points_table.setHorizontalHeaderLabels(
            ["Temperature (°C)", "Fan Speed (%)"]
        )
        self.points_table.horizontalHeader().setStretchLastSection(True)
        curve_layout.addWidget(self.points_table)

        point_actions = QHBoxLayout()
        self.add_point_button = QPushButton("Add Point", self)
        self.add_point_button.clicked.connect(self.add_point)
        point_actions.addWidget(self.add_point_button)
        self.remove_point_button = QPushButton("Remove Point", self)
        self.remove_point_button.clicked.connect(self.remove_selected_point)
        point_actions.addWidget(self.remove_point_button)
        point_actions.addWidget(QLabel("Hysteresis (°C)", self))
        self.hysteresis_spin = QDoubleSpinBox(self)
        self.hysteresis_spin.setRange(0.0, 20.0)
        self.hysteresis_spin.setSingleStep(0.5)
        point_actions.addWidget(self.hysteresis_spin)
        point_actions.addStretch(1)
        curve_layout.addLayout(point_actions)

        preview_actions = QHBoxLayout()
        preview_actions.addWidget(QLabel("Preview temperature (°C)", self))
        self.preview_temp_spin = QDoubleSpinBox(self)
        self.preview_temp_spin.setRange(20.0, 100.0)
        self.preview_temp_spin.setSingleStep(1.0)
        self.preview_temp_spin.setValue(60.0)
        preview_actions.addWidget(self.preview_temp_spin)
        self.preview_button = QPushButton("Preview", self)
        self.preview_button.clicked.connect(self.preview_curve)
        preview_actions.addWidget(self.preview_button)
        self.preview_result_label = QLabel("Preview speed: N/A", self)
        preview_actions.addWidget(self.preview_result_label)
        preview_actions.addStretch(1)
        curve_layout.addLayout(preview_actions)

        self.preview_plot = self._create_plot_widget()
        curve_layout.addWidget(self.preview_plot)
        editor_layout.addWidget(curve_group, 0, 0)

        fan_group = QGroupBox("Fan Configuration", self)
        fan_layout = QGridLayout(fan_group)
        fan_layout.setHorizontalSpacing(12)
        fan_layout.setVerticalSpacing(12)

        fan_layout.addWidget(QLabel("Fan", self), 0, 0)
        self.fan_selector = QComboBox(self)
        self.fan_selector.currentTextChanged.connect(self._load_selected_fan)
        fan_layout.addWidget(self.fan_selector, 0, 1)

        fan_layout.addWidget(QLabel("Assigned curve", self), 1, 0)
        self.fan_curve_selector = QComboBox(self)
        fan_layout.addWidget(self.fan_curve_selector, 1, 1)

        fan_layout.addWidget(QLabel("Temp sensor IDs", self), 2, 0)
        self.temp_ids_edit = QLineEdit(self)
        self.temp_ids_edit.setPlaceholderText("Comma-separated sensor identifiers")
        fan_layout.addWidget(self.temp_ids_edit, 2, 1)

        fan_layout.addWidget(QLabel("Aggregation", self), 3, 0)
        self.aggregation_selector = QComboBox(self)
        self.aggregation_selector.addItems(get_valid_aggregation_methods())
        fan_layout.addWidget(self.aggregation_selector, 3, 1)

        self.allow_fan_off_checkbox = QCheckBox("Allow fan off", self)
        fan_layout.addWidget(self.allow_fan_off_checkbox, 4, 0, 1, 2)

        self.save_fan_button = QPushButton("Save Fan Settings", self)
        self.save_fan_button.clicked.connect(self.save_fan_settings)
        fan_layout.addWidget(self.save_fan_button, 5, 0, 1, 2)
        editor_layout.addWidget(fan_group, 0, 1)

        layout.addLayout(editor_layout)
        layout.addStretch(1)

    def refresh_data(self) -> None:
        """Load the active profile config from disk."""
        try:
            self._active_profile, self._config_path, self._config = load_profile_config(
                self._profile_manager
            )
        except Exception as exc:
            self._show_message(str(exc), is_error=True)
            return

        self._show_message("", is_error=False)
        self.config_path_label.setText(f"Config path: {self._config_path}")
        self.poll_interval_spin.setValue(self._config.poll_interval)
        self._populate_profile_selector()
        self._populate_curve_selector()
        self._populate_fan_selector()
        self.preview_curve()

    def switch_profile(self) -> None:
        """Switch the active profile and reload the editor."""
        profile_name = self.profile_selector.currentText().strip()
        if not profile_name:
            self._show_message("Select a profile first", is_error=True)
            return

        try:
            self._profile_manager.set_active_profile(profile_name)
        except Exception as exc:
            self._show_message(str(exc), is_error=True)
            return

        self.refresh_data()
        daemon_state = read_daemon_state(self._state_path)
        if daemon_state and daemon_state.config_path != str(self._config_path):
            self._show_message(
                "Profile switched. Restart the daemon/service to pick up the new profile file.",
                is_error=False,
            )
        else:
            self._show_message(f"Switched to profile: {profile_name}", is_error=False)

    def create_curve(self) -> None:
        """Create a new curve in memory and select it."""
        if self._config is None:
            return

        name, accepted = QInputDialog.getText(self, "Create Curve", "Curve name:")
        if not accepted or not name.strip():
            return

        curve_name = name.strip()
        if curve_name in self._config.curves:
            self._show_message(f"Curve '{curve_name}' already exists", is_error=True)
            return

        self._config.curves[curve_name] = CurveConfig(
            points=[(30.0, 30.0), (60.0, 60.0), (85.0, 100.0)],
            hysteresis=3.0,
        )
        self._populate_curve_selector(selected=curve_name)
        self._show_message(
            f"Curve '{curve_name}' created locally. Save to persist.",
            is_error=False,
        )

    def save_curve(self) -> None:
        """Save the current curve and general settings to the YAML config."""
        if self._config is None or self._config_path is None:
            return

        curve_name = self.curve_selector.currentText().strip()
        if not curve_name:
            self._show_message("Select a curve before saving", is_error=True)
            return

        points = self._collect_points()
        if len(points) < 2:
            self._show_message("A curve needs at least two points", is_error=True)
            return

        self._config.curves[curve_name] = CurveConfig(
            points=[(float(temp), float(speed)) for temp, speed in points],
            hysteresis=self.hysteresis_spin.value(),
        )
        self._config.poll_interval = self.poll_interval_spin.value()

        if not self._save_config():
            return

        self._populate_curve_selector(selected=curve_name)
        self.preview_curve()
        self._show_message(
            f"Curve '{curve_name}' saved. The daemon will reload the YAML automatically.",
            is_error=False,
        )

    def delete_curve(self) -> None:
        """Delete the selected curve after checking fan references."""
        if self._config is None:
            return

        curve_name = self.curve_selector.currentText().strip()
        if not curve_name:
            return

        if curve_name in self.PRESET_CURVES:
            self._show_message(
                f"'{curve_name}' is a built-in preset and cannot be deleted.",
                is_error=True,
            )
            return

        used_by = [
            name for name, fan in self._config.fans.items() if fan.curve == curve_name
        ]
        if used_by:
            joined = ", ".join(used_by)
            self._show_message(
                f"Cannot delete '{curve_name}' because it is used by: {joined}",
                is_error=True,
            )
            return

        if not self._confirm(f"Delete curve '{curve_name}'?"):
            return

        del self._config.curves[curve_name]
        if not self._save_config():
            return

        self._populate_curve_selector()
        self._show_message(f"Curve '{curve_name}' deleted", is_error=False)

    def preview_curve(self) -> None:
        """Preview the current curve in the result label and plot."""
        points = self._collect_points()
        if len(points) < 2:
            self.preview_result_label.setText("Preview speed: N/A")
            self._plot_preview([])
            return

        try:
            preview_series = build_curve_preview_series(
                points,
                self.hysteresis_spin.value(),
            )
        except Exception as exc:
            self._show_message(str(exc), is_error=True)
            return

        preview_temp = self.preview_temp_spin.value()
        matching = next(
            (speed for temp, speed in preview_series if temp == preview_temp),
            preview_series[-1][1],
        )
        self.preview_result_label.setText(f"Preview speed: {matching:.1f}%")
        self._plot_preview(preview_series)

    def save_fan_settings(self) -> None:
        """Save the selected fan's config block directly to YAML."""
        if self._config is None or self._config_path is None:
            return

        fan_name = self.fan_selector.currentText().strip()
        if not fan_name or fan_name not in self._config.fans:
            self._show_message("Select a configured fan first", is_error=True)
            return

        temp_ids = [
            item.strip()
            for item in self.temp_ids_edit.text().split(",")
            if item.strip()
        ]
        fan_config = self._config.fans[fan_name]
        self._config.fans[fan_name] = FanConfig(
            fan_id=fan_config.fan_id,
            curve=self.fan_curve_selector.currentText().strip(),
            temp_ids=temp_ids,
            aggregation=self.aggregation_selector.currentText(),
            header_name=fan_config.header_name,
            allow_fan_off=self.allow_fan_off_checkbox.isChecked(),
        )
        self._config.poll_interval = self.poll_interval_spin.value()

        if not self._save_config():
            return

        self._show_message(
            f"Saved fan settings for '{fan_name}'. The daemon will reload the YAML automatically.",
            is_error=False,
        )
        self.refresh_data()
        self.fan_selector.setCurrentText(fan_name)

    def add_point(self) -> None:
        """Append a new point row to the table."""
        row_count = self.points_table.rowCount()
        last_temp = 30.0
        if row_count > 0:
            temp_item = self.points_table.item(row_count - 1, 0)
            if temp_item is not None:
                last_temp = float(temp_item.text())

        self._append_point_row(min(last_temp + 10.0, 100.0), 50.0)

    def remove_selected_point(self) -> None:
        """Remove the selected point if enough remain."""
        if self.points_table.rowCount() <= 2:
            self._show_message("A curve needs at least two points", is_error=True)
            return

        row = self.points_table.currentRow()
        if row < 0:
            self._show_message("Select a point to remove", is_error=True)
            return
        self.points_table.removeRow(row)
        self.preview_curve()

    def _populate_profile_selector(self) -> None:
        current = self._active_profile
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        self.profile_selector.addItems(get_profile_names(self._profile_manager))
        self.profile_selector.blockSignals(False)
        self.profile_selector.setCurrentText(current)

    def _populate_curve_selector(self, selected: str | None = None) -> None:
        if self._config is None:
            self.curve_selector.clear()
            return

        current = selected or self.curve_selector.currentText()
        self.curve_selector.blockSignals(True)
        self.curve_selector.clear()
        # Populate selectors from the config's curve names (already
        # normalized by the loader to string keys).
        curve_keys = list(self._config.curves.keys())
        self.curve_selector.addItems(sorted(curve_keys))
        self.fan_curve_selector.clear()
        self.fan_curve_selector.addItems(sorted(curve_keys))
        self.curve_selector.blockSignals(False)

        target = (
            current
            if current in self._config.curves
            else self.curve_selector.itemText(0)
        )
        if target:
            self.curve_selector.setCurrentText(target)
            self._load_selected_curve(target)

    def _populate_fan_selector(self) -> None:
        if self._config is None:
            self.fan_selector.clear()
            return

        current = self.fan_selector.currentText()
        self.fan_selector.blockSignals(True)
        self.fan_selector.clear()
        self.fan_selector.addItems(sorted(self._config.fans))
        self.fan_selector.blockSignals(False)

        target = (
            current if current in self._config.fans else self.fan_selector.itemText(0)
        )
        if target:
            self.fan_selector.setCurrentText(target)
            self._load_selected_fan(target)

    def _load_selected_curve(self, curve_name: str) -> None:
        if self._config is None or curve_name not in self._config.curves:
            self._load_curve_points([])
            return

        curve = self._config.curves[curve_name]
        self._load_curve_points(curve.points)
        self.hysteresis_spin.setValue(curve.hysteresis)
        self.preview_curve()

    def _load_selected_fan(self, fan_name: str) -> None:
        if self._config is None or fan_name not in self._config.fans:
            self.temp_ids_edit.clear()
            return

        fan = self._config.fans[fan_name]
        self.fan_curve_selector.setCurrentText(fan.curve)
        self.curve_selector.setCurrentText(fan.curve)
        self.temp_ids_edit.setText(", ".join(fan.temp_ids))
        self.aggregation_selector.setCurrentText(fan.aggregation)
        self.allow_fan_off_checkbox.setChecked(fan.allow_fan_off)

    def _load_curve_points(self, points) -> None:
        self.points_table.setRowCount(0)
        for temp, speed in points:
            self._append_point_row(float(temp), float(speed))

    def _append_point_row(self, temperature: float, speed: float) -> None:
        row = self.points_table.rowCount()
        self.points_table.insertRow(row)
        self.points_table.setItem(row, 0, QTableWidgetItem(f"{temperature:.1f}"))
        self.points_table.setItem(row, 1, QTableWidgetItem(f"{speed:.1f}"))

    def _collect_points(self) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for row in range(self.points_table.rowCount()):
            temp_item = self.points_table.item(row, 0)
            speed_item = self.points_table.item(row, 1)
            if temp_item is None or speed_item is None:
                continue
            points.append((float(temp_item.text()), float(speed_item.text())))
        return sorted(points, key=lambda point: point[0])

    def _save_config(self) -> bool:
        if self._config is None or self._config_path is None:
            return False

        errors = validate_config_model(self._config)
        if errors:
            self._show_message("; ".join(errors), is_error=True)
            return False

        self._config.save(self._config_path)
        return True

    def _plot_preview(self, preview_series: list[tuple[float, float]]) -> None:
        widget = self.preview_plot.layout().itemAt(0).widget()
        if pg is None or not isinstance(widget, pg.PlotWidget):
            return

        widget.clear()
        if not preview_series:
            return

        xs = [point[0] for point in preview_series]
        ys = [point[1] for point in preview_series]
        widget.plot(xs, ys, pen=pg.mkPen(color="#4E79A7", width=2))
        widget.plot(
            [self.preview_temp_spin.value()],
            [ys[min(max(int(self.preview_temp_spin.value()) - 20, 0), len(ys) - 1)]],
            pen=None,
            symbol="o",
            symbolBrush="#E15759",
            symbolSize=8,
        )

    def _create_plot_widget(self) -> QGroupBox:
        if pg is None:
            fallback = QLabel("Install pyqtgraph to enable curve preview charts.", self)
            fallback.setWordWrap(True)
            return self._wrap_widget("Preview", fallback)

        plot_widget = pg.PlotWidget(self)
        plot_widget.setBackground("w")
        plot_widget.showGrid(x=True, y=True, alpha=0.2)
        plot_widget.setLabel("bottom", "Temperature", units="°C")
        plot_widget.setLabel("left", "Fan speed", units="%")
        return self._wrap_widget("Preview", plot_widget)

    @staticmethod
    def _wrap_widget(title: str, widget: QWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(widget)
        return group

    def _confirm(self, message: str) -> bool:
        return (
            QMessageBox.question(
                self,
                "Confirm Action",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _show_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.message_label.clear()
            self.message_label.hide()
            return

        color = "#b00020" if is_error else "#1d6f42"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(message)
        self.message_label.show()
