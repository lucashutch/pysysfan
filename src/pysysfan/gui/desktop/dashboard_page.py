"""Dashboard page for the PySide6 desktop GUI."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pysysfan.config import Config, FanConfig
from pysysfan.gui.desktop.local_backend import read_daemon_state, run_service_command
from pysysfan.gui.desktop.theme import (
    DASHBOARD_PAGE_QSS,
    EMPHASIS_TEXT_STYLE,
    PAGE_HEADING_STYLE,
    SECTION_HINT_STYLE,
    SUBTLE_TEXT_STYLE,
    badge_stylesheet,
    message_stylesheet,
)
from pysysfan.platforms import windows_service
from pysysfan.profiles import ProfileManager
from pysysfan.state_file import DEFAULT_STATE_PATH, DaemonStateFile

try:  # pragma: no cover - exercised indirectly when installed
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - fallback path when optional dep missing
    pg = None


class DashboardPage(QWidget):
    """Desktop dashboard backed by the local daemon state file."""

    HISTORY_WINDOWS = {
        "60 s": 60,
        "5 min": 300,
        "15 min": 900,
    }
    PLOT_COLORS = [
        "#4E79A7",
        "#F28E2B",
        "#E15759",
        "#76B7B2",
        "#59A14F",
        "#EDC948",
        "#B07AA1",
        "#FF9DA7",
    ]

    def __init__(
        self,
        state_path: Path = DEFAULT_STATE_PATH,
        service_action_runner=None,
        service_status_getter=None,
        profile_manager: ProfileManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._state_path = Path(state_path)
        self._service_action_runner = service_action_runner or run_service_command
        self._service_status_getter = (
            service_status_getter or windows_service.get_service_status
        )
        self._profile_manager = profile_manager or ProfileManager()
        self._history_seconds = self.HISTORY_WINDOWS["60 s"]
        self._last_state_timestamp: float | None = None
        self._temperature_history: dict[str, deque[tuple[float, float]]] = defaultdict(
            deque
        )
        self._fan_rpm_history: dict[str, deque[tuple[float, float]]] = defaultdict(
            deque
        )
        self._fan_target_history: dict[str, deque[tuple[float, float]]] = defaultdict(
            deque
        )
        self._temperature_labels: dict[str, str] = {}
        self._fan_labels: dict[str, str] = {}
        self._target_labels: dict[str, str] = {}
        self._fan_summary_cards: list[QWidget] = []
        self.setStyleSheet(DASHBOARD_PAGE_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Dashboard", self)
        heading.setObjectName("dashboardTitle")
        heading.setStyleSheet(PAGE_HEADING_STYLE)
        layout.addWidget(heading)

        hint = QLabel(
            "Live control view for the active profile, current fan targets, and controlling sensors.",
            self,
        )
        hint.setStyleSheet(SECTION_HINT_STYLE)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.connection_label = QLabel("Daemon: Waiting for state file", self)
        self.connection_label.setObjectName("connectionLabel")
        toolbar.addWidget(self.connection_label)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.refresh_button)

        self.start_service_button = QPushButton("Start Service", self)
        self.start_service_button.setObjectName("startServiceButton")
        self.start_service_button.clicked.connect(self.start_service)
        toolbar.addWidget(self.start_service_button)

        toolbar.addWidget(QLabel("History", self))
        self.history_selector = QComboBox(self)
        self.history_selector.setObjectName("historySelector")
        self.history_selector.addItems(list(self.HISTORY_WINDOWS))
        self.history_selector.currentTextChanged.connect(self._change_history_window)
        toolbar.addWidget(self.history_selector)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("dashboardMessageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)

        self.profile_overview_card = QFrame(self)
        self.profile_overview_card.setObjectName("profileOverviewCard")
        profile_layout = QVBoxLayout(self.profile_overview_card)
        profile_layout.setContentsMargins(20, 18, 20, 18)
        profile_layout.setSpacing(10)

        profile_header = QHBoxLayout()
        profile_header.setSpacing(12)
        profile_title = QLabel("Current Profile", self.profile_overview_card)
        profile_title.setProperty("cardTextRole", "eyebrow")
        profile_header.addWidget(profile_title)
        profile_header.addStretch(1)
        self.profile_status_badge = QLabel("Waiting", self.profile_overview_card)
        self.profile_status_badge.setObjectName("profileStatusBadge")
        self.profile_status_badge.setStyleSheet(badge_stylesheet("neutral"))
        profile_header.addWidget(self.profile_status_badge)
        profile_layout.addLayout(profile_header)

        self.active_profile_label = QLabel("N/A", self.profile_overview_card)
        self.active_profile_label.setObjectName("activeProfileLabel")
        self.active_profile_label.setProperty("cardTextRole", "value")
        profile_layout.addWidget(self.active_profile_label)

        self.active_profile_meta_label = QLabel("Profile details unavailable", self)
        self.active_profile_meta_label.setObjectName("activeProfileMetaLabel")
        self.active_profile_meta_label.setStyleSheet(EMPHASIS_TEXT_STYLE)
        self.active_profile_meta_label.setWordWrap(True)
        profile_layout.addWidget(self.active_profile_meta_label)

        self.active_profile_description_label = QLabel(
            "Waiting for the daemon snapshot.",
            self.profile_overview_card,
        )
        self.active_profile_description_label.setObjectName(
            "activeProfileDescriptionLabel"
        )
        self.active_profile_description_label.setStyleSheet(SUBTLE_TEXT_STYLE)
        self.active_profile_description_label.setWordWrap(True)
        profile_layout.addWidget(self.active_profile_description_label)
        layout.addWidget(self.profile_overview_card)

        self.fan_summary_group = QGroupBox("Active Fan Control", self)
        fan_summary_group_layout = QVBoxLayout(self.fan_summary_group)
        fan_summary_group_layout.setContentsMargins(14, 16, 14, 14)
        fan_summary_group_layout.setSpacing(10)

        fan_summary_hint = QLabel(
            "Each card shows a configured fan, its live target, and the sensor set driving it.",
            self.fan_summary_group,
        )
        fan_summary_hint.setStyleSheet(SUBTLE_TEXT_STYLE)
        fan_summary_hint.setWordWrap(True)
        fan_summary_group_layout.addWidget(fan_summary_hint)

        self.fan_summary_empty_label = QLabel(
            "No active fan mappings available yet.",
            self.fan_summary_group,
        )
        self.fan_summary_empty_label.setObjectName("fanSummaryEmptyLabel")
        self.fan_summary_empty_label.setStyleSheet(SUBTLE_TEXT_STYLE)
        self.fan_summary_empty_label.setWordWrap(True)
        fan_summary_group_layout.addWidget(self.fan_summary_empty_label)

        self.fan_summary_layout = QGridLayout()
        self.fan_summary_layout.setHorizontalSpacing(12)
        self.fan_summary_layout.setVerticalSpacing(12)
        fan_summary_group_layout.addLayout(self.fan_summary_layout)
        layout.addWidget(self.fan_summary_group)

        summary_layout = QGridLayout()
        summary_layout.setHorizontalSpacing(16)
        summary_layout.setVerticalSpacing(16)

        daemon_card, self.daemon_status_label = self._create_stat_card(
            "Daemon status",
            "Waiting",
            "Looking for the local state snapshot",
            accent="#2563eb",
        )
        uptime_card, self.uptime_label = self._create_stat_card(
            "Uptime",
            "N/A",
            "Daemon runtime",
            accent="#0891b2",
        )
        poll_card, self.poll_interval_label = self._create_stat_card(
            "Poll interval",
            "N/A",
            "Control loop cadence",
            accent="#0f766e",
        )
        hottest_card, self.hottest_temp_label = self._create_stat_card(
            "Hottest temp",
            "N/A",
            "Highest live sensor reading",
            accent="#dc2626",
        )
        target_card, self.target_pwm_label = self._create_stat_card(
            "Target PWM",
            "N/A",
            "Highest current fan target",
            accent="#ea580c",
        )
        fans_card, self.fans_configured_label = self._create_stat_card(
            "Configured fans",
            "N/A",
            "Fan rules in the active config",
            accent="#2563eb",
        )
        curves_card, self.curves_configured_label = self._create_stat_card(
            "Configured curves",
            "N/A",
            "Saved named curve definitions",
            accent="#4f46e5",
        )
        alerts_card, self.recent_alerts_label = self._create_stat_card(
            "Recent alerts",
            "0",
            "Newest alert count in the daemon snapshot",
            accent="#dc2626",
        )

        cards = [
            daemon_card,
            uptime_card,
            poll_card,
            hottest_card,
            target_card,
            fans_card,
            curves_card,
            alerts_card,
        ]
        for index, card in enumerate(cards):
            summary_layout.addWidget(card, index // 4, index % 4)

        layout.addLayout(summary_layout)

        details_group = QGroupBox("Config Details", self)
        details_layout = QGridLayout(details_group)
        details_layout.setHorizontalSpacing(24)
        details_layout.setVerticalSpacing(8)

        self.config_path_label = QLabel("Config path: N/A", self)
        self.config_path_label.setWordWrap(True)
        self.config_error_label = QLabel("Config error: none", self)
        self.config_error_label.setWordWrap(True)
        self.config_error_label.setStyleSheet("color: #1d6f42; font-weight: 600;")

        details_layout.addWidget(self.config_path_label, 0, 0)
        details_layout.addWidget(self.config_error_label, 1, 0)
        layout.addWidget(details_group)

        plots_layout = QGridLayout()
        plots_layout.setHorizontalSpacing(16)
        plots_layout.setVerticalSpacing(16)

        self.temperature_plot = self._create_plot_widget(
            "Temperatures", "Seconds", "°C"
        )
        self.fan_rpm_plot = self._create_plot_widget("Fan RPM", "Seconds", "RPM")
        self.fan_target_plot = self._create_plot_widget("Target PWM", "Seconds", "%")

        self.temperature_plot.setMinimumHeight(320)
        self.fan_rpm_plot.setMinimumHeight(260)
        self.fan_target_plot.setMinimumHeight(260)

        plots_layout.addWidget(self.temperature_plot, 0, 0, 1, 2)
        plots_layout.addWidget(self.fan_rpm_plot, 1, 0)
        plots_layout.addWidget(self.fan_target_plot, 1, 1)
        layout.addLayout(plots_layout, 3)

        tables_layout = QHBoxLayout()
        tables_layout.setSpacing(16)

        self.temperatures_table = QTableWidget(0, 3, self)
        self.temperatures_table.setObjectName("temperaturesTable")
        self.temperatures_table.setHorizontalHeaderLabels(
            ["Hardware", "Sensor", "Value"]
        )
        self.temperatures_table.horizontalHeader().setStretchLastSection(True)
        self.temperatures_table.setMinimumHeight(220)
        temps_group = self._wrap_widget("Temperatures", self.temperatures_table)
        tables_layout.addWidget(temps_group, 2)

        self.fans_table = QTableWidget(0, 5, self)
        self.fans_table.setObjectName("fansTable")
        self.fans_table.setHorizontalHeaderLabels(
            ["Hardware", "Fan", "RPM", "Actual PWM", "Target PWM"]
        )
        self.fans_table.horizontalHeader().setStretchLastSection(True)
        self.fans_table.setMinimumHeight(220)
        fans_group = self._wrap_widget("Fans", self.fans_table)
        tables_layout.addWidget(fans_group, 3)

        self.alerts_list = QListWidget(self)
        self.alerts_list.setObjectName("alertsList")
        self.alerts_list.setMinimumHeight(220)
        alerts_group = self._wrap_widget("Recent Alerts", self.alerts_list)
        tables_layout.addWidget(alerts_group, 2)

        layout.addLayout(tables_layout, 2)
        layout.addStretch(1)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self.refresh_data)
        self._refresh_timer.start()

    def refresh_data(self) -> None:
        """Refresh the dashboard using the latest local daemon state."""
        try:
            service_status = self._service_status_getter()
        except Exception:
            service_status = None

        state = read_daemon_state(self._state_path)
        if state is None:
            self._apply_offline_state(service_status)
            return

        self.connection_label.setText("Daemon: Connected")
        self.start_service_button.setEnabled(False)
        self._show_message("", is_error=False)
        self._apply_summary(state)
        self._apply_temperatures(state)
        self._apply_fans(state)
        self._apply_alerts(state)
        self._append_history(state)
        self._refresh_plots()

    def start_service(self) -> None:
        """Request startup of the configured service/task."""
        success, message = self._service_action_runner("start")
        self.refresh_data()
        self._show_message(message, is_error=not success)

    def _apply_offline_state(self, service_status) -> None:
        self.connection_label.setText("Daemon: Not running")
        self.daemon_status_label.setText("Not running")
        installed = bool(getattr(service_status, "task_installed", False))
        self.start_service_button.setEnabled(installed)
        if installed:
            self._show_message(
                "Daemon state file not found. Start the service to resume monitoring.",
                is_error=True,
            )
        else:
            self._show_message(
                "Daemon state file not found. Install the service from the Service tab.",
                is_error=True,
            )

        self.active_profile_label.setText("N/A")
        self.active_profile_meta_label.setText("Profile details unavailable")
        self.active_profile_description_label.setText(
            "Start the daemon to populate profile and control details."
        )
        self.profile_status_badge.setText("Offline")
        self.profile_status_badge.setStyleSheet(badge_stylesheet("warning"))
        self.uptime_label.setText("N/A")
        self.poll_interval_label.setText("N/A")
        self.hottest_temp_label.setText("N/A")
        self.target_pwm_label.setText("N/A")
        self.fans_configured_label.setText("N/A")
        self.curves_configured_label.setText("N/A")
        self.recent_alerts_label.setText("0")
        self.config_path_label.setText("Config path: N/A")
        self.config_error_label.setText("Config error: N/A")
        self.config_error_label.setStyleSheet("color: #b00020; font-weight: 600;")
        self.temperatures_table.setRowCount(0)
        self.fans_table.setRowCount(0)
        self.alerts_list.clear()
        self.alerts_list.addItem("No daemon state available")
        self._rebuild_fan_summary_cards(None, None)
        self._refresh_plots()

    def _apply_summary(self, state: DaemonStateFile) -> None:
        hottest_temp = max(
            (sensor.value for sensor in state.temperatures if sensor.value is not None),
            default=None,
        )
        max_target = max(state.fan_targets.values(), default=None)
        active_config = self._load_active_config(state)
        profile_display_name, profile_description = self._load_profile_metadata(state)

        self.daemon_status_label.setText("Connected")
        self.active_profile_label.setText(profile_display_name)
        fan_count = (
            len(active_config.fans)
            if active_config is not None
            else state.fans_configured
        )
        curve_count = (
            len(active_config.curves)
            if active_config is not None
            else state.curves_configured
        )
        self.active_profile_meta_label.setText(
            f"Profile key: {state.active_profile} • {fan_count} fans • {curve_count} curves"
        )
        self.active_profile_description_label.setText(
            profile_description
            or "Current profile loaded by the daemon. Live fan cards below show targets and controlling sensors."
        )
        badge_tone = "critical" if state.config_error else "success"
        badge_text = "Config issue" if state.config_error else "Live"
        self.profile_status_badge.setText(badge_text)
        self.profile_status_badge.setStyleSheet(badge_stylesheet(badge_tone))
        self.uptime_label.setText(f"{state.uptime_seconds:.1f}s")
        self.poll_interval_label.setText(f"{state.poll_interval:.1f}s")
        self.hottest_temp_label.setText(
            "N/A" if hottest_temp is None else f"{hottest_temp:.1f}°C"
        )
        self.target_pwm_label.setText(
            "N/A" if max_target is None else f"{max_target:.1f}%"
        )
        self.fans_configured_label.setText(str(fan_count))
        self.curves_configured_label.setText(str(curve_count))
        self.recent_alerts_label.setText(str(len(state.recent_alerts)))
        self.config_path_label.setText(f"Config path: {state.config_path}")
        if state.config_error:
            self.config_error_label.setText(f"Config error: {state.config_error}")
            self.config_error_label.setStyleSheet("color: #b00020; font-weight: 600;")
        else:
            self.config_error_label.setText("Config error: none")
            self.config_error_label.setStyleSheet("color: #1d6f42; font-weight: 600;")
        self._rebuild_fan_summary_cards(state, active_config)

    def _apply_temperatures(self, state: DaemonStateFile) -> None:
        self.temperatures_table.setRowCount(len(state.temperatures))
        for row, sensor in enumerate(state.temperatures):
            self._temperature_labels[sensor.identifier] = (
                f"{sensor.hardware_name} / {sensor.sensor_name}"
            )
            self.temperatures_table.setItem(
                row, 0, QTableWidgetItem(sensor.hardware_name)
            )
            self.temperatures_table.setItem(
                row, 1, QTableWidgetItem(sensor.sensor_name)
            )
            value_text = "N/A" if sensor.value is None else f"{sensor.value:.1f}°C"
            self.temperatures_table.setItem(row, 2, QTableWidgetItem(value_text))

    def _apply_fans(self, state: DaemonStateFile) -> None:
        self.fans_table.setRowCount(len(state.fan_speeds))
        for row, fan in enumerate(state.fan_speeds):
            label = f"{fan.hardware_name} / {fan.sensor_name}"
            self._fan_labels[fan.identifier] = label
            target_label = fan.control_identifier or fan.identifier
            self._target_labels[target_label] = label
            target_value = (
                state.fan_targets.get(fan.control_identifier)
                if fan.control_identifier is not None
                else None
            )
            rpm_text = "N/A" if fan.rpm is None else f"{fan.rpm:.0f}"
            actual_pwm_text = (
                "N/A"
                if fan.current_control_pct is None
                else f"{fan.current_control_pct:.1f}%"
            )
            target_pwm_text = "N/A" if target_value is None else f"{target_value:.1f}%"
            self.fans_table.setItem(row, 0, QTableWidgetItem(fan.hardware_name))
            self.fans_table.setItem(row, 1, QTableWidgetItem(fan.sensor_name))
            self.fans_table.setItem(row, 2, QTableWidgetItem(rpm_text))
            self.fans_table.setItem(row, 3, QTableWidgetItem(actual_pwm_text))
            self.fans_table.setItem(row, 4, QTableWidgetItem(target_pwm_text))

    def _apply_alerts(self, state: DaemonStateFile) -> None:
        self.alerts_list.clear()
        if not state.recent_alerts:
            self.alerts_list.addItem("No recent alerts")
            return

        for alert in reversed(state.recent_alerts[-10:]):
            self.alerts_list.addItem(
                f"{alert.sensor_id} [{alert.alert_type}] - {alert.message}"
            )

    def _append_history(self, state: DaemonStateFile) -> None:
        if self._last_state_timestamp == state.timestamp:
            return

        self._last_state_timestamp = state.timestamp
        for sensor in state.temperatures:
            if sensor.value is not None:
                self._temperature_history[sensor.identifier].append(
                    (state.timestamp, sensor.value)
                )

        for fan in state.fan_speeds:
            if fan.rpm is not None:
                self._fan_rpm_history[fan.identifier].append((state.timestamp, fan.rpm))
            if fan.control_identifier is not None:
                target = state.fan_targets.get(fan.control_identifier)
                if target is not None:
                    self._fan_target_history[fan.control_identifier].append(
                        (state.timestamp, target)
                    )

        self._trim_history(state.timestamp)

    def _trim_history(self, latest_timestamp: float) -> None:
        cutoff = latest_timestamp - self._history_seconds
        for history_map in (
            self._temperature_history,
            self._fan_rpm_history,
            self._fan_target_history,
        ):
            for sensor_id in list(history_map.keys()):
                series = history_map[sensor_id]
                while series and series[0][0] < cutoff:
                    series.popleft()
                if not series:
                    del history_map[sensor_id]

    def _change_history_window(self, label: str) -> None:
        self._history_seconds = self.HISTORY_WINDOWS.get(label, 60)
        if self._last_state_timestamp is not None:
            self._trim_history(self._last_state_timestamp)
        self._refresh_plots()

    def _create_plot_widget(self, title: str, x_label: str, y_label: str) -> QWidget:
        if pg is None:
            fallback = QLabel(
                f"Install pyqtgraph to enable the {title.lower()} graph.",
                self,
            )
            fallback.setWordWrap(True)
            return self._wrap_widget(title, fallback)

        plot_widget = pg.PlotWidget(self)
        plot_widget.setBackground("w")
        plot_widget.showGrid(x=True, y=True, alpha=0.2)
        plot_widget.setLabel("bottom", x_label)
        plot_widget.setLabel("left", y_label)
        plot_widget.addLegend()
        return self._wrap_widget(title, plot_widget)

    def _refresh_plots(self) -> None:
        if pg is None:
            return

        self._refresh_plot_widget(
            self.temperature_plot,
            self._temperature_history,
            self._temperature_labels,
        )
        self._refresh_plot_widget(
            self.fan_rpm_plot,
            self._fan_rpm_history,
            self._fan_labels,
        )
        self._refresh_plot_widget(
            self.fan_target_plot,
            self._fan_target_history,
            self._target_labels,
        )

    def _refresh_plot_widget(
        self,
        plot_container: QWidget,
        history_map: dict[str, deque[tuple[float, float]]],
        labels: dict[str, str],
    ) -> None:
        plot_widget = plot_container.layout().itemAt(0).widget()
        if pg is None or not isinstance(plot_widget, pg.PlotWidget):
            return

        plot_item = plot_widget.getPlotItem()
        plot_item.clear()
        if plot_item.legend is None:
            plot_item.addLegend()
        else:
            plot_item.legend.clear()
        if not history_map:
            return

        latest_timestamp = max(
            series[-1][0] for series in history_map.values() if series
        )
        for index, (sensor_id, series) in enumerate(sorted(history_map.items())):
            if not series:
                continue
            xs = [point[0] - latest_timestamp for point in series]
            ys = [point[1] for point in series]
            color = self.PLOT_COLORS[index % len(self.PLOT_COLORS)]
            plot_widget.plot(
                xs,
                ys,
                pen=pg.mkPen(color=color, width=2),
                name=labels.get(sensor_id, sensor_id),
            )

    def _create_stat_card(
        self,
        title: str,
        initial_value: str,
        subtitle: str,
        *,
        accent: str,
    ) -> tuple[QFrame, QLabel]:
        card = QFrame(self)
        card.setObjectName(title.lower().replace(" ", "") + "Card")
        card.setProperty("cardRole", "metric")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(6)

        icon_and_title = QHBoxLayout()
        icon_and_title.setSpacing(8)

        icon_label = QLabel(self._metric_icon(title), card)
        icon_label.setProperty("cardTextRole", "icon")
        icon_and_title.addWidget(icon_label)

        title_label = QLabel(title, card)
        title_label.setProperty("cardTextRole", "eyebrow")
        icon_and_title.addWidget(title_label)
        icon_and_title.addStretch(1)
        card_layout.addLayout(icon_and_title)

        value_label = QLabel(initial_value, card)
        value_label.setProperty("cardTextRole", "value")
        value_label.setStyleSheet(
            f"border-left: 4px solid {accent}; padding-left: 10px;"
        )
        card_layout.addWidget(value_label)

        subtitle_label = QLabel(subtitle, card)
        subtitle_label.setWordWrap(True)
        subtitle_label.setProperty("cardTextRole", "body")
        card_layout.addWidget(subtitle_label)
        card_layout.addStretch(1)

        return card, value_label

    def _load_active_config(self, state: DaemonStateFile) -> Config | None:
        config_path = Path(state.config_path)
        if config_path.exists():
            try:
                return Config.load(config_path)
            except Exception:
                return None
        return None

    def _load_profile_metadata(self, state: DaemonStateFile) -> tuple[str, str]:
        try:
            profile = self._profile_manager.get_profile(state.active_profile)
        except Exception:
            return state.active_profile, ""

        display_name = profile.metadata.display_name or state.active_profile
        return display_name, profile.metadata.description

    def _rebuild_fan_summary_cards(
        self,
        state: DaemonStateFile | None,
        active_config: Config | None,
    ) -> None:
        while self.fan_summary_layout.count():
            item = self.fan_summary_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._fan_summary_cards.clear()
        if state is None or active_config is None or not active_config.fans:
            self.fan_summary_empty_label.show()
            return

        self.fan_summary_empty_label.hide()
        for index, (fan_name, fan_config) in enumerate(
            sorted(active_config.fans.items())
        ):
            card = self._create_fan_summary_card(state, fan_name, fan_config)
            self._fan_summary_cards.append(card)
            self.fan_summary_layout.addWidget(card, index // 3, index % 3)

    def _create_fan_summary_card(
        self,
        state: DaemonStateFile,
        fan_name: str,
        fan_config: FanConfig,
    ) -> QFrame:
        card = QFrame(self.fan_summary_group)
        card.setObjectName(f"{fan_name}SummaryCard")
        card.setProperty("cardRole", "fan-summary")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)

        icon_label = QLabel("🌀", card)
        icon_label.setProperty("cardTextRole", "icon")
        header.addWidget(icon_label)

        title_label = QLabel(
            self._friendly_fan_name(fan_name, fan_config, state),
            card,
        )
        title_label.setProperty("cardTextRole", "title")
        header.addWidget(title_label)
        header.addStretch(1)

        target_value = state.fan_targets.get(fan_config.fan_id)
        target_badge = QLabel(
            "Awaiting target"
            if target_value is None
            else f"Target {target_value:.0f}%",
            card,
        )
        target_badge.setStyleSheet(
            badge_stylesheet("warning" if target_value is None else "info")
        )
        header.addWidget(target_badge)
        layout.addLayout(header)

        value_label = QLabel(
            "No live target" if target_value is None else f"{target_value:.1f}%",
            card,
        )
        value_label.setProperty("cardTextRole", "value")
        layout.addWidget(value_label)

        live_fan = self._find_live_fan_state(state, fan_config)
        details = []
        details.append(f"Curve: {fan_config.curve}")
        details.append(f"Aggregation: {fan_config.aggregation}")
        if live_fan is not None and live_fan.rpm is not None:
            details.append(f"RPM: {live_fan.rpm:.0f}")
        if live_fan is not None and live_fan.current_control_pct is not None:
            details.append(f"Actual: {live_fan.current_control_pct:.1f}%")

        details_label = QLabel(" • ".join(details), card)
        details_label.setProperty("cardTextRole", "body")
        details_label.setWordWrap(True)
        layout.addWidget(details_label)

        sensor_labels = self._resolve_sensor_labels(state, fan_config.temp_ids)
        sensors_label = QLabel(
            "Sensors: " + ", ".join(sensor_labels),
            card,
        )
        sensors_label.setProperty("cardTextRole", "muted")
        sensors_label.setWordWrap(True)
        layout.addWidget(sensors_label)
        return card

    def _find_live_fan_state(self, state: DaemonStateFile, fan_config: FanConfig):
        for fan in state.fan_speeds:
            if (
                fan.control_identifier == fan_config.fan_id
                or fan.identifier == fan_config.fan_id
            ):
                return fan
        return None

    def _friendly_fan_name(
        self,
        fan_name: str,
        fan_config: FanConfig,
        state: DaemonStateFile,
    ) -> str:
        if fan_config.header_name:
            return fan_config.header_name

        live_fan = self._find_live_fan_state(state, fan_config)
        if live_fan is not None:
            return f"{live_fan.hardware_name} / {live_fan.sensor_name}"

        return fan_name.replace("_", " ").title()

    def _resolve_sensor_labels(
        self,
        state: DaemonStateFile,
        sensor_ids: list[str],
    ) -> list[str]:
        labels = {
            sensor.identifier: f"{sensor.hardware_name} / {sensor.sensor_name}"
            for sensor in state.temperatures
        }
        resolved = [
            labels.get(sensor_id, self._compact_identifier(sensor_id))
            for sensor_id in sensor_ids
        ]
        return resolved or ["No sensors configured"]

    @staticmethod
    def _compact_identifier(identifier: str) -> str:
        trimmed = identifier.strip("/")
        if not trimmed:
            return identifier
        parts = trimmed.split("/")
        return " / ".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

    @staticmethod
    def _metric_icon(title: str) -> str:
        icon_map = {
            "Daemon status": "●",
            "Uptime": "⏱",
            "Poll interval": "◷",
            "Hottest temp": "🌡",
            "Target PWM": "🎯",
            "Configured fans": "🌀",
            "Configured curves": "📈",
            "Recent alerts": "⚠",
        }
        return icon_map.get(title, "•")

    @staticmethod
    def _wrap_widget(title: str, widget: QWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(widget)
        return group

    def _show_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.message_label.clear()
            self.message_label.hide()
            return

        self.message_label.setStyleSheet(message_stylesheet(is_error=is_error))
        self.message_label.setText(message)
        self.message_label.show()
