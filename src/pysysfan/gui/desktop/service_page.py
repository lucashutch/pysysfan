"""Service management page for the PySide6 desktop GUI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pysysfan.api.client import PySysFanClient


class ServicePage(QWidget):
    """Desktop service management page backed by the Python API client."""

    def __init__(
        self,
        client_factory: Callable[[], PySysFanClient] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._client_factory = client_factory or PySysFanClient
        self._client: PySysFanClient | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Service", self)
        heading.setObjectName("serviceTitle")
        heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(heading)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.connection_label = QLabel("Connection: Disconnected", self)
        self.connection_label.setObjectName("serviceConnectionLabel")
        toolbar.addWidget(self.connection_label)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("serviceRefreshButton")
        self.refresh_button.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.refresh_button)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("serviceMessageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)

        status_layout = QGridLayout()
        status_layout.setHorizontalSpacing(24)
        status_layout.setVerticalSpacing(8)

        self.task_installed_label = QLabel("Task installed: N/A", self)
        self.task_enabled_label = QLabel("Task enabled: N/A", self)
        self.task_status_label = QLabel("Task status: N/A", self)
        self.task_last_run_label = QLabel("Last run: N/A", self)
        self.daemon_running_label = QLabel("Daemon: N/A", self)
        self.daemon_pid_label = QLabel("Daemon PID: N/A", self)

        status_layout.addWidget(self.task_installed_label, 0, 0)
        status_layout.addWidget(self.task_enabled_label, 0, 1)
        status_layout.addWidget(self.task_status_label, 1, 0)
        status_layout.addWidget(self.task_last_run_label, 1, 1)
        status_layout.addWidget(self.daemon_running_label, 2, 0)
        status_layout.addWidget(self.daemon_pid_label, 2, 1)

        layout.addLayout(status_layout)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.install_button = QPushButton("Install", self)
        self.install_button.clicked.connect(
            lambda: self._run_action("Service installed", "install")
        )
        actions_layout.addWidget(self.install_button)

        self.uninstall_button = QPushButton("Uninstall", self)
        self.uninstall_button.clicked.connect(
            lambda: self._run_action(
                "Service uninstalled",
                "uninstall",
                confirm_message="Uninstall the service? This removes the scheduled task.",
            )
        )
        actions_layout.addWidget(self.uninstall_button)

        self.enable_button = QPushButton("Enable", self)
        self.enable_button.clicked.connect(
            lambda: self._run_action("Service enabled", "enable")
        )
        actions_layout.addWidget(self.enable_button)

        self.disable_button = QPushButton("Disable", self)
        self.disable_button.clicked.connect(
            lambda: self._run_action("Service disabled", "disable")
        )
        actions_layout.addWidget(self.disable_button)

        self.start_button = QPushButton("Start", self)
        self.start_button.clicked.connect(
            lambda: self._run_action("Daemon started", "start")
        )
        actions_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop", self)
        self.stop_button.clicked.connect(
            lambda: self._run_action(
                "Daemon stopped",
                "stop",
                confirm_message="Stop the daemon? Fans will return to BIOS control.",
            )
        )
        actions_layout.addWidget(self.stop_button)

        self.restart_button = QPushButton("Restart", self)
        self.restart_button.clicked.connect(
            lambda: self._run_action("Daemon restarted", "restart")
        )
        actions_layout.addWidget(self.restart_button)

        actions_layout.addStretch(1)
        layout.addLayout(actions_layout)

        logs_toolbar = QHBoxLayout()
        logs_toolbar.setSpacing(12)

        logs_heading = QLabel("Logs", self)
        logs_heading.setStyleSheet("font-weight: 600;")
        logs_toolbar.addWidget(logs_heading)

        self.log_line_count = QSpinBox(self)
        self.log_line_count.setObjectName("logLineCount")
        self.log_line_count.setRange(10, 500)
        self.log_line_count.setSingleStep(10)
        self.log_line_count.setValue(100)
        logs_toolbar.addWidget(self.log_line_count)

        self.refresh_logs_button = QPushButton("Refresh Logs", self)
        self.refresh_logs_button.setObjectName("refreshLogsButton")
        self.refresh_logs_button.clicked.connect(self.refresh_logs)
        logs_toolbar.addWidget(self.refresh_logs_button)

        self.logs_summary_label = QLabel("Showing 0 lines", self)
        self.logs_summary_label.setObjectName("logsSummaryLabel")
        logs_toolbar.addWidget(self.logs_summary_label)

        logs_toolbar.addStretch(1)
        layout.addLayout(logs_toolbar)

        self.logs_view = QPlainTextEdit(self)
        self.logs_view.setObjectName("logsView")
        self.logs_view.setReadOnly(True)
        self.logs_view.setMinimumHeight(220)
        layout.addWidget(self.logs_view)

        layout.addStretch(1)

    def refresh_data(self) -> None:
        """Refresh service status and recent logs."""
        try:
            client = self._get_client()
            status = client.get_service_status()
            logs = client.get_service_logs(self.log_line_count.value())
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_message(str(exc), is_error=True)
            return

        self.connection_label.setText("Connection: Connected")
        self._apply_status(status)
        self._apply_logs(logs)
        self._show_message("", is_error=False)

    def refresh_logs(self) -> None:
        """Refresh only the log view."""
        try:
            logs = self._get_client().get_service_logs(self.log_line_count.value())
        except Exception as exc:
            self._show_message(str(exc), is_error=True)
            return

        self.connection_label.setText("Connection: Connected")
        self._apply_logs(logs)
        self._show_message("", is_error=False)

    def _run_action(
        self,
        fallback_message: str,
        action: str,
        confirm_message: str | None = None,
    ) -> None:
        if confirm_message and not self._confirm(confirm_message):
            return

        client = self._get_client()
        action_method = getattr(client, f"{action}_service")

        try:
            response = action_method()
        except Exception as exc:
            self.connection_label.setText("Connection: Disconnected")
            self._show_message(str(exc), is_error=True)
            return

        message = response.get("message", fallback_message)
        method = response.get("method")
        if method:
            message = f"{message} ({method})"

        self.connection_label.setText("Connection: Connected")
        self.refresh_data()
        self._show_message(message, is_error=False)

    def _confirm(self, message: str) -> bool:
        return (
            QMessageBox.question(
                self,
                "Confirm Service Action",
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

    def _apply_status(self, status: dict[str, Any]) -> None:
        self.task_installed_label.setText(
            f"Task installed: {self._format_bool(status.get('task_installed'))}"
        )
        self.task_enabled_label.setText(
            f"Task enabled: {self._format_bool(status.get('task_enabled'))}"
        )
        self.task_status_label.setText(
            f"Task status: {status.get('task_status') or 'N/A'}"
        )
        self.task_last_run_label.setText(
            f"Last run: {status.get('task_last_run') or 'Never'}"
        )

        if status.get("daemon_running"):
            daemon_health = "healthy" if status.get("daemon_healthy") else "unhealthy"
            daemon_text = f"Running ({daemon_health})"
        else:
            daemon_text = "Stopped"
        self.daemon_running_label.setText(f"Daemon: {daemon_text}")
        self.daemon_pid_label.setText(
            f"Daemon PID: {status.get('daemon_pid') or 'N/A'}"
        )

        task_installed = bool(status.get("task_installed"))
        task_enabled = bool(status.get("task_enabled"))
        daemon_running = bool(status.get("daemon_running"))

        self.install_button.setEnabled(not task_installed)
        self.uninstall_button.setEnabled(task_installed)
        self.enable_button.setEnabled(task_installed and not task_enabled)
        self.disable_button.setEnabled(task_installed and task_enabled)
        self.start_button.setEnabled(task_installed and not daemon_running)
        self.stop_button.setEnabled(daemon_running)
        self.restart_button.setEnabled(task_installed and daemon_running)

    def _apply_logs(self, logs: dict[str, Any]) -> None:
        log_lines = logs.get("logs", [])
        self.logs_view.setPlainText("\n".join(log_lines))
        self.logs_summary_label.setText(
            f"Showing {len(log_lines)} of {logs.get('total_lines', len(log_lines))} lines"
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

    @staticmethod
    def _format_bool(value: Any) -> str:
        return "Yes" if value else "No"
