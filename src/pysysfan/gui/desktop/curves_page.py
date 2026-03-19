"""Curve and config management page for the PySide6 desktop GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pysysfan.config import Config, CurveConfig, FanConfig
from pysysfan.gui.desktop.local_backend import (
    build_curve_preview_series,
    load_profile_config,
    read_daemon_state,
    validate_config_model,
)
from pysysfan.gui.desktop.plotting import CurveEditorPlotWidget, pg
from pysysfan.gui.desktop.theme import (
    PAGE_HEADING_STYLE,
    management_page_stylesheet,
    plot_theme,
)
from pysysfan.profiles import DEFAULT_PROFILE_NAME, ProfileManager
from pysysfan.state_file import DEFAULT_STATE_PATH
from pysysfan.temperature import get_valid_aggregation_methods


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
        self.setObjectName("managementPageRoot")
        self._profile_manager = profile_manager or ProfileManager()
        self._state_path = Path(state_path)
        self._active_profile = ""
        self._config_path: Path | None = None
        self._config: Config | None = None
        self._syncing_points = False
        self._profile_display_names: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Config", self)
        heading.setObjectName("curvesTitle")
        heading.setStyleSheet(PAGE_HEADING_STYLE)
        layout.addWidget(heading)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)
        profile_row.addWidget(QLabel("Profile", self))

        self.profile_selector = QComboBox(self)
        self.profile_selector.setObjectName("profileSelector")
        profile_row.addWidget(self.profile_selector)

        self.switch_profile_button = QPushButton("Switch Profile", self)
        self.switch_profile_button.clicked.connect(self.switch_profile)
        profile_row.addWidget(self.switch_profile_button)

        self.new_profile_button = QPushButton("New Profile", self)
        self.new_profile_button.clicked.connect(self.create_profile)
        profile_row.addWidget(self.new_profile_button)

        self.rename_profile_button = QPushButton("Rename Profile", self)
        self.rename_profile_button.clicked.connect(self.rename_profile)
        profile_row.addWidget(self.rename_profile_button)

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

        content_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setHandleWidth(8)
        layout.addWidget(content_splitter, 1)

        self.left_column = QWidget(content_splitter)
        left_layout = QVBoxLayout(self.left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)

        self.right_column = QWidget(content_splitter)
        right_layout = QVBoxLayout(self.right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)

        self.config_path_label = QLabel("Config path: N/A", self.left_column)
        self.config_path_label.setWordWrap(True)
        left_layout.addWidget(self.config_path_label)

        options_group = QGroupBox("General Settings", self.left_column)
        options_layout = QHBoxLayout(options_group)
        options_layout.addWidget(QLabel("Poll interval (s)", self))
        self.poll_interval_spin = QDoubleSpinBox(self)
        self.poll_interval_spin.setRange(0.1, 60.0)
        self.poll_interval_spin.setSingleStep(0.1)
        self.poll_interval_spin.setDecimals(1)
        self.poll_interval_spin.setKeyboardTracking(False)
        options_layout.addWidget(self.poll_interval_spin)
        self.save_settings_button = QPushButton("Save Settings", self)
        self.save_settings_button.clicked.connect(self.save_general_settings)
        options_layout.addWidget(self.save_settings_button)
        options_layout.addStretch(1)
        left_layout.addWidget(options_group)

        curve_group = QGroupBox("Curve Editor", self.left_column)
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
        header = self.points_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.points_table.setColumnWidth(0, 190)
        self.points_table.setMinimumHeight(260)
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
        left_layout.addWidget(curve_group)

        fan_group = QGroupBox("Fan Configuration", self.left_column)
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

        self.save_fan_button = QPushButton("Save Fan Settings", self)
        self.save_fan_button.clicked.connect(self.save_fan_settings)
        fan_layout.addWidget(self.save_fan_button, 4, 0, 1, 2)
        left_layout.addWidget(fan_group)
        left_layout.addStretch(1)

        self.preview_group = QGroupBox("Curve Preview", self.right_column)
        self.preview_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        preview_layout = QVBoxLayout(self.preview_group)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)

        self.preview_result_label = QLabel(
            "Hover over the graph to inspect values. Drag control points to edit the curve.",
            self.preview_group,
        )
        self.preview_result_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_result_label)

        self.preview_plot = self._create_plot_widget()
        self.preview_plot.setMinimumWidth(300)
        self.preview_plot.setMinimumHeight(400)
        self.preview_plot.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        preview_layout.addWidget(self.preview_plot, 1)
        right_layout.addWidget(self.preview_group, 1)

        content_splitter.addWidget(self.left_column)
        content_splitter.addWidget(self.right_column)
        self.left_column.setMinimumWidth(0)
        self.right_column.setMinimumWidth(0)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setSizes([1, 1])

        self.points_table.itemChanged.connect(self._handle_curve_inputs_changed)
        self.hysteresis_spin.valueChanged.connect(self._handle_curve_inputs_changed)
        self.setStyleSheet(management_page_stylesheet(self.palette()))

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
        self.poll_interval_spin.setValue(
            self._normalized_poll_interval(self._config.poll_interval)
        )
        self._populate_profile_selector()
        self._populate_curve_selector()
        self._populate_fan_selector()
        self.preview_curve()

    def switch_profile(self) -> None:
        """Switch the active profile and reload the editor."""
        profile_name = self._selected_profile_name()
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

    def create_profile(self) -> None:
        """Create a new profile by copying the current profile configuration."""
        seed_name = self._display_name_for_profile(self._active_profile) or ""
        name, accepted = QInputDialog.getText(
            self,
            "Create Profile",
            "Profile name:",
            text=seed_name,
        )
        if not accepted or not name.strip():
            return

        try:
            profile = self._profile_manager.create_profile(
                name=name.strip(),
                display_name=name.strip(),
                copy_from=self._active_profile or DEFAULT_PROFILE_NAME,
            )
            self._profile_manager.set_active_profile(profile.name)
        except Exception as exc:
            self._show_message(str(exc), is_error=True)
            return

        self.refresh_data()
        self._show_message(
            f"Created and switched to profile: {profile.metadata.display_name}",
            is_error=False,
        )

    def rename_profile(self) -> None:
        """Rename the visible display name for the selected profile."""
        profile_name = self._selected_profile_name()
        if not profile_name:
            self._show_message("Select a profile first", is_error=True)
            return

        current_display = self._display_name_for_profile(profile_name) or profile_name
        display_name, accepted = QInputDialog.getText(
            self,
            "Rename Profile",
            "Display name:",
            text=current_display,
        )
        if not accepted or not display_name.strip():
            return

        try:
            self._profile_manager.update_profile(
                profile_name,
                display_name=display_name.strip(),
            )
        except Exception as exc:
            self._show_message(str(exc), is_error=True)
            return

        self.refresh_data()
        self._show_message(
            f"Renamed profile '{profile_name}' to '{display_name.strip()}'",
            is_error=False,
        )

    def save_general_settings(self) -> None:
        """Persist general config settings such as the poll interval."""
        if self._config is None or self._config_path is None:
            return

        self._config.poll_interval = self._normalized_poll_interval(
            self.poll_interval_spin.value()
        )
        if not self._save_config():
            return

        self.poll_interval_spin.setValue(self._config.poll_interval)
        self._show_message(
            "Saved general settings. The daemon will reload the YAML automatically.",
            is_error=False,
        )

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
        self._config.poll_interval = self._normalized_poll_interval(
            self.poll_interval_spin.value()
        )

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
        """Preview the current curve in the interactive plot."""
        points = self._collect_points()
        if len(points) < 2:
            self.preview_result_label.setText(
                "Hover over the graph to inspect values. Drag control points to edit the curve."
            )
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

        self.preview_result_label.setText(
            "Hover over the graph to inspect values. Drag control points to edit the curve."
        )
        self._plot_preview(preview_series, points)

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
            allow_fan_off=True,
        )
        self._config.poll_interval = self._normalized_poll_interval(
            self.poll_interval_spin.value()
        )

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
        current = self._active_profile or self._selected_profile_name()
        profiles = sorted(
            self._profile_manager.list_profiles(),
            key=lambda profile: (
                profile.name != self._active_profile,
                (profile.metadata.display_name or profile.name).lower(),
            ),
        )
        self._profile_display_names = {
            profile.name: profile.metadata.display_name or profile.name
            for profile in profiles
        }
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        for profile in profiles:
            self.profile_selector.addItem(
                self._profile_label(profile.name),
                profile.name,
            )
        self.profile_selector.blockSignals(False)
        if current:
            index = self.profile_selector.findData(current)
            if index >= 0:
                self.profile_selector.setCurrentIndex(index)

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

    def _load_curve_points(self, points) -> None:
        self._syncing_points = True
        self.points_table.setRowCount(0)
        for temp, speed in points:
            self._append_point_row(float(temp), float(speed))
        self._syncing_points = False
        self.preview_curve()

    def _append_point_row(self, temperature: float, speed: float) -> None:
        row = self.points_table.rowCount()
        self.points_table.insertRow(row)
        self.points_table.setItem(row, 0, QTableWidgetItem(f"{temperature:.1f}"))
        self.points_table.setItem(row, 1, QTableWidgetItem(f"{speed:.1f}"))

    def _handle_curve_inputs_changed(self, *_args) -> None:
        if self._syncing_points:
            return
        self.preview_curve()

    def _handle_plot_hover_changed(self, hover_point: tuple[int, int] | None) -> None:
        if hover_point is None:
            self.preview_result_label.setText(
                "Hover over the graph to inspect values. Drag control points to edit the curve."
            )
            return

        temperature, speed = hover_point
        self.preview_result_label.setText(f"Hover: {temperature}°C → {speed}%")

    def _handle_plot_points_changed(
        self,
        points: list[tuple[float, float]],
    ) -> None:
        self._syncing_points = True
        self.points_table.setRowCount(0)
        for temperature, speed in points:
            self._append_point_row(temperature, speed)
        self._syncing_points = False
        self.preview_curve()

    def _selected_profile_name(self) -> str:
        value = self.profile_selector.currentData()
        if isinstance(value, str) and value.strip():
            return value.strip()
        return self.profile_selector.currentText().strip()

    def _display_name_for_profile(self, profile_name: str) -> str:
        return self._profile_display_names.get(profile_name, profile_name)

    def _profile_label(self, profile_name: str) -> str:
        display_name = self._display_name_for_profile(profile_name)
        if display_name.lower() == profile_name.lower():
            return display_name
        return f"{display_name} ({profile_name})"

    @staticmethod
    def _normalized_poll_interval(value: float) -> float:
        return round(float(value), 1)

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

    def _plot_preview(
        self,
        preview_series: list[tuple[float, float]],
        control_points: list[tuple[float, float]] | None = None,
    ) -> None:
        widget = self.preview_plot
        if pg is None or not isinstance(widget, CurveEditorPlotWidget):
            return

        widget.set_theme(plot_theme(self.palette()))
        widget.showGrid(x=True, y=True, alpha=0.2)
        widget.setLabel("bottom", "Temperature", units="°C")
        widget.setLabel("left", "Fan speed", units="%")
        plot_item = widget.getPlotItem()
        plot_item.getAxis("bottom").setHeight(30)
        left_axis = plot_item.getAxis("left")
        left_axis.setWidth(40)
        left_axis.setStyle(
            autoExpandTextSpace=False,
            autoReduceTextSpace=False,
            tickTextWidth=24,
            tickTextOffset=4,
        )
        if not preview_series:
            widget.set_preview_series([])
            widget.set_points([])
            return

        widget.set_preview_series(preview_series)
        widget.set_points(control_points or [])

    def _create_plot_widget(self) -> QWidget:
        if pg is None:
            fallback = QLabel("Install pyqtgraph to enable curve preview charts.", self)
            fallback.setWordWrap(True)
            return fallback

        plot_widget = CurveEditorPlotWidget(self)
        plot_widget.showGrid(x=True, y=True, alpha=0.2)
        plot_widget.setLabel("bottom", "Temperature", units="°C")
        plot_widget.setLabel("left", "Fan speed", units="%")
        plot_widget.set_theme(plot_theme(self.palette()))
        left_axis = plot_widget.getPlotItem().getAxis("left")
        left_axis.setWidth(40)
        left_axis.setStyle(
            autoExpandTextSpace=False,
            autoReduceTextSpace=False,
            tickTextWidth=24,
            tickTextOffset=4,
        )
        plot_widget.hoverChanged.connect(self._handle_plot_hover_changed)
        plot_widget.pointsChanged.connect(self._handle_plot_points_changed)
        return plot_widget

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
