"""Dashboard page for the PySide6 desktop GUI."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QSplitter,
)

from pysysfan.config import Config, FanConfig
from pysysfan.gui.desktop.local_backend import (
    read_daemon_history,
    read_daemon_state,
    run_service_command,
)
from pysysfan.gui.desktop.plotting import DashboardPlotWidget, ElapsedSecondsAxis, pg
from pysysfan.gui.desktop.theme import (
    SECTION_SUBTITLE_STYLE,
    SECTION_TITLE_STYLE,
    SUBTLE_TEXT_STYLE,
    badge_stylesheet,
    dashboard_page_stylesheet,
    message_stylesheet,
    plot_theme,
)
from pysysfan.history_file import DEFAULT_HISTORY_PATH, HistorySample
from pysysfan.platforms import windows_service
from pysysfan.profiles import ProfileManager
from pysysfan.state_file import DEFAULT_STATE_PATH, DaemonStateFile


class DashboardPage(QWidget):
    """Desktop dashboard backed by the local daemon state file."""

    REFRESH_INTERVAL_MS = 1000
    IDLE_REFRESH_INTERVAL_MS = 3000
    OFFLINE_REFRESH_INTERVAL_MS = 5000

    HISTORY_WINDOWS = {
        "60 s": 60,
        "5 min": 300,
        "15 min": 900,
    }

    def __init__(
        self,
        state_path: Path = DEFAULT_STATE_PATH,
        history_path: Path = DEFAULT_HISTORY_PATH,
        service_action_runner=None,
        service_status_getter=None,
        profile_manager: ProfileManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._state_path = Path(state_path)
        self._history_path = Path(history_path)
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
        self._fan_groups: dict[str, str] = {}
        self._target_groups: dict[str, str] = {}
        self._fan_summary_cards: list[QWidget] = []
        self._daemon_indicator_tone = "warning"
        self._alerts_badge_tone = "neutral"
        self._recent_alerts: list[str] = []
        self._active_config: Config | None = None
        self._graph_controls: dict[str, dict[str, QWidget | QMenu]] = {}
        self._graph_enabled_series: dict[str, set[str]] = {
            "temperature": set(),
            "fan_rpm": set(),
            "fan_target": set(),
        }
        self._graph_defaults_initialized: set[str] = set()
        self._last_polled_state_timestamp: float | None = None

        self.setObjectName("dashboardRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("dashboardScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.scroll_area)

        self.content = QWidget(self.scroll_area)
        self.content.setObjectName("dashboardContent")
        self.scroll_area.setWidget(self.content)

        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(16)

        self.status_corner_widget = QWidget(self)
        self.status_corner_widget.setObjectName("dashboardStatusCorner")
        status_layout = QHBoxLayout(self.status_corner_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)

        self.daemon_indicator = QLabel("●", self.status_corner_widget)
        self.daemon_indicator.setObjectName("daemonIndicator")
        self.daemon_indicator.setToolTip("Waiting for daemon state")
        status_layout.addWidget(self.daemon_indicator)

        self.alerts_button = QToolButton(self.status_corner_widget)
        self.alerts_button.setObjectName("alertsButton")
        self.alerts_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.alerts_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.alerts_menu = QMenu(self.alerts_button)
        self.alerts_button.setMenu(self.alerts_menu)
        status_layout.addWidget(self.alerts_button)

        self.message_label = QLabel("", self.content)
        self.message_label.setObjectName("dashboardMessageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        content_layout.addWidget(self.message_label)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self.content)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setMinimumHeight(800)
        content_layout.addWidget(self.main_splitter, 1)

        self.left_panel = QWidget(self.main_splitter)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)

        self.fan_summary_group = QGroupBox("Fan Groups", self.left_panel)
        self.fan_summary_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        fan_summary_layout = QVBoxLayout(self.fan_summary_group)
        fan_summary_layout.setContentsMargins(16, 18, 16, 16)
        fan_summary_layout.setSpacing(10)

        fan_summary_heading = QLabel(
            "Configured fan groups, their live targets, and the sensors currently steering them."
        )
        fan_summary_heading.setProperty("sectionRole", "subtitle")
        fan_summary_heading.setWordWrap(True)
        fan_summary_layout.addWidget(fan_summary_heading)

        self.fan_summary_empty_label = QLabel(
            "No active fan mappings available yet.",
            self.fan_summary_group,
        )
        self.fan_summary_empty_label.setObjectName("fanSummaryEmptyLabel")
        self.fan_summary_empty_label.setStyleSheet(SUBTLE_TEXT_STYLE)
        self.fan_summary_empty_label.setWordWrap(True)
        fan_summary_layout.addWidget(self.fan_summary_empty_label)

        self.fan_summary_scroll_area = QScrollArea(self.fan_summary_group)
        self.fan_summary_scroll_area.setObjectName("fanSummaryScrollArea")
        self.fan_summary_scroll_area.setWidgetResizable(True)
        self.fan_summary_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.fan_summary_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        fan_summary_layout.addWidget(self.fan_summary_scroll_area, 1)

        self.fan_summary_scroll_content = QWidget(self.fan_summary_scroll_area)
        self.fan_summary_scroll_content.setObjectName("fanSummaryScrollContent")
        self.fan_summary_scroll_area.setWidget(self.fan_summary_scroll_content)

        self.fan_summary_layout = QGridLayout(self.fan_summary_scroll_content)
        self.fan_summary_layout.setContentsMargins(0, 0, 0, 0)
        self.fan_summary_layout.setHorizontalSpacing(12)
        self.fan_summary_layout.setVerticalSpacing(12)
        left_layout.addWidget(self.fan_summary_group, 1)

        self.right_panel = QWidget(self.main_splitter)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)

        graph_header = QHBoxLayout()
        graph_header.setSpacing(12)
        graph_heading = QLabel("Live Graphs", self.right_panel)
        graph_heading.setStyleSheet(SECTION_TITLE_STYLE)
        graph_header.addWidget(graph_heading)

        graph_subtitle = QLabel(
            "Recent temperature, RPM, and target history.",
            self.right_panel,
        )
        graph_subtitle.setStyleSheet(SECTION_SUBTITLE_STYLE)
        graph_header.addWidget(graph_subtitle)
        graph_header.addStretch(1)

        history_label = QLabel("History", self.right_panel)
        history_label.setObjectName("historySelectorLabel")
        history_label.setProperty("sectionRole", "subtitle")
        graph_header.addWidget(history_label)

        self.history_selector = QComboBox(self.right_panel)
        self.history_selector.setObjectName("historySelector")
        self.history_selector.addItems(list(self.HISTORY_WINDOWS))
        self.history_selector.setMinimumContentsLength(4)
        self.history_selector.setMaximumWidth(98)
        self.history_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self.history_selector.currentTextChanged.connect(self._change_history_window)
        graph_header.addWidget(self.history_selector)
        right_layout.addLayout(graph_header)

        self.temperature_plot = self._create_plot_widget(
            "temperature",
            "Temperatures",
            "",
            "°C",
        )
        self.temperature_plot.setMinimumHeight(220)
        self.temperature_plot.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        right_layout.addWidget(self.temperature_plot, 1)

        self.fan_rpm_plot = self._create_plot_widget(
            "fan_rpm",
            "Fan RPM",
            "",
            "RPM",
        )
        self.fan_target_plot = self._create_plot_widget(
            "fan_target",
            "Target PWM",
            "",
            "%",
        )
        self.fan_rpm_plot.setMinimumHeight(180)
        self.fan_target_plot.setMinimumHeight(180)
        self.fan_rpm_plot.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.fan_target_plot.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        right_layout.addWidget(self.fan_rpm_plot, 1)
        right_layout.addWidget(self.fan_target_plot, 1)

        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.right_panel)
        self.left_panel.setMinimumWidth(440)
        self.right_panel.setMinimumWidth(520)
        self.right_panel.setMinimumHeight(800)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([470, 980])

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh_data)

        self._apply_theme()
        self._apply_offline_state(None)

    def showEvent(self, event) -> None:  # noqa: N802
        """Refresh and poll only while the dashboard page is visible."""
        super().showEvent(event)
        self.refresh_data()
        self._refresh_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        """Stop periodic polling when the dashboard page is hidden."""
        self._refresh_timer.stop()
        super().hideEvent(event)

    def refresh_data(self) -> None:
        """Refresh the dashboard using the latest local daemon state."""
        try:
            service_status = self._service_status_getter()
        except Exception:
            service_status = None

        state = read_daemon_state(self._state_path)
        if state is None:
            self._set_refresh_interval(self.OFFLINE_REFRESH_INTERVAL_MS)
            self._last_polled_state_timestamp = None
            self._apply_offline_state(service_status)
            return

        if (not state.running) or (
            self._last_polled_state_timestamp is not None
            and state.timestamp <= self._last_polled_state_timestamp
        ):
            self._set_refresh_interval(self.IDLE_REFRESH_INTERVAL_MS)
        else:
            self._set_refresh_interval(self.REFRESH_INTERVAL_MS)
        self._last_polled_state_timestamp = state.timestamp

        self._show_message("", is_error=False)
        self._apply_summary(state)
        self._apply_alerts(state)
        self._record_live_labels(state)
        self._load_history(state)
        self._refresh_graph_controls()
        self._refresh_plots()

    def _set_refresh_interval(self, interval_ms: int) -> None:
        """Set timer cadence only when needed to avoid unnecessary churn."""
        if self._refresh_timer.interval() != interval_ms:
            self._refresh_timer.setInterval(interval_ms)

    def start_service(self) -> None:
        """Request startup of the configured service/task."""
        success, message = self._service_action_runner("start")
        self.refresh_data()
        self._show_message(message, is_error=not success)

    def _apply_theme(self) -> None:
        self.setStyleSheet(dashboard_page_stylesheet(self.palette()))
        self._style_status_widgets()
        self._apply_plot_theme(self.temperature_plot)
        self._apply_plot_theme(self.fan_rpm_plot)
        self._apply_plot_theme(self.fan_target_plot)

    def _style_status_widgets(self) -> None:
        palette = self.palette()
        self.alerts_button.setStyleSheet(
            badge_stylesheet(self._alerts_badge_tone, palette)
        )
        daemon_colors = {
            "success": "#22c55e",
            "warning": "#f59e0b",
            "critical": "#ef4444",
            "neutral": palette.color(palette.ColorRole.Text).name(),
        }
        self.daemon_indicator.setStyleSheet(
            "font-size: 14px; font-weight: 900; "
            f"color: {daemon_colors.get(self._daemon_indicator_tone, daemon_colors['neutral'])};"
        )

    def _apply_offline_state(self, service_status) -> None:
        installed = bool(getattr(service_status, "task_installed", False))
        self._daemon_indicator_tone = "warning" if installed else "critical"
        self.daemon_indicator.setToolTip("Daemon is not running")
        self._active_config = None
        self._last_state_timestamp = None
        self._temperature_history.clear()
        self._fan_rpm_history.clear()
        self._fan_target_history.clear()
        self._rebuild_fan_summary_cards(None, None)
        self._apply_alert_menu([])
        self._refresh_graph_controls()
        self._style_status_widgets()
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
        self._refresh_plots()

    def _apply_summary(self, state: DaemonStateFile) -> None:
        active_config = self._load_active_config(state)
        self._active_config = active_config

        self._daemon_indicator_tone = "critical" if state.config_error else "success"
        self.daemon_indicator.setToolTip(
            "Daemon connected" if not state.config_error else state.config_error
        )
        self._rebuild_fan_summary_cards(state, active_config)
        self._style_status_widgets()

    def _apply_alerts(self, state: DaemonStateFile) -> None:
        labels = [
            f"{alert.sensor_id} [{alert.alert_type}] - {alert.message}"
            for alert in reversed(state.recent_alerts[-10:])
        ]
        self._apply_alert_menu(labels)

    def _apply_alert_menu(self, alert_lines: list[str]) -> None:
        self._recent_alerts = alert_lines
        self.alerts_menu.clear()
        if not alert_lines:
            empty_action = QAction("No recent alerts", self.alerts_menu)
            empty_action.setEnabled(False)
            self.alerts_menu.addAction(empty_action)
            self._alerts_badge_tone = "neutral"
            self.alerts_button.setText("⚠ 0")
            self.alerts_button.setToolTip("No recent alerts")
            self._style_status_widgets()
            return

        for line in alert_lines:
            action = QAction(line, self.alerts_menu)
            action.setEnabled(False)
            self.alerts_menu.addAction(action)

        self._alerts_badge_tone = "critical"
        self.alerts_button.setText(f"⚠ {len(alert_lines)}")
        self.alerts_button.setToolTip("Recent alerts")
        self._style_status_widgets()

    def _record_live_labels(self, state: DaemonStateFile) -> None:
        self._fan_groups.clear()
        self._target_groups.clear()
        for sensor in state.temperatures:
            if not self._is_relevant_temperature(sensor):
                continue
            self._temperature_labels[sensor.identifier] = (
                f"{sensor.hardware_name} / {sensor.sensor_name}"
            )

        for fan in state.fan_speeds:
            group_name, fan_config = self._resolve_live_fan_config(fan)
            if group_name is None:
                continue
            label = self._series_display_name(group_name, fan_config, fan)
            series_id = fan.control_identifier or fan.identifier
            self._fan_labels[series_id] = label
            self._fan_groups[series_id] = group_name
            self._target_labels[series_id] = label
            self._target_groups[series_id] = group_name

        if self._active_config is not None:
            for group_name, fan_config in sorted(self._active_config.fans.items()):
                label = self._series_display_name(group_name, fan_config, None)
                self._target_labels[fan_config.fan_id] = label
                self._target_groups[fan_config.fan_id] = group_name

        self._prune_unmapped_fan_history()

    def _load_history(self, state: DaemonStateFile) -> None:
        samples = read_daemon_history(self._history_path)
        if not samples:
            samples = [self._build_fallback_history_sample(state)]

        self._temperature_history.clear()
        self._fan_rpm_history.clear()
        self._fan_target_history.clear()

        latest_timestamp = state.timestamp
        for sample in samples:
            latest_timestamp = max(latest_timestamp, sample.timestamp)
            for sensor_id, value in sample.temperatures.items():
                self._temperature_history[sensor_id].append((sample.timestamp, value))
            for series_id, value in sample.fan_rpm.items():
                self._fan_rpm_history[series_id].append((sample.timestamp, value))
            for series_id, value in sample.fan_targets.items():
                self._fan_target_history[series_id].append((sample.timestamp, value))

        self._last_state_timestamp = latest_timestamp
        self._prune_unmapped_fan_history()
        self._trim_history(latest_timestamp)

    def _build_fallback_history_sample(self, state: DaemonStateFile) -> HistorySample:
        temperatures = {
            sensor.identifier: float(sensor.value)
            for sensor in state.temperatures
            if sensor.value is not None and self._is_relevant_temperature(sensor)
        }
        fan_rpm = {
            (fan.control_identifier or fan.identifier): float(fan.rpm)
            for fan in state.fan_speeds
            if fan.rpm is not None
        }
        fan_targets = {
            identifier: float(value) for identifier, value in state.fan_targets.items()
        }
        return HistorySample(
            timestamp=state.timestamp,
            temperatures=temperatures,
            fan_rpm=fan_rpm,
            fan_targets=fan_targets,
        )

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

    def _create_plot_widget(
        self,
        graph_key: str,
        title: str,
        x_label: str,
        y_label: str,
    ) -> QWidget:
        if pg is None:
            fallback = QLabel(
                f"Install pyqtgraph to enable the {title.lower()} graph.",
                self,
            )
            fallback.setWordWrap(True)
            return self._wrap_widget(title, fallback)

        plot_widget = DashboardPlotWidget(
            self,
            axisItems={"bottom": ElapsedSecondsAxis(orientation="bottom")},
        )
        plot_widget.setLabel("bottom", "")
        plot_widget.setLabel("left", y_label)
        plot_widget.showGrid(x=True, y=True, alpha=0.25)
        plot_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._apply_plot_theme(plot_widget)

        plot_group = QGroupBox(title, self.right_panel)
        plot_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        group_layout = QVBoxLayout(plot_group)
        group_layout.setContentsMargins(12, 12, 12, 12)
        group_layout.setSpacing(6)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        legend_label = QLabel("Visible: none", plot_group)
        legend_label.setObjectName(f"{graph_key}LegendLabel")
        legend_label.setProperty("sectionRole", "subtitle")
        legend_label.setWordWrap(True)
        legend_label.setTextFormat(Qt.TextFormat.RichText)
        controls_row.addWidget(legend_label, 1)

        series_button = QToolButton(plot_group)
        series_button.setObjectName(f"{graph_key}SeriesButton")
        series_button.setProperty("graphControl", "selector")
        series_button.setText("Show Lines")
        series_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        series_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        series_menu = QMenu(series_button)
        series_button.setMenu(series_menu)
        series_menu.aboutToHide.connect(self._refresh_graph_controls)
        controls_row.addWidget(series_button)
        group_layout.addLayout(controls_row)

        group_layout.addWidget(plot_widget, 1)

        self._graph_controls[graph_key] = {
            "group": plot_group,
            "menu": series_menu,
            "button": series_button,
            "legend": legend_label,
        }
        return plot_group

    def _apply_plot_theme(self, plot_container: QWidget) -> None:
        if pg is None:
            return

        plot_widget = self._extract_plot_widget(plot_container)
        if plot_widget is None:
            return

        colors = plot_theme(self.palette())
        plot_widget.setBackground(colors["background"])
        plot_item = plot_widget.getPlotItem()
        plot_item.getAxis("left").setTextPen(colors["foreground"])
        plot_item.getAxis("bottom").setTextPen(colors["foreground"])
        plot_item.getAxis("left").setPen(colors["muted"])
        plot_item.getAxis("bottom").setPen(colors["muted"])
        plot_item.getAxis("top").setPen(colors["muted"])
        plot_item.getAxis("right").setPen(colors["muted"])
        plot_item.getAxis("bottom").setHeight(28)
        plot_item.getAxis("left").setWidth(52)
        plot_item.showGrid(x=True, y=True, alpha=0.25)

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
        plot_widget = self._extract_plot_widget(plot_container)
        if pg is None or plot_widget is None:
            return

        self._apply_plot_theme(plot_container)
        plot_item = plot_widget.getPlotItem()
        plot_item.clear()
        graph_key = self._graph_key_for_plot(plot_container)
        filtered_history = self._filtered_history_map(graph_key, history_map)
        if not filtered_history:
            self._set_plot_legend(graph_key, [])
            return

        latest_timestamp = max(
            series[-1][0] for series in filtered_history.values() if series
        )
        colors = plot_theme(self.palette())
        series_colors = colors["series"]
        legend_items: list[tuple[str, str]] = []
        for index, (sensor_id, series) in enumerate(sorted(filtered_history.items())):
            if not series:
                continue
            xs = [point[0] - latest_timestamp for point in series]
            ys = [point[1] for point in series]
            color = series_colors[index % len(series_colors)]
            label = labels.get(sensor_id, sensor_id)
            plot_widget.plot(
                xs,
                ys,
                pen=pg.mkPen(color=color, width=2.5),
                name=label,
                antialias=True,
            )
            legend_items.append((color, label))

        self._set_plot_legend(graph_key, legend_items)

    def _refresh_graph_controls(self) -> None:
        catalogs = {
            "temperature": self._build_temperature_catalog(),
            "fan_rpm": self._build_grouped_catalog(
                self._fan_rpm_history,
                self._fan_labels,
                self._fan_groups,
                singular_prefix="Fan",
            ),
            "fan_target": self._build_grouped_catalog(
                self._fan_target_history,
                self._target_labels,
                self._target_groups,
                singular_prefix="Target",
            ),
        }
        for graph_key, catalog in catalogs.items():
            self._sync_graph_selection(graph_key, catalog)
            self._populate_graph_menu(graph_key, catalog)

    def _build_temperature_catalog(self) -> dict[str, str]:
        return {
            sensor_id: self._temperature_labels.get(sensor_id, sensor_id)
            for sensor_id, series in sorted(self._temperature_history.items())
            if series
        }

    def _build_grouped_catalog(
        self,
        history_map: dict[str, deque[tuple[float, float]]],
        labels: dict[str, str],
        group_map: dict[str, str],
        *,
        singular_prefix: str,
    ) -> dict[str, str]:
        catalog: dict[str, str] = {}
        groups = sorted({group for group in group_map.values() if group})
        for group in groups:
            catalog[f"group::{group}"] = self._display_group_name(group)
        for series_id, series in sorted(history_map.items()):
            if not series:
                continue
            catalog[f"series::{series_id}"] = (
                f"{singular_prefix} · {labels.get(series_id, series_id)}"
            )
        return catalog

    def _sync_graph_selection(
        self,
        graph_key: str,
        catalog: dict[str, str],
    ) -> None:
        if not catalog:
            self._graph_enabled_series[graph_key] = set()
            return

        enabled = self._graph_enabled_series[graph_key]
        if graph_key not in self._graph_defaults_initialized:
            self._graph_enabled_series[graph_key] = self._default_graph_selection(
                graph_key,
                catalog,
            )
            self._graph_defaults_initialized.add(graph_key)
            return

        available = set(catalog)
        filtered = {series_id for series_id in enabled if series_id in available}
        if enabled and not filtered and catalog:
            filtered = self._default_graph_selection(graph_key, catalog)
        self._graph_enabled_series[graph_key] = filtered

    def _default_graph_selection(
        self,
        graph_key: str,
        catalog: dict[str, str],
    ) -> set[str]:
        if not catalog:
            return set()

        if graph_key == "temperature":
            controlled_ids = []
            if self._active_config is not None:
                for fan in self._active_config.fans.values():
                    controlled_ids.extend(fan.temp_ids)
            defaults = [
                sensor_id for sensor_id in controlled_ids if sensor_id in catalog
            ]
            return set(defaults or list(catalog)[:3])

        group_defaults = [
            series_id for series_id in catalog if series_id.startswith("group::")
        ]
        return set(group_defaults or list(catalog)[:1])

    def _populate_graph_menu(
        self,
        graph_key: str,
        catalog: dict[str, str],
    ) -> None:
        controls = self._graph_controls.get(graph_key)
        if not controls:
            return
        menu = controls["menu"]
        button = controls["button"]
        if not isinstance(menu, QMenu) or not isinstance(button, QToolButton):
            return

        if menu.isVisible():
            return
        menu.clear()
        if not catalog:
            empty_action = QAction("No series available", menu)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
            button.setText("Show Lines")
            button.setToolTip("No series available")
            return

        enabled_count = 0
        for series_id, label in catalog.items():
            action = QAction(label, menu)
            action.setCheckable(True)
            checked = series_id in self._graph_enabled_series[graph_key]
            action.setChecked(checked)
            if checked:
                enabled_count += 1
            action.toggled.connect(
                lambda checked, g=graph_key, s=series_id: self._toggle_graph_series(
                    g,
                    s,
                    checked,
                )
            )
            menu.addAction(action)

        button.setText("Show Lines")
        button.setToolTip(f"Shown lines: {enabled_count}")

    def _toggle_graph_series(
        self,
        graph_key: str,
        series_id: str,
        checked: bool,
    ) -> None:
        enabled = self._graph_enabled_series[graph_key]
        if checked:
            enabled.add(series_id)
        else:
            enabled.discard(series_id)
        self._refresh_graph_controls()
        self._refresh_plots()

    def _filtered_history_map(
        self,
        graph_key: str,
        history_map: dict[str, deque[tuple[float, float]]],
    ) -> dict[str, list[tuple[float, float]]]:
        enabled = self._graph_enabled_series.get(graph_key, set())
        if not enabled:
            return {}

        if graph_key == "temperature":
            return {
                sensor_id: list(series)
                for sensor_id, series in history_map.items()
                if sensor_id in enabled and series
            }

        group_map = self._fan_groups if graph_key == "fan_rpm" else self._target_groups
        labels = self._fan_labels if graph_key == "fan_rpm" else self._target_labels
        grouped_history = self._build_grouped_history(history_map, group_map)
        filtered: dict[str, list[tuple[float, float]]] = {}
        for series_id in enabled:
            if series_id.startswith("group::"):
                group = series_id.split("::", 1)[1]
                if group in grouped_history:
                    filtered[series_id] = grouped_history[group]
                    display_group = self._display_group_name(group)
                    if graph_key == "fan_rpm":
                        self._fan_labels[series_id] = display_group
                    else:
                        self._target_labels[series_id] = display_group
                continue

            raw_id = series_id.split("::", 1)[1] if "::" in series_id else series_id
            series = history_map.get(raw_id)
            if series:
                filtered[series_id] = list(series)
                if graph_key == "fan_rpm":
                    self._fan_labels[series_id] = labels.get(raw_id, raw_id)
                else:
                    self._target_labels[series_id] = labels.get(raw_id, raw_id)
        return filtered

    def _prune_unmapped_fan_history(self) -> None:
        mapped_fan_ids = set(self._fan_groups)
        mapped_target_ids = set(self._target_groups)
        for history_map, mapped_ids in (
            (self._fan_rpm_history, mapped_fan_ids),
            (self._fan_target_history, mapped_target_ids),
        ):
            for series_id in list(history_map.keys()):
                if series_id not in mapped_ids:
                    del history_map[series_id]

    def _build_grouped_history(
        self,
        history_map: dict[str, deque[tuple[float, float]]],
        group_map: dict[str, str],
    ) -> dict[str, list[tuple[float, float]]]:
        grouped_points: dict[str, dict[float, list[float]]] = defaultdict(dict)
        for series_id, series in history_map.items():
            group = group_map.get(series_id)
            if not group:
                continue
            bucket = grouped_points.setdefault(group, {})
            for timestamp, value in series:
                bucket.setdefault(timestamp, []).append(value)

        return {
            group: [
                (timestamp, sum(values) / len(values))
                for timestamp, values in sorted(points.items())
            ]
            for group, points in grouped_points.items()
        }

    def _graph_key_for_plot(self, plot_container: QWidget) -> str:
        for graph_key, controls in self._graph_controls.items():
            if controls.get("group") is plot_container:
                return graph_key
        return ""

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

    def _sensor_count(self, active_config: Config | None) -> int:
        if active_config is None:
            return 0
        sensor_ids = {
            sensor_id
            for fan in active_config.fans.values()
            for sensor_id in fan.temp_ids
        }
        return len(sensor_ids)

    def _build_profile_mapping_summary(
        self,
        state: DaemonStateFile,
        active_config: Config | None,
    ) -> str:
        if active_config is None or not active_config.fans:
            return "No mapped fans are available in the active config."

        lines: list[str] = []
        for fan_name, fan_config in list(sorted(active_config.fans.items()))[:4]:
            fan_label = self._friendly_fan_name(fan_name, fan_config, state)
            sensors = ", ".join(self._resolve_sensor_labels(state, fan_config.temp_ids))
            lines.append(f"{fan_label} → {sensors} ({fan_config.curve})")
        if len(active_config.fans) > 4:
            lines.append(f"+ {len(active_config.fans) - 4} more mappings")
        return "\n".join(lines)

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
        for index, group in enumerate(self._group_fan_configs(state, active_config)):
            card = self._create_fan_group_card(state, group)
            self._fan_summary_cards.append(card)
            self.fan_summary_layout.addWidget(card, index, 0)

    def _create_fan_group_card(
        self,
        state: DaemonStateFile,
        group: tuple[str, list[tuple[str, FanConfig, object | None]]],
    ) -> QFrame:
        group_name, members = group
        card = QFrame(self.fan_summary_group)
        card.setObjectName(f"{self._object_name_token(group_name)}GroupCard")
        card.setProperty("cardRole", "fan-summary")
        card.setMinimumHeight(178)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)

        title_label = QLabel(self._display_group_name(group_name), card)
        title_label.setObjectName("fanGroupTitleLabel")
        title_label.setProperty("cardTextRole", "title")
        header.addWidget(title_label)
        header.addStretch(1)

        target_values = [
            target
            for _, fan_config, _ in members
            for target in [state.fan_targets.get(fan_config.fan_id)]
            if target is not None
        ]
        curve_badge = QLabel(self._group_curve_badge_text(members), card)
        curve_badge.setObjectName("fanGroupCurveBadgeLabel")
        curve_badge.setStyleSheet(badge_stylesheet("info", self.palette()))
        header.addWidget(curve_badge)
        layout.addLayout(header)

        subtitle_text = self._group_subtitle_text(state, members)
        if subtitle_text:
            fans_label = QLabel(subtitle_text, card)
            fans_label.setObjectName("fanGroupMembersLabel")
            fans_label.setProperty("cardTextRole", "muted")
            fans_label.setWordWrap(True)
            layout.addWidget(fans_label)

        actual_values = [
            float(live_fan.current_control_pct)
            for _, _, live_fan in members
            if live_fan is not None
            and getattr(live_fan, "current_control_pct", None) is not None
        ]
        rpm_values = [
            float(live_fan.rpm)
            for _, _, live_fan in members
            if live_fan is not None and getattr(live_fan, "rpm", None) is not None
        ]

        metrics_layout = QGridLayout()
        metrics_layout.setHorizontalSpacing(10)
        metrics_layout.setVerticalSpacing(10)
        metrics_layout.addWidget(
            self._create_metric_card(
                card,
                "Target",
                self._format_percent_metric(target_values),
                "fanGroupTargetValueLabel",
            ),
            0,
            0,
        )
        metrics_layout.addWidget(
            self._create_metric_card(
                card,
                "Actual",
                self._format_percent_metric(actual_values, digits=1),
                "fanGroupActualValueLabel",
            ),
            0,
            1,
        )
        metrics_layout.addWidget(
            self._create_metric_card(
                card,
                "RPM",
                self._format_rpm_metric(rpm_values),
                "fanGroupRpmValueLabel",
            ),
            0,
            2,
        )
        layout.addLayout(metrics_layout)

        sensors_caption = QLabel("Controlling sensors", card)
        sensors_caption.setProperty("cardTextRole", "eyebrow")
        layout.addWidget(sensors_caption)

        sensors_label = QLabel(self._group_sensor_text(state, members), card)
        sensors_label.setObjectName("fanGroupSensorsLabel")
        sensors_label.setProperty("cardTextRole", "body")
        sensors_label.setWordWrap(True)
        layout.addWidget(sensors_label)
        return card

    def _group_fan_configs(
        self,
        state: DaemonStateFile,
        active_config: Config,
    ) -> list[tuple[str, list[tuple[str, FanConfig, object | None]]]]:
        return [
            (
                fan_name,
                [(fan_name, fan_config, self._find_live_fan_state(state, fan_config))],
            )
            for fan_name, fan_config in sorted(active_config.fans.items())
        ]

    def _group_subtitle_text(
        self,
        state: DaemonStateFile,
        members: list[tuple[str, FanConfig, object | None]],
    ) -> str:
        labels: list[str] = []
        for fan_name, fan_config, _ in members:
            label = self._friendly_fan_name(fan_name, fan_config, state)
            if label != fan_name:
                labels.append(label)
        if not labels:
            return "Mapped control: direct"
        prefix = "Mapped control" if len(labels) == 1 else "Mapped controls"
        return f"{prefix}: {'; '.join(labels)}"

    def _group_sensor_text(
        self,
        state: DaemonStateFile,
        members: list[tuple[str, FanConfig, object | None]],
    ) -> str:
        sensor_details: list[str] = []
        seen: set[str] = set()
        for _, fan_config, _ in members:
            for detail in self._resolve_sensor_details(state, fan_config.temp_ids):
                if detail not in seen:
                    seen.add(detail)
                    sensor_details.append(detail)
        return "  •  ".join(sensor_details or ["No sensors configured"])

    def _group_curve_text(
        self,
        members: list[tuple[str, FanConfig, object | None]],
    ) -> str:
        curves = sorted({fan_config.curve for _, fan_config, _ in members})
        return "Curve: " + ", ".join(curves or ["None"])

    def _group_curve_badge_text(
        self,
        members: list[tuple[str, FanConfig, object | None]],
    ) -> str:
        curves = sorted({fan_config.curve for _, fan_config, _ in members})
        if not curves:
            return "No curve"
        if len(curves) == 1:
            return curves[0]
        return f"{len(curves)} curves"

    @staticmethod
    def _target_summary_text(target_values: list[float], fan_count: int) -> str:
        if not target_values:
            return "Awaiting targets"
        if len(target_values) == 1:
            return f"1 target • {target_values[0]:.0f}%"
        return f"{fan_count} fans • {min(target_values):.0f}–{max(target_values):.0f}%"

    @staticmethod
    def _target_detail_text(target_values: list[float]) -> str:
        if not target_values:
            return "No live target"
        if len(target_values) == 1:
            return f"{target_values[0]:.1f}%"
        return f"{sum(target_values) / len(target_values):.1f}% avg"

    def _resolve_live_fan_config(
        self,
        live_fan,
    ) -> tuple[str | None, FanConfig | None]:
        if self._active_config is None:
            return None, None

        candidate_ids = self._candidate_fan_ids(live_fan)

        for fan_name, fan_config in sorted(self._active_config.fans.items()):
            if fan_config.fan_id in candidate_ids:
                return fan_name, fan_config

        return None, None

    def _series_display_name(
        self,
        group_name: str,
        fan_config: FanConfig | None,
        live_fan,
    ) -> str:
        group_label = self._display_group_name(group_name)
        detail = ""
        if fan_config is not None and fan_config.header_name:
            detail = fan_config.header_name
        elif getattr(live_fan, "sensor_name", None):
            detail = str(live_fan.sensor_name)
        elif getattr(live_fan, "hardware_name", None):
            detail = str(live_fan.hardware_name)
        if detail:
            if detail.strip().lower() == group_label.strip().lower():
                return group_label
            return f"{group_label} · {detail}"
        return group_label

    def _create_metric_card(
        self,
        parent: QWidget,
        title: str,
        value: str,
        value_object_name: str,
    ) -> QFrame:
        frame = QFrame(parent)
        frame.setProperty("cardRole", "fan-metric")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title_label = QLabel(title, frame)
        title_label.setProperty("cardTextRole", "metricTitle")
        layout.addWidget(title_label)

        value_label = QLabel(value, frame)
        value_label.setObjectName(value_object_name)
        value_label.setProperty("cardTextRole", "metricValue")
        layout.addWidget(value_label)
        return frame

    @staticmethod
    def _format_percent_metric(values: list[float], *, digits: int = 0) -> str:
        if not values:
            return "—"
        if len(values) == 1:
            return f"{values[0]:.{digits}f}%"
        return f"{min(values):.{digits}f}–{max(values):.{digits}f}%"

    @staticmethod
    def _format_rpm_metric(values: list[float]) -> str:
        if not values:
            return "—"
        if len(values) == 1:
            return f"{values[0]:.0f} RPM"
        return f"{min(values):.0f}–{max(values):.0f} RPM"

    def _set_plot_legend(
        self,
        graph_key: str,
        items: list[tuple[str, str]],
    ) -> None:
        controls = self._graph_controls.get(graph_key)
        if not controls:
            return
        legend_label = controls.get("legend")
        if not isinstance(legend_label, QLabel):
            return
        if not items:
            legend_label.setText("Visible: none")
            return

        rendered = " &nbsp; ".join(
            f'<span style="color: {color}; font-weight: 800;">●</span> {label}'
            for color, label in items
        )
        legend_label.setText(f"Visible: {rendered}")

    def _find_live_fan_state(self, state: DaemonStateFile, fan_config: FanConfig):
        for fan in state.fan_speeds:
            if fan_config.fan_id in self._candidate_fan_ids(fan):
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

    @staticmethod
    def _candidate_fan_ids(live_fan) -> set[str]:
        candidates = {
            value
            for value in (
                getattr(live_fan, "control_identifier", None),
                getattr(live_fan, "identifier", None),
            )
            if isinstance(value, str) and value
        }
        identifier = getattr(live_fan, "identifier", None)
        if isinstance(identifier, str) and "/fan/" in identifier:
            candidates.add(identifier.replace("/fan/", "/control/"))
        if isinstance(identifier, str) and "/control/" in identifier:
            candidates.add(identifier.replace("/control/", "/fan/"))
        return candidates

    @staticmethod
    def _display_group_name(group_name: str) -> str:
        acronyms = {"cpu", "gpu", "ram", "aio", "vrm"}
        parts = [part for part in group_name.replace("-", "_").split("_") if part]
        if not parts:
            return group_name
        rendered: list[str] = []
        for part in parts:
            lowered = part.lower()
            if lowered in acronyms:
                rendered.append(lowered.upper())
                continue
            rendered.append(part.capitalize())
        return " ".join(rendered)

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

    def _resolve_sensor_details(
        self,
        state: DaemonStateFile,
        sensor_ids: list[str],
    ) -> list[str]:
        by_id = {sensor.identifier: sensor for sensor in state.temperatures}
        resolved: list[str] = []
        for sensor_id in sensor_ids:
            sensor = by_id.get(sensor_id)
            label = self._compact_identifier(sensor_id)
            if sensor is not None:
                label = f"{sensor.hardware_name} / {sensor.sensor_name}"
                if sensor.value is not None:
                    label = f"{label} · {sensor.value:.1f}°C"
            resolved.append(label)
        return resolved or ["No sensors configured"]

    @staticmethod
    def _object_name_token(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip()
        if not cleaned:
            return "fanGroup"
        parts = cleaned.split()
        return parts[0].lower() + "".join(part.title() for part in parts[1:])

    @staticmethod
    def _is_relevant_temperature(sensor) -> bool:
        combined = (
            f"{sensor.hardware_name} {sensor.sensor_name} {sensor.identifier}"
        ).lower()
        blocked_terms = ("alarm", "limit")
        return not any(term in combined for term in blocked_terms)

    @staticmethod
    def _compact_identifier(identifier: str) -> str:
        trimmed = identifier.strip("/")
        if not trimmed:
            return identifier
        parts = trimmed.split("/")
        return " / ".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

    @staticmethod
    def _wrap_widget(title: str, widget: QWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(widget)
        return group

    @staticmethod
    def _extract_plot_widget(widget: QWidget) -> DashboardPlotWidget | None:
        if isinstance(widget, DashboardPlotWidget):
            return widget
        if widget.layout() is None or widget.layout().count() == 0:
            return None
        for index in range(widget.layout().count()):
            child = widget.layout().itemAt(index).widget()
            if isinstance(child, DashboardPlotWidget):
                return child
        return None

    def _show_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.message_label.clear()
            self.message_label.hide()
            return

        self.message_label.setStyleSheet(
            message_stylesheet(is_error=is_error, palette=self.palette())
        )
        self.message_label.setText(message)
        self.message_label.show()
