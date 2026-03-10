"""Service management page for the PySide6 desktop GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from pysysfan.gui.desktop.local_backend import (
    read_daemon_state,
    run_installer_command,
    run_service_command,
)
from pysysfan.gui.desktop.preferences import (
    get_minimize_to_tray,
    set_minimize_to_tray,
)
from pysysfan.gui.desktop.theme import PAGE_HEADING_STYLE, management_page_stylesheet
from pysysfan.platforms import windows_service
from pysysfan.state_file import DEFAULT_STATE_PATH


class ServicePage(QWidget):
    """Desktop service management page backed by local helpers."""

    REFRESH_INTERVAL_MS = 10000

    def __init__(
        self,
        state_path: Path = DEFAULT_STATE_PATH,
        service_status_getter: Callable[[], Any] | None = None,
        task_details_getter: Callable[[], dict[str, str] | None] | None = None,
        command_runner: Callable[[str], tuple[bool, str]] | None = None,
        installer_runner: Callable[[str], tuple[bool, str]] | None = None,
        minimize_to_tray_getter: Callable[[], bool] | None = None,
        minimize_to_tray_setter: Callable[[bool], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("managementPageRoot")
        self._state_path = Path(state_path)
        self._service_status_getter = (
            service_status_getter or windows_service.get_service_status
        )
        self._task_details_getter = (
            task_details_getter or windows_service.get_task_details
        )
        self._command_runner = command_runner or run_service_command
        self._installer_runner = installer_runner or run_installer_command
        self._minimize_to_tray_getter = minimize_to_tray_getter or get_minimize_to_tray
        self._minimize_to_tray_setter = minimize_to_tray_setter or set_minimize_to_tray

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Service", self)
        heading.setObjectName("serviceTitle")
        heading.setStyleSheet(PAGE_HEADING_STYLE)
        layout.addWidget(heading)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.connection_label = QLabel("Service state: Unknown", self)
        self.connection_label.setObjectName("serviceConnectionLabel")
        toolbar.addWidget(self.connection_label)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.refresh_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("serviceMessageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)

        summary_group = QGroupBox("Task and Daemon State", self)
        summary_layout = QGridLayout(summary_group)
        summary_layout.setHorizontalSpacing(24)
        summary_layout.setVerticalSpacing(8)

        self.task_installed_label = QLabel("Task installed: N/A", self)
        self.task_enabled_label = QLabel("Task enabled: N/A", self)
        self.task_status_label = QLabel("Task status: N/A", self)
        self.task_last_run_label = QLabel("Last run: N/A", self)
        self.daemon_running_label = QLabel("Daemon: N/A", self)
        self.daemon_pid_label = QLabel("Daemon PID: N/A", self)
        self.daemon_profile_label = QLabel("Daemon profile: N/A", self)
        self.daemon_config_label = QLabel("Daemon config: N/A", self)
        self.daemon_config_label.setWordWrap(True)

        summary_layout.addWidget(self.task_installed_label, 0, 0)
        summary_layout.addWidget(self.task_enabled_label, 0, 1)
        summary_layout.addWidget(self.task_status_label, 1, 0)
        summary_layout.addWidget(self.task_last_run_label, 1, 1)
        summary_layout.addWidget(self.daemon_running_label, 2, 0)
        summary_layout.addWidget(self.daemon_pid_label, 2, 1)
        summary_layout.addWidget(self.daemon_profile_label, 3, 0)
        summary_layout.addWidget(self.daemon_config_label, 3, 1)
        layout.addWidget(summary_group)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        self.install_button = QPushButton("Install", self)
        self.install_button.clicked.connect(lambda: self._run_action("install"))
        actions_row.addWidget(self.install_button)

        self.uninstall_button = QPushButton("Uninstall", self)
        self.uninstall_button.clicked.connect(
            lambda: self._run_action(
                "uninstall",
                confirm_message="Uninstall the scheduled task?",
            )
        )
        actions_row.addWidget(self.uninstall_button)

        self.enable_button = QPushButton("Enable", self)
        self.enable_button.clicked.connect(lambda: self._run_action("enable"))
        actions_row.addWidget(self.enable_button)

        self.disable_button = QPushButton("Disable", self)
        self.disable_button.clicked.connect(lambda: self._run_action("disable"))
        actions_row.addWidget(self.disable_button)

        self.start_button = QPushButton("Start", self)
        self.start_button.clicked.connect(lambda: self._run_action("start"))
        actions_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop", self)
        self.stop_button.clicked.connect(
            lambda: self._run_action(
                "stop",
                confirm_message="Stop the daemon and return fan control to BIOS?",
            )
        )
        actions_row.addWidget(self.stop_button)

        self.restart_button = QPushButton("Restart", self)
        self.restart_button.clicked.connect(lambda: self._run_action("restart"))
        actions_row.addWidget(self.restart_button)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        installers_row = QHBoxLayout()
        installers_row.setSpacing(8)
        self.install_lhm_button = QPushButton("Install LHM", self)
        self.install_lhm_button.clicked.connect(
            lambda: self._run_installer("pysysfan-install-lhm")
        )
        installers_row.addWidget(self.install_lhm_button)

        self.install_pawnio_button = QPushButton("Install PawnIO", self)
        self.install_pawnio_button.clicked.connect(
            lambda: self._run_installer("pysysfan-install-pawnio")
        )
        installers_row.addWidget(self.install_pawnio_button)
        installers_row.addStretch(1)
        layout.addLayout(installers_row)

        desktop_group = QGroupBox("Desktop App", self)
        desktop_layout = QVBoxLayout(desktop_group)
        desktop_layout.setSpacing(8)

        self.minimize_to_tray_checkbox = QCheckBox(
            "Minimize the GUI to the Windows notification area",
            self,
        )
        self.minimize_to_tray_checkbox.setChecked(self._minimize_to_tray_getter())
        self.minimize_to_tray_checkbox.toggled.connect(
            self._set_minimize_to_tray_preference
        )
        desktop_layout.addWidget(self.minimize_to_tray_checkbox)

        desktop_hint = QLabel(
            "When enabled, clicking the title-bar minimize button hides the app "
            "to the tray instead of leaving it minimized on the taskbar.",
            self,
        )
        desktop_hint.setWordWrap(True)
        desktop_layout.addWidget(desktop_hint)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.minimize_to_tray_checkbox.setEnabled(False)
            desktop_hint.setText(
                "System tray integration is unavailable on this system, so the "
                "minimize-to-tray option is disabled."
            )

        layout.addWidget(desktop_group)

        diagnostics_group = QGroupBox("Diagnostics", self)
        diagnostics_layout = QVBoxLayout(diagnostics_group)
        self.diagnostics_view = QPlainTextEdit(self)
        self.diagnostics_view.setObjectName("diagnosticsView")
        self.diagnostics_view.setReadOnly(True)
        self.diagnostics_view.setMinimumHeight(260)
        diagnostics_layout.addWidget(self.diagnostics_view)
        layout.addWidget(diagnostics_group)
        layout.addStretch(1)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh_data)
        self.setStyleSheet(management_page_stylesheet(self.palette()))

    def showEvent(self, event) -> None:  # noqa: N802
        """Refresh and poll only while the service page is visible."""
        super().showEvent(event)
        self.refresh_data()
        self._refresh_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        """Stop periodic polling when the service page is hidden."""
        self._refresh_timer.stop()
        super().hideEvent(event)

    def refresh_data(self) -> None:
        """Refresh Task Scheduler and daemon state."""
        try:
            service_status = self._service_status_getter()
            task_details = self._task_details_getter() or {}
        except Exception as exc:
            self.connection_label.setText("Service state: Error")
            self._show_message(str(exc), is_error=True)
            return

        daemon_state = read_daemon_state(self._state_path)
        self.connection_label.setText("Service state: Ready")
        self._show_message("", is_error=False)
        self._apply_status(service_status, daemon_state)
        self._apply_diagnostics(task_details, daemon_state)

    def _run_action(self, action: str, confirm_message: str | None = None) -> None:
        if confirm_message and not self._confirm(confirm_message):
            return

        success, message = self._command_runner(action)
        self.refresh_data()
        self._show_message(message, is_error=not success)

    def _run_installer(self, executable_name: str) -> None:
        success, message = self._installer_runner(executable_name)
        self._show_message(message, is_error=not success)

    def _set_minimize_to_tray_preference(self, enabled: bool) -> None:
        self._minimize_to_tray_setter(enabled)
        self._show_message("Saved desktop app preference.", is_error=False)

    def _apply_status(self, service_status: Any, daemon_state) -> None:
        task_installed = bool(getattr(service_status, "task_installed", False))
        task_enabled = bool(getattr(service_status, "task_enabled", False))
        daemon_running = bool(getattr(service_status, "daemon_running", False))
        daemon_healthy = bool(getattr(service_status, "daemon_healthy", False))

        self.task_installed_label.setText(
            f"Task installed: {self._format_bool(task_installed)}"
        )
        self.task_enabled_label.setText(
            f"Task enabled: {self._format_bool(task_enabled)}"
        )
        self.task_status_label.setText(
            f"Task status: {getattr(service_status, 'task_status', None) or 'N/A'}"
        )
        self.task_last_run_label.setText(
            f"Last run: {getattr(service_status, 'task_last_run', None) or 'N/A'}"
        )

        if daemon_running:
            health_text = "healthy" if daemon_healthy else "needs attention"
            self.daemon_running_label.setText(f"Daemon: Running ({health_text})")
        else:
            self.daemon_running_label.setText("Daemon: Stopped")
        self.daemon_pid_label.setText(
            f"Daemon PID: {getattr(service_status, 'daemon_pid', None) or 'N/A'}"
        )

        if daemon_state is not None:
            self.daemon_profile_label.setText(
                f"Daemon profile: {daemon_state.active_profile}"
            )
            self.daemon_config_label.setText(
                f"Daemon config: {daemon_state.config_path}"
            )
        else:
            self.daemon_profile_label.setText("Daemon profile: N/A")
            self.daemon_config_label.setText("Daemon config: N/A")

        self.install_button.setEnabled(not task_installed)
        self.uninstall_button.setEnabled(task_installed)
        self.enable_button.setEnabled(task_installed and not task_enabled)
        self.disable_button.setEnabled(task_installed and task_enabled)
        self.start_button.setEnabled(task_installed and not daemon_running)
        self.stop_button.setEnabled(daemon_running)
        self.restart_button.setEnabled(task_installed and daemon_running)

    def _apply_diagnostics(self, task_details: dict[str, str], daemon_state) -> None:
        lines = ["Task Scheduler"]
        if task_details:
            for key in sorted(task_details):
                lines.append(f"{key}: {task_details[key]}")
        else:
            lines.append("No task details available.")

        lines.append("")
        lines.append("Daemon State")
        if daemon_state is None:
            lines.append("No daemon state file available.")
        else:
            lines.extend(
                [
                    f"PID: {daemon_state.pid}",
                    f"Running: {daemon_state.running}",
                    f"Active profile: {daemon_state.active_profile}",
                    f"Poll interval: {daemon_state.poll_interval:.1f}s",
                    f"Uptime: {daemon_state.uptime_seconds:.1f}s",
                    f"Config path: {daemon_state.config_path}",
                    f"Config error: {daemon_state.config_error or 'none'}",
                    f"Temperatures: {len(daemon_state.temperatures)}",
                    f"Fans: {len(daemon_state.fan_speeds)}",
                    f"Recent alerts: {len(daemon_state.recent_alerts)}",
                ]
            )

        self.diagnostics_view.setPlainText("\n".join(lines))

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
