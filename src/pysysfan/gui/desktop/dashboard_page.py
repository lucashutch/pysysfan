"""Dashboard page for the PySide6 desktop GUI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pysysfan.api.client import PySysFanClient


class SensorStreamWorker(QThread):
    """Background worker for daemon sensor streaming."""

    sensors_received = Signal(dict)
    stream_failed = Signal(str)

    def __init__(self, client: PySysFanClient):
        super().__init__()
        self._client = client

    def run(self) -> None:
        try:
            for payload in self._client.stream_sensors():
                if self.isInterruptionRequested():
                    return
                self.sensors_received.emit(payload)
        except Exception as exc:
            self.stream_failed.emit(str(exc))


class DashboardPage(QWidget):
    """Desktop dashboard backed by the Python API client."""

    def __init__(
        self,
        client_factory: Callable[[], PySysFanClient] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
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

        layout.addLayout(summary_layout)

        sensor_layout = QHBoxLayout()
        sensor_layout.setSpacing(16)

        temps_column = QVBoxLayout()
        temps_heading = QLabel("Temperatures", self)
        temps_heading.setStyleSheet("font-weight: 600;")
        temps_column.addWidget(temps_heading)
        self.temperatures_list = QListWidget(self)
        self.temperatures_list.setObjectName("temperaturesList")
        temps_column.addWidget(self.temperatures_list)
        sensor_layout.addLayout(temps_column)

        fans_column = QVBoxLayout()
        fans_heading = QLabel("Fans", self)
        fans_heading.setStyleSheet("font-weight: 600;")
        fans_column.addWidget(fans_heading)
        self.fans_list = QListWidget(self)
        self.fans_list.setObjectName("fansList")
        fans_column.addWidget(self.fans_list)
        sensor_layout.addLayout(fans_column)

        layout.addLayout(sensor_layout)
        layout.addStretch(1)

    def refresh_data(self) -> None:
        """Refresh the dashboard using the latest daemon snapshot and sensors."""
        try:
            client = self._get_client()
            status = client.get_status()
            sensors = client.get_sensors()
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_error(str(exc))
            return

        self.connection_label.setText("Connection: Connected")
        self._hide_error()
        self._apply_status(status)
        self._apply_sensor_payload(sensors)

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

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Ensure the stream worker is shut down when the page closes."""
        self.stop_live_updates()
        super().closeEvent(event)

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

    def _apply_sensor_payload(self, sensors: dict[str, Any]) -> None:
        self.temperatures_list.clear()
        for sensor in sensors.get("temperatures", []):
            label = (
                f"{sensor.get('sensor_name', 'Unknown')}: "
                f"{sensor.get('value', 'N/A')} C"
            )
            self.temperatures_list.addItem(label)

        self.fans_list.clear()
        for fan in sensors.get("fans", []):
            label = f"{fan.get('sensor_name', 'Unknown')}: {fan.get('rpm', 'N/A')} RPM"
            self.fans_list.addItem(label)

    def _handle_stream_payload(self, sensors: dict[str, Any]) -> None:
        self.connection_label.setText("Connection: Connected")
        self._hide_error()
        self._apply_sensor_payload(sensors)

    def _handle_stream_failure(self, message: str) -> None:
        self.connection_label.setText("Connection: Disconnected")
        self._show_error(message)
        self.stop_live_updates()

    def _handle_stream_finished(self) -> None:
        if self._stream_worker is not None and not self._stream_worker.isRunning():
            self._stream_worker = None
            self.live_updates_button.setText("Start Live Updates")

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _hide_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()
