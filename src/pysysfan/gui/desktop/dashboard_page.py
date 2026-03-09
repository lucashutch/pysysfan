"""Dashboard page for the PySide6 desktop GUI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pysysfan.api.client import PySysFanClient


class SensorStreamWorker(QThread):
    """Background worker for daemon sensor streaming."""

    sensors_received = Signal(dict)
    stream_failed = Signal(str)
    stream_finished = Signal()

    def __init__(self, client: PySysFanClient):
        super().__init__()
        self._client = client

    def run(self) -> None:
        try:
            for payload in self._client.stream_sensors():
                if self.isInterruptionRequested():
                    return
                self.sensors_received.emit(payload)
            # Signal that the generator completed naturally so the UI can
            # transition back to the stopped state deterministically.
            self.stream_finished.emit()
        except Exception as exc:
            self.stream_failed.emit(str(exc))


class DashboardPage(QWidget):
    """Desktop dashboard backed by the Python API client."""

    def __init__(
        self,
        client_factory: Callable[[], PySysFanClient]
        | type[PySysFanClient]
        | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        # Handle both factory function and class reference
        if isinstance(client_factory, type):
            self._client_factory = client_factory
        else:
            self._client_factory = client_factory or PySysFanClient
        self._client: PySysFanClient | None = None
        self._stream_worker: SensorStreamWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Dashboard", self)
        heading.setObjectName("dashboardTitle")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(heading)

        control_row = QHBoxLayout()
        control_row.setSpacing(12)

        self.connection_label = QLabel("Connection: Disconnected", self)
        self.connection_label.setObjectName("connectionLabel")
        control_row.addWidget(self.connection_label)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.refresh_data)
        control_row.addWidget(self.refresh_button)

        self.live_updates_button = QPushButton("Start Live Updates", self)
        self.live_updates_button.setObjectName("liveUpdatesButton")
        self.live_updates_button.clicked.connect(self.toggle_live_updates)
        control_row.addWidget(self.live_updates_button)

        control_row.addStretch(1)
        layout.addLayout(control_row)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        summary_layout = QGridLayout()
        summary_layout.setHorizontalSpacing(24)
        summary_layout.setVerticalSpacing(8)

        self.active_profile_label = QLabel("Active profile: N/A", self)
        self.active_profile_label.setObjectName("activeProfileLabel")
        summary_layout.addWidget(self.active_profile_label, 0, 0)

        self.uptime_label = QLabel("Uptime: N/A", self)
        self.uptime_label.setObjectName("uptimeLabel")
        summary_layout.addWidget(self.uptime_label, 0, 1)

        self.poll_interval_label = QLabel("Poll interval: N/A", self)
        self.poll_interval_label.setObjectName("pollIntervalLabel")
        summary_layout.addWidget(self.poll_interval_label, 1, 0)

        self.fans_configured_label = QLabel("Configured fans: N/A", self)
        self.fans_configured_label.setObjectName("fansConfiguredLabel")
        summary_layout.addWidget(self.fans_configured_label, 1, 1)

        self.alert_rules_label = QLabel("Alert rules: N/A", self)
        self.alert_rules_label.setObjectName("alertRulesLabel")
        summary_layout.addWidget(self.alert_rules_label, 2, 0)

        self.alert_history_label = QLabel("Recent alerts: N/A", self)
        self.alert_history_label.setObjectName("alertHistoryLabel")
        summary_layout.addWidget(self.alert_history_label, 2, 1)

        layout.addLayout(summary_layout)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(12)

        profile_row.addWidget(QLabel("Available profiles", self))
        self.profile_selector = QComboBox(self)
        self.profile_selector.setObjectName("profileSelector")
        profile_row.addWidget(self.profile_selector)

        self.activate_profile_button = QPushButton("Activate Profile", self)
        self.activate_profile_button.setObjectName("activateProfileButton")
        self.activate_profile_button.clicked.connect(self.activate_selected_profile)
        profile_row.addWidget(self.activate_profile_button)

        self.clear_alert_history_button = QPushButton("Clear Alert History", self)
        self.clear_alert_history_button.setObjectName("clearAlertHistoryButton")
        self.clear_alert_history_button.clicked.connect(self.clear_alert_history)
        profile_row.addWidget(self.clear_alert_history_button)

        profile_row.addStretch(1)
        layout.addLayout(profile_row)

        sensor_layout = QHBoxLayout()
        sensor_layout.setSpacing(16)

        temps_column = QVBoxLayout()
        temps_heading = QLabel("Temperatures", self)
        temps_heading.setStyleSheet("font-weight: 600;")
        temps_column.addWidget(temps_heading)
        self.temperatures_list = QTableWidget(0, 2, self)
        self.temperatures_list.setObjectName("temperaturesList")
        self.temperatures_list.setHorizontalHeaderLabels(["Sensor", "Value"])
        self.temperatures_list.horizontalHeader().setStretchLastSection(False)
        temps_column.addWidget(self.temperatures_list)
        sensor_layout.addLayout(temps_column)

        fans_column = QVBoxLayout()
        fans_heading = QLabel("Fans", self)
        fans_heading.setStyleSheet("font-weight: 600;")
        fans_column.addWidget(fans_heading)
        self.fans_list = QTableWidget(0, 2, self)
        self.fans_list.setObjectName("fansList")
        self.fans_list.setHorizontalHeaderLabels(["Fan", "Speed"])
        self.fans_list.horizontalHeader().setStretchLastSection(False)
        fans_column.addWidget(self.fans_list)
        sensor_layout.addLayout(fans_column)

        alerts_column = QVBoxLayout()
        alerts_heading = QLabel("Recent Alerts", self)
        alerts_heading.setStyleSheet("font-weight: 600;")
        alerts_column.addWidget(alerts_heading)
        self.alerts_list = QListWidget(self)
        self.alerts_list.setObjectName("alertsList")
        alerts_column.addWidget(self.alerts_list)
        sensor_layout.addLayout(alerts_column)

        layout.addLayout(sensor_layout)
        layout.addStretch(1)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop streaming worker before closing."""
        self.stop_live_updates()
        super().closeEvent(event)

    def __del__(self) -> None:
        """Ensure worker is stopped on deletion."""
        self.stop_live_updates()

    def refresh_data(self) -> None:
        """Refresh the dashboard using the latest daemon snapshot and sensors."""
        try:
            client = self._get_client()
            status = client.get_status()
            sensors = client.get_sensors()
            profiles = client.list_profiles()
            alert_rules = client.list_alert_rules()
            alert_history = client.get_alert_history(5)
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_error(str(exc))
            return

        self.connection_label.setText("Connection: Connected")
        self._hide_error()
        self._apply_status(status)
        self._apply_sensor_payload(sensors)
        self._apply_profiles(profiles)
        self._apply_alerts(alert_rules, alert_history)

    def activate_selected_profile(self) -> None:
        """Activate the currently selected profile."""
        profile_name = self.profile_selector.currentText().strip()
        if not profile_name:
            self._show_error("Select a profile before activating it")
            return

        try:
            response = self._get_client().activate_profile(profile_name)
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_error(str(exc))
            return

        self.connection_label.setText("Connection: Connected")
        self.refresh_data()
        self._show_message(
            response.get("message", f"Switched to profile: {profile_name}")
        )

    def clear_alert_history(self) -> None:
        """Clear the alert history shown on the dashboard."""
        try:
            self._get_client().clear_alert_history()
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_error(str(exc))
            return

        self.connection_label.setText("Connection: Connected")
        self.refresh_data()
        self._show_message("Alert history cleared")

    def toggle_live_updates(self) -> None:
        """Start or stop live sensor updates."""
        if self._stream_worker and self._stream_worker.isRunning():
            self.stop_live_updates()
            return

        try:
            worker = SensorStreamWorker(self._get_client())
        except Exception as exc:
            self._show_error(str(exc))
            return

        worker.sensors_received.connect(self._handle_stream_payload)
        worker.stream_failed.connect(self._handle_stream_failure)
        worker.stream_finished.connect(self._handle_stream_finished)
        worker.finished.connect(self._handle_stream_finished)
        self._stream_worker = worker
        self.live_updates_button.setText("Stop Live Updates")
        worker.start()

    def stop_live_updates(self) -> None:
        """Stop the active sensor stream worker, if present."""
        if self._stream_worker is None:
            return

        self._stream_worker.requestInterruption()
        self._stream_worker.wait(1000)
        self._stream_worker = None
        self.live_updates_button.setText("Start Live Updates")

    def _get_client(self) -> PySysFanClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _apply_status(self, status: dict[str, Any]) -> None:
        self.active_profile_label.setText(
            f"Active profile: {status.get('active_profile', 'N/A')}"
        )
        uptime = status.get("uptime_seconds")
        uptime_text = f"{uptime:.1f}s" if isinstance(uptime, (int, float)) else "N/A"
        self.uptime_label.setText(f"Uptime: {uptime_text}")
        poll_interval = status.get("poll_interval")
        poll_text = (
            f"{poll_interval:.1f}s"
            if isinstance(poll_interval, (int, float))
            else "N/A"
        )
        self.poll_interval_label.setText(f"Poll interval: {poll_text}")
        self.fans_configured_label.setText(
            f"Configured fans: {status.get('fans_configured', 'N/A')}"
        )

    def _apply_profiles(self, profiles_payload: dict[str, Any]) -> None:
        profiles = profiles_payload.get("profiles", [])
        active = profiles_payload.get("active")
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        self.profile_selector.addItems(
            [profile.get("name", "") for profile in profiles if profile.get("name")]
        )
        self.profile_selector.blockSignals(False)
        if active:
            self.profile_selector.setCurrentText(active)
        self.activate_profile_button.setEnabled(self.profile_selector.count() > 0)

    def _apply_alerts(
        self,
        rules_payload: dict[str, Any],
        history_payload: dict[str, Any],
    ) -> None:
        rules = rules_payload.get("rules", [])
        alerts = history_payload.get("alerts", [])
        self.alert_rules_label.setText(f"Alert rules: {len(rules)}")
        self.alert_history_label.setText(f"Recent alerts: {len(alerts)}")
        self.alerts_list.clear()
        for alert in alerts:
            sensor_id = alert.get("sensor_id", "unknown")
            alert_type = alert.get("alert_type", "alert")
            value = alert.get("value", "N/A")
            self.alerts_list.addItem(f"{sensor_id} [{alert_type}] -> {value}")
        if not alerts:
            self.alerts_list.addItem("No recent alerts")
        self.clear_alert_history_button.setEnabled(bool(alerts))

    def _apply_sensor_payload(self, sensors: dict[str, Any]) -> None:
        # Update temperatures table
        temps = sensors.get("temperatures", [])
        self.temperatures_list.setRowCount(len(temps))
        for row, sensor in enumerate(temps):
            hw_name = sensor.get("hardware_name", "Unknown")
            sensor_name = sensor.get("sensor_name", "Unknown")
            value = sensor.get("value", "N/A")

            # Name column
            name_item = QTableWidgetItem(f"{hw_name} / {sensor_name}")
            self.temperatures_list.setItem(row, 0, name_item)

            # Value column
            if isinstance(value, (int, float)):
                value_text = f"{value:.1f}°C"
            else:
                value_text = str(value)
            value_item = QTableWidgetItem(value_text)
            self.temperatures_list.setItem(row, 1, value_item)

        # Update fans table
        fans = sensors.get("fans", [])
        self.fans_list.setRowCount(len(fans))
        for row, fan in enumerate(fans):
            hw_name = fan.get("hardware_name", "Unknown")
            sensor_name = fan.get("sensor_name", "Unknown")
            rpm = fan.get("rpm", "N/A")

            # Name column
            name_item = QTableWidgetItem(f"{hw_name} / {sensor_name}")
            self.fans_list.setItem(row, 0, name_item)

            # Value column
            if isinstance(rpm, (int, float)):
                rpm_text = f"{int(round(rpm))} RPM"
            else:
                rpm_text = str(rpm)
            value_item = QTableWidgetItem(rpm_text)
            self.fans_list.setItem(row, 1, value_item)

    def _handle_stream_payload(self, sensors: dict[str, Any]) -> None:
        self.connection_label.setText("Connection: Connected")
        self._hide_error()
        self._apply_sensor_payload(sensors)

    def _handle_stream_failure(self, message: str) -> None:
        self.connection_label.setText("Connection: Disconnected")
        self._show_error(message)
        self.stop_live_updates()

    def _handle_stream_finished(self) -> None:
        # Regardless of thread running state, treat this as the end of
        # the active stream and update UI immediately. This makes the
        # behaviour deterministic across platforms and avoids races
        # where the thread finishes slightly later than the payload
        # delivery.
        self._stream_worker = None
        self.live_updates_button.setText("Start Live Updates")

    def _show_error(self, message: str) -> None:
        self.error_label.setStyleSheet("color: #b00020;")
        self.error_label.setText(message)
        self.error_label.show()

    def _show_message(self, message: str) -> None:
        self.error_label.setStyleSheet("color: #1d6f42;")
        self.error_label.setText(message)
        self.error_label.show()

    def _hide_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()
