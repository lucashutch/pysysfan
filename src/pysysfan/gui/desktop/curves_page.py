"""Curve and config management page for the PySide6 desktop GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pysysfan.config import Config, CurveConfig, FanConfig
from pysysfan.gui.desktop.accordion import AccordionWidget
from pysysfan.gui.desktop.local_backend import (
    build_curve_preview_series,
    load_profile_config,
    read_daemon_state,
    validate_config_model,
)
from pysysfan.gui.desktop.plotting import CurveEditorPlotWidget, pg
from pysysfan.gui.desktop.theme import (
    PAGE_HEADING_STYLE,
    flat_management_page_stylesheet,
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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        heading = QLabel("Configuration", self)
        heading.setObjectName("curvesTitle")
        heading.setStyleSheet(PAGE_HEADING_STYLE)
        layout.addWidget(heading)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.status_label = QLabel("● default · Poll 1.0s · Hysteresis 3.0°C", self)
        self.status_label.setObjectName("serviceConnectionLabel")
        toolbar.addWidget(self.status_label)

        toolbar.addStretch(1)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("serviceRefreshBtn")
        self.refresh_button.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.refresh_button)

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("curvesMessageLabel")
        self.message_label.setWordWrap(False)
        self.message_label.hide()
        toolbar.addWidget(self.message_label)
        layout.addLayout(toolbar)

        content_row = QHBoxLayout()
        content_row.setSpacing(12)
        layout.addLayout(content_row, 1)

        self.left_column = QWidget(self)
        self.left_column.setObjectName("curvesLeftColumn")
        left_layout = QVBoxLayout(self.left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        content_row.addWidget(self.left_column, 1)

        self.left_scroll = QScrollArea(self.left_column)
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.left_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        left_layout.addWidget(self.left_scroll, 1)

        left_scroll_content = QWidget(self.left_scroll)
        self.left_scroll.setWidget(left_scroll_content)
        left_scroll_layout = QVBoxLayout(left_scroll_content)
        left_scroll_layout.setContentsMargins(0, 0, 0, 0)
        left_scroll_layout.setSpacing(10)

        self.accordion = AccordionWidget(left_scroll_content)
        left_scroll_layout.addWidget(self.accordion)
        left_scroll_layout.addStretch(1)

        self.profile_selector = QComboBox(self)
        self.profile_selector.setObjectName("profileSelector")

        self.switch_profile_button = QPushButton("Switch Profile", self)
        self.switch_profile_button.clicked.connect(self.switch_profile)

        self.new_profile_button = QPushButton("New Profile", self)
        self.new_profile_button.clicked.connect(self.create_profile)

        self.rename_profile_button = QPushButton("Rename Profile", self)
        self.rename_profile_button.clicked.connect(self.rename_profile)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh_data)

        self.curve_selector = QComboBox(self)
        self.curve_selector.currentTextChanged.connect(self._load_selected_curve)
        self.new_curve_button = QPushButton("New Curve", self)
        self.new_curve_button.clicked.connect(self.create_curve)
        self.save_curve_button = QPushButton("Save Curve", self)
        self.save_curve_button.clicked.connect(self.save_curve)
        self.delete_curve_button = QPushButton("Delete Curve", self)
        self.delete_curve_button.clicked.connect(self.delete_curve)

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

        self.add_point_button = QPushButton("Add Point", self)
        self.add_point_button.clicked.connect(self.add_point)
        self.remove_point_button = QPushButton("Remove Point", self)
        self.remove_point_button.clicked.connect(self.remove_selected_point)
        self.hysteresis_spin = QDoubleSpinBox(self)
        self.hysteresis_spin.setRange(0.0, 20.0)
        self.hysteresis_spin.setSingleStep(0.5)

        self.fan_selector = QComboBox(self)
        self.fan_selector.currentTextChanged.connect(self._load_selected_fan)
        self.fan_curve_selector = QComboBox(self)
        self.temp_ids_edit = QLineEdit(self)
        self.temp_ids_edit.setPlaceholderText("Comma-separated sensor identifiers")
        self.aggregation_selector = QComboBox(self)
        self.aggregation_selector.addItems(get_valid_aggregation_methods())
        self.save_fan_button = QPushButton("Save Fan Settings", self)
        self.save_fan_button.clicked.connect(self.save_fan_settings)

        self.poll_interval_spin = QDoubleSpinBox(self)
        self.poll_interval_spin.setRange(0.1, 60.0)
        self.poll_interval_spin.setSingleStep(0.1)
        self.poll_interval_spin.setDecimals(1)
        self.poll_interval_spin.setKeyboardTracking(False)
        self.save_settings_button = QPushButton("Save Settings", self)
        self.save_settings_button.clicked.connect(self.save_general_settings)

        self.curve_points_section = self.accordion.add_section(
            "Curve Points",
            summary="3 points · Hysteresis 3.0°C",
            open_=True,
        )
        curve_points_header = QHBoxLayout()
        curve_points_header.addWidget(QLabel("Curve", self))
        curve_points_header.addWidget(self.curve_selector, 1)
        self.curve_points_section.add_layout(curve_points_header)
        self.curve_points_section.add_widget(self.points_table)
        curve_points_actions = QHBoxLayout()
        curve_points_actions.addWidget(self.new_curve_button)
        curve_points_actions.addWidget(self.save_curve_button)
        curve_points_actions.addWidget(self.delete_curve_button)
        curve_points_actions.addWidget(self.add_point_button)
        curve_points_actions.addWidget(self.remove_point_button)
        curve_points_actions.addStretch(1)
        self.curve_points_section.add_layout(curve_points_actions)

        self.fan_assignment_section = self.accordion.add_section(
            "Fan Assignment",
            summary="No fan selected",
        )
        fan_assignment_layout = QGridLayout()
        fan_assignment_layout.setHorizontalSpacing(10)
        fan_assignment_layout.setVerticalSpacing(10)
        fan_assignment_layout.addWidget(QLabel("Fan", self), 0, 0)
        fan_assignment_layout.addWidget(self.fan_selector, 0, 1)
        fan_assignment_layout.addWidget(QLabel("Assigned curve", self), 1, 0)
        fan_assignment_layout.addWidget(self.fan_curve_selector, 1, 1)
        self.fan_assignment_section.add_layout(fan_assignment_layout)

        self.sensor_mapping_section = self.accordion.add_section(
            "Sensor Mapping",
            summary="No sensors selected",
        )
        sensor_mapping_layout = QGridLayout()
        sensor_mapping_layout.setHorizontalSpacing(10)
        sensor_mapping_layout.setVerticalSpacing(10)
        sensor_mapping_layout.addWidget(QLabel("Temp sensor IDs", self), 0, 0)
        sensor_mapping_layout.addWidget(self.temp_ids_edit, 0, 1)
        sensor_mapping_layout.addWidget(QLabel("Aggregation", self), 1, 0)
        sensor_mapping_layout.addWidget(self.aggregation_selector, 1, 1)
        sensor_mapping_layout.addWidget(self.save_fan_button, 2, 0, 1, 2)
        self.sensor_mapping_section.add_layout(sensor_mapping_layout)

        self.general_settings_section = self.accordion.add_section(
            "General Settings",
            summary="Poll 1.0s · Hysteresis 3.0°C",
        )
        general_settings_layout = QGridLayout()
        general_settings_layout.setHorizontalSpacing(10)
        general_settings_layout.setVerticalSpacing(10)
        general_settings_layout.addWidget(QLabel("Poll interval (s)", self), 0, 0)
        general_settings_layout.addWidget(self.poll_interval_spin, 0, 1)
        general_settings_layout.addWidget(QLabel("Hysteresis (°C)", self), 1, 0)
        general_settings_layout.addWidget(self.hysteresis_spin, 1, 1)
        general_settings_layout.addWidget(self.save_settings_button, 2, 0, 1, 2)
        self.general_settings_section.add_layout(general_settings_layout)

        self.profiles_section = self.accordion.add_section(
            "Profiles",
            summary="default",
        )
        profile_layout = QGridLayout()
        profile_layout.setHorizontalSpacing(10)
        profile_layout.setVerticalSpacing(10)
        profile_layout.addWidget(QLabel("Profile", self), 0, 0)
        profile_layout.addWidget(self.profile_selector, 0, 1)
        profile_actions = QHBoxLayout()
        profile_actions.addWidget(self.switch_profile_button)
        profile_actions.addWidget(self.new_profile_button)
        profile_actions.addWidget(self.rename_profile_button)
        profile_actions.addWidget(self.refresh_button)
        profile_actions.addStretch(1)
        profile_layout.addLayout(profile_actions, 1, 0, 1, 2)
        self.profiles_section.add_layout(profile_layout)

        self.right_column = QWidget(self)
        self.right_column.setObjectName("curvesRightColumn")
        right_layout = QVBoxLayout(self.right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        content_row.addWidget(self.right_column, 1)

        self.preview_group = QFrame(self.right_column)
        self.preview_group.setObjectName("previewGroup")
        self.preview_group.setProperty("liveValueCard", True)
        self.preview_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        preview_layout = QVBoxLayout(self.preview_group)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(12)

        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("Curve Preview", self.preview_group))
        preview_header.addStretch(1)
        preview_layout.addLayout(preview_header)

        live_row = QHBoxLayout()
        live_row.setSpacing(10)
        self.live_temp_card = QFrame(self.preview_group)
        self.live_temp_card.setProperty("liveValueCard", True)
        live_temp_layout = QVBoxLayout(self.live_temp_card)
        live_temp_layout.setContentsMargins(10, 10, 10, 10)
        live_temp_layout.setSpacing(4)
        live_temp_title = QLabel("Live temperature", self.live_temp_card)
        live_temp_title.setObjectName("liveValueTitle")
        self.live_temp_value_label = QLabel("—", self.live_temp_card)
        self.live_temp_value_label.setObjectName("liveTempValue")
        live_temp_layout.addWidget(live_temp_title)
        live_temp_layout.addWidget(self.live_temp_value_label)

        self.live_fan_card = QFrame(self.preview_group)
        self.live_fan_card.setProperty("liveValueCard", True)
        live_fan_layout = QVBoxLayout(self.live_fan_card)
        live_fan_layout.setContentsMargins(10, 10, 10, 10)
        live_fan_layout.setSpacing(4)
        live_fan_title = QLabel("Selected fan", self.live_fan_card)
        live_fan_title.setObjectName("liveValueTitle")
        self.live_fan_value_label = QLabel("—", self.live_fan_card)
        self.live_fan_value_label.setObjectName("liveFanValue")
        live_fan_layout.addWidget(live_fan_title)
        live_fan_layout.addWidget(self.live_fan_value_label)

        live_row.addWidget(self.live_temp_card)
        live_row.addWidget(self.live_fan_card)
        preview_layout.addLayout(live_row)

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

        self.points_table.itemChanged.connect(self._handle_curve_inputs_changed)
        self.hysteresis_spin.valueChanged.connect(self._handle_curve_inputs_changed)
        self.setStyleSheet(flat_management_page_stylesheet(self.palette()))

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
        self.poll_interval_spin.setValue(
            self._normalized_poll_interval(self._config.poll_interval)
        )
        self._populate_profile_selector()
        self._populate_curve_selector()
        self._populate_fan_selector()
        self.preview_curve()
        self._update_live_preview_summary()
        self._update_section_summaries()
        self._update_status_label()

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
        self._update_section_summaries()

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
        self._update_section_summaries()

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
        self._update_section_summaries()

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
        self._update_section_summaries()

    def preview_curve(self) -> None:
        """Preview the current curve in the interactive plot."""
        points = self._collect_points()
        if len(points) < 2:
            self.preview_result_label.setText(
                "Hover over the graph to inspect values. Drag control points to edit the curve."
            )
            self._plot_preview([])
            self._update_section_summaries()
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
        self._update_section_summaries()

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
        self._update_section_summaries()

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
        self._update_section_summaries()

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
        self._update_section_summaries()

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
        self._update_section_summaries()

    def _load_selected_curve(self, curve_name: str) -> None:
        if self._config is None or curve_name not in self._config.curves:
            self._load_curve_points([])
            return

        curve = self._config.curves[curve_name]
        self._load_curve_points(curve.points)
        self.hysteresis_spin.setValue(curve.hysteresis)
        self.preview_curve()
        self._update_section_summaries()

    def _load_selected_fan(self, fan_name: str) -> None:
        if self._config is None or fan_name not in self._config.fans:
            self.temp_ids_edit.clear()
            return

        fan = self._config.fans[fan_name]
        self.fan_curve_selector.setCurrentText(fan.curve)
        self.curve_selector.setCurrentText(fan.curve)
        self.temp_ids_edit.setText(", ".join(fan.temp_ids))
        self.aggregation_selector.setCurrentText(fan.aggregation)
        self._update_section_summaries()

    def _load_curve_points(self, points) -> None:
        self._syncing_points = True
        self.points_table.setRowCount(0)
        for temp, speed in points:
            self._append_point_row(float(temp), float(speed))
        self._syncing_points = False
        self.preview_curve()
        self._update_section_summaries()

    def _append_point_row(self, temperature: float, speed: float) -> None:
        row = self.points_table.rowCount()
        self.points_table.insertRow(row)
        self.points_table.setItem(row, 0, QTableWidgetItem(f"{temperature:.1f}"))
        self.points_table.setItem(row, 1, QTableWidgetItem(f"{speed:.1f}"))

    def _handle_curve_inputs_changed(self, *_args) -> None:
        if self._syncing_points:
            return
        self.preview_curve()
        self._update_section_summaries()

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

    def _update_live_preview_summary(self) -> None:
        state = read_daemon_state(self._state_path)

        temp_text = "—"
        if state is not None:
            for sensor in state.temperatures:
                if sensor.value is not None:
                    temp_text = f"{float(sensor.value):.1f} °C"
                    break

        fan_text = "—"
        selected_fan_name = self.fan_selector.currentText().strip()
        if state is not None and self._config is not None and selected_fan_name:
            fan_config = self._config.fans.get(selected_fan_name)
            if fan_config is not None:
                candidate_ids = {fan_config.fan_id}
                if "/control/" in fan_config.fan_id:
                    candidate_ids.add(fan_config.fan_id.replace("/control/", "/fan/"))
                if "/fan/" in fan_config.fan_id:
                    candidate_ids.add(fan_config.fan_id.replace("/fan/", "/control/"))
                for fan in state.fan_speeds:
                    if (
                        fan.control_identifier in candidate_ids
                        or fan.identifier in candidate_ids
                    ):
                        if fan.current_control_pct is not None:
                            fan_text = f"{float(fan.current_control_pct):.0f}%"
                        elif fan.rpm is not None:
                            fan_text = f"{float(fan.rpm):.0f} rpm"
                        break

        self.live_temp_value_label.setText(temp_text)
        self.live_fan_value_label.setText(fan_text)

    def _update_section_summaries(self) -> None:
        curve_summary = f"{self.points_table.rowCount()} points"
        if self._config is not None:
            curve_name = self.curve_selector.currentText().strip()
            if curve_name in self._config.curves:
                curve = self._config.curves[curve_name]
                curve_summary = (
                    f"{len(curve.points)} points · Hysteresis {curve.hysteresis:.1f}°C"
                )
        self.curve_points_section.set_summary(curve_summary)

        fan_name = self.fan_selector.currentText().strip()
        if self._config is not None and fan_name in self._config.fans:
            fan = self._config.fans[fan_name]
            fan_summary = f"{fan_name} → {fan.curve}"
            if fan.temp_ids:
                fan_summary = f"{fan_summary} · {len(fan.temp_ids)} sensors"
        else:
            fan_summary = "No fan selected"
        self.fan_assignment_section.set_summary(fan_summary)

        temp_ids = [
            item.strip()
            for item in self.temp_ids_edit.text().split(",")
            if item.strip()
        ]
        if temp_ids:
            sensor_summary = (
                f"{len(temp_ids)} sensors · {self.aggregation_selector.currentText()}"
            )
        else:
            sensor_summary = f"{self.aggregation_selector.currentText()} · no sensors"
        self.sensor_mapping_section.set_summary(sensor_summary)

        self.general_settings_section.set_summary(
            f"Poll {self.poll_interval_spin.value():.1f}s · Hysteresis {self.hysteresis_spin.value():.1f}°C"
        )

        active_profile = (
            self.profile_selector.currentText().strip() or self._active_profile
        )
        self.profiles_section.set_summary(active_profile or "No profile selected")

    def _update_status_label(self) -> None:
        profile = self._active_profile or "default"
        poll = self.poll_interval_spin.value()
        hyst = self.hysteresis_spin.value()
        self.status_label.setText(
            f"● {profile} · Poll {poll:.1f}s · Hysteresis {hyst:.1f}°C"
        )

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
