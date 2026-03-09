"""Dashboard page for the PySide6 desktop GUI."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
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

from pysysfan.gui.desktop.local_backend import read_daemon_state, run_service_command
from pysysfan.platforms import windows_service
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
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._state_path = Path(state_path)
        self._service_action_runner = service_action_runner or run_service_command
        self._service_status_getter = (
            service_status_getter or windows_service.get_service_status
        )
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Dashboard", self)
        heading.setObjectName("dashboardTitle")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(heading)

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

        summary_group = QGroupBox("Daemon Summary", self)
        summary_layout = QGridLayout(summary_group)
        summary_layout.setHorizontalSpacing(24)
        summary_layout.setVerticalSpacing(8)

        self.active_profile_label = QLabel("Active profile: N/A", self)
        self.uptime_label = QLabel("Uptime: N/A", self)
        self.poll_interval_label = QLabel("Poll interval: N/A", self)
        self.fans_configured_label = QLabel("Configured fans: N/A", self)
        self.curves_configured_label = QLabel("Configured curves: N/A", self)
        self.config_path_label = QLabel("Config path: N/A", self)
        self.config_path_label.setWordWrap(True)
        self.config_error_label = QLabel("Config error: none", self)
        self.config_error_label.setWordWrap(True)

        summary_layout.addWidget(self.active_profile_label, 0, 0)
        summary_layout.addWidget(self.uptime_label, 0, 1)
        summary_layout.addWidget(self.poll_interval_label, 1, 0)
        summary_layout.addWidget(self.fans_configured_label, 1, 1)
        summary_layout.addWidget(self.curves_configured_label, 2, 0)
        summary_layout.addWidget(self.config_path_label, 2, 1)
        summary_layout.addWidget(self.config_error_label, 3, 0, 1, 2)
        layout.addWidget(summary_group)

        tables_layout = QHBoxLayout()
        tables_layout.setSpacing(16)

        self.temperatures_table = QTableWidget(0, 3, self)
        self.temperatures_table.setObjectName("temperaturesTable")
        self.temperatures_table.setHorizontalHeaderLabels(
            ["Hardware", "Sensor", "Value"]
        )
        self.temperatures_table.horizontalHeader().setStretchLastSection(True)
        temps_group = self._wrap_widget("Temperatures", self.temperatures_table)
        tables_layout.addWidget(temps_group, 2)

        self.fans_table = QTableWidget(0, 5, self)
        self.fans_table.setObjectName("fansTable")
        self.fans_table.setHorizontalHeaderLabels(
            ["Hardware", "Fan", "RPM", "Actual PWM", "Target PWM"]
        )
        self.fans_table.horizontalHeader().setStretchLastSection(True)
        fans_group = self._wrap_widget("Fans", self.fans_table)
        tables_layout.addWidget(fans_group, 3)

        self.alerts_list = QListWidget(self)
        self.alerts_list.setObjectName("alertsList")
        alerts_group = self._wrap_widget("Recent Alerts", self.alerts_list)
        tables_layout.addWidget(alerts_group, 2)

        layout.addLayout(tables_layout)

        plots_layout = QGridLayout()
        plots_layout.setHorizontalSpacing(16)
        plots_layout.setVerticalSpacing(16)

        self.temperature_plot = self._create_plot_widget(
            "Temperatures", "Seconds", "°C"
        )
        self.fan_rpm_plot = self._create_plot_widget("Fan RPM", "Seconds", "RPM")
        self.fan_target_plot = self._create_plot_widget("Target PWM", "Seconds", "%")

        plots_layout.addWidget(self.temperature_plot, 0, 0)
        plots_layout.addWidget(self.fan_rpm_plot, 0, 1)
        plots_layout.addWidget(self.fan_target_plot, 1, 0, 1, 2)
        layout.addLayout(plots_layout)
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

        self.active_profile_label.setText("Active profile: N/A")
        self.uptime_label.setText("Uptime: N/A")
        self.poll_interval_label.setText("Poll interval: N/A")
        self.fans_configured_label.setText("Configured fans: N/A")
        self.curves_configured_label.setText("Configured curves: N/A")
        self.config_path_label.setText("Config path: N/A")
        self.config_error_label.setText("Config error: N/A")
        self.temperatures_table.setRowCount(0)
        self.fans_table.setRowCount(0)
        self.alerts_list.clear()
        self.alerts_list.addItem("No daemon state available")
        self._refresh_plots()

    def _apply_summary(self, state: DaemonStateFile) -> None:
        self.active_profile_label.setText(f"Active profile: {state.active_profile}")
        self.uptime_label.setText(f"Uptime: {state.uptime_seconds:.1f}s")
        self.poll_interval_label.setText(f"Poll interval: {state.poll_interval:.1f}s")
        self.fans_configured_label.setText(f"Configured fans: {state.fans_configured}")
        self.curves_configured_label.setText(
            f"Configured curves: {state.curves_configured}"
        )
        self.config_path_label.setText(f"Config path: {state.config_path}")
        if state.config_error:
            self.config_error_label.setText(f"Config error: {state.config_error}")
        else:
            self.config_error_label.setText("Config error: none")

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

        color = "#b00020" if is_error else "#1d6f42"
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(message)
        self.message_label.show()
