"""Service management page for the PySide6 desktop GUI."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pysysfan.gui.desktop.local_backend import (
    ELEVATION_REQUESTED_SENTINEL,
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
        self._task_installed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

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
        self.refresh_button.setObjectName("serviceRefreshBtn")
        self.refresh_button.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.refresh_button)

        self.message_label = QLabel("", self)
        self.message_label.setObjectName("serviceMessageLabel")
        self.message_label.setWordWrap(False)
        self.message_label.hide()
        toolbar.addWidget(self.message_label)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.start_stop_button = QPushButton("▶ Start", self)
        self.start_stop_button.setObjectName("serviceStartStopBtn")
        self.start_stop_button.clicked.connect(
            lambda: self._run_action("start_stop_toggle")
        )

        self.restart_button = QPushButton("↻ Restart", self)
        self.restart_button.setObjectName("serviceRestartBtn")
        self.restart_button.clicked.connect(lambda: self._run_action("restart"))

        self.install_uninstall_button = QPushButton("Install", self)
        self.install_uninstall_button.setObjectName("serviceInstallUninstallBtn")
        self.install_uninstall_button.clicked.connect(
            lambda: self._run_action("install_uninstall_toggle")
        )

        self.enable_disable_button = QPushButton("Enable Schedule", self)
        self.enable_disable_button.setObjectName("serviceEnableDisableBtn")
        self.enable_disable_button.clicked.connect(
            lambda: self._run_action("enable_disable_toggle")
        )

        self.install_lhm_button = QPushButton("↓", self)
        self.install_lhm_button.setObjectName("serviceInstallLhmBtn")
        self.install_lhm_button.setToolTip("Download LHM")
        self.install_lhm_button.clicked.connect(
            lambda: self._run_installer("pysysfan-install-lhm")
        )

        self.install_pawnio_button = QPushButton("↓", self)
        self.install_pawnio_button.setObjectName("serviceInstallPawnioBtn")
        self.install_pawnio_button.setToolTip("Download PawnIO")
        self.install_pawnio_button.clicked.connect(
            lambda: self._run_installer("pysysfan-install-pawnio")
        )

        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(content_layout, 1)

        left_scroll = QScrollArea(self)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(200)
        left_scroll.setMaximumWidth(200)

        self._sidebar = QFrame(left_scroll)
        self._sidebar.setObjectName("serviceSidebar")
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(0, 0, 16, 0)
        sidebar_layout.setSpacing(12)

        def section_header(text: str) -> QLabel:
            label = QLabel(text, self._sidebar)
            label.setProperty("serviceSectionHeader", True)
            return label

        status_box = QFrame(self._sidebar)
        status_box.setObjectName("serviceStatusBox")
        status_box.setProperty("serviceCard", True)
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(16, 12, 16, 12)
        status_layout.setSpacing(8)

        status_top = QHBoxLayout()
        status_top.setSpacing(10)

        self.status_dot = QFrame(status_box)
        self.status_dot.setObjectName("serviceStatusDot")
        self.status_dot.setFixedSize(20, 20)

        self.service_status_label = QLabel("Unknown", status_box)
        self.service_status_label.setObjectName("serviceStatusLabel")

        status_top.addWidget(self.status_dot)
        status_top.addWidget(self.service_status_label)
        status_top.addStretch(1)

        self.service_pid_label = QLabel("PID N/A · N/A", status_box)
        self.service_pid_label.setObjectName("servicePidLabel")

        status_layout.addLayout(status_top)
        status_layout.addWidget(self.service_pid_label)

        details_box = QFrame(self._sidebar)
        details_box.setObjectName("serviceDetailsBox")
        details_box.setProperty("serviceCard", True)
        details_layout = QGridLayout(details_box)
        details_layout.setContentsMargins(12, 10, 12, 10)
        details_layout.setHorizontalSpacing(8)
        details_layout.setVerticalSpacing(6)

        self.detail_task_label = QLabel("Task", details_box)
        self.detail_task_value = QLabel("N/A", details_box)
        self.detail_task_value.setObjectName("detailValue")

        self.detail_schedule_label = QLabel("Schedule", details_box)
        self.detail_schedule_value = QLabel("N/A", details_box)
        self.detail_schedule_value.setObjectName("detailValue")

        self.detail_trigger_label = QLabel("Trigger", details_box)
        self.detail_trigger_value = QLabel("N/A", details_box)
        self.detail_trigger_value.setObjectName("detailValue")

        self.detail_tray_label = QLabel("Minimise to tray", details_box)
        self.tray_switch = QCheckBox(details_box)
        self.tray_switch.setObjectName("traySwitch")
        self.tray_switch.setChecked(self._minimize_to_tray_getter())
        self.tray_switch.toggled.connect(self._set_minimize_to_tray_preference)

        details_layout.addWidget(self.detail_task_label, 0, 0)
        details_layout.addWidget(self.detail_task_value, 0, 1)
        details_layout.addWidget(self.detail_schedule_label, 1, 0)
        details_layout.addWidget(self.detail_schedule_value, 1, 1)
        details_layout.addWidget(self.detail_trigger_label, 2, 0)
        details_layout.addWidget(self.detail_trigger_value, 2, 1)
        details_layout.addWidget(self.detail_tray_label, 3, 0)
        details_layout.addWidget(self.tray_switch, 3, 1)

        actions_box = QFrame(self._sidebar)
        actions_box.setObjectName("serviceActionsBox")
        actions_box.setProperty("serviceCard", True)
        actions_layout = QGridLayout(actions_box)
        actions_layout.setContentsMargins(12, 10, 12, 10)
        actions_layout.setHorizontalSpacing(8)
        actions_layout.setVerticalSpacing(8)

        actions_layout.addWidget(self.start_stop_button, 0, 0)
        actions_layout.addWidget(self.restart_button, 1, 0)
        actions_layout.addWidget(self.install_uninstall_button, 2, 0)
        actions_layout.addWidget(self.enable_disable_button, 3, 0)

        components_box = QFrame(self._sidebar)
        components_box.setObjectName("serviceComponentsBox")
        components_layout = QVBoxLayout(components_box)
        components_layout.setContentsMargins(0, 0, 0, 0)
        components_layout.setSpacing(10)

        lhm_card = QFrame(components_box)
        lhm_card.setObjectName("serviceComponentCard")
        lhm_card.setProperty("serviceCard", True)
        lhm_card.setProperty("componentAccent", "lhm")
        lhm_layout = QHBoxLayout(lhm_card)
        lhm_layout.setContentsMargins(0, 0, 12, 0)
        lhm_layout.setSpacing(0)

        lhm_accent = QFrame(lhm_card)
        lhm_accent.setObjectName("componentAccentBar")
        lhm_accent.setFixedWidth(4)
        lhm_layout.addWidget(lhm_accent)

        lhm_text = QVBoxLayout()
        lhm_text.setSpacing(2)
        lhm_title = QLabel("LHM v0.9.14", lhm_card)
        lhm_title.setObjectName("serviceComponentTitle")
        lhm_text.addWidget(lhm_title)
        lhm_layout.addLayout(lhm_text, stretch=1)
        lhm_layout.addWidget(self.install_lhm_button)

        pawnio_card = QFrame(components_box)
        pawnio_card.setObjectName("serviceComponentCard")
        pawnio_card.setProperty("serviceCard", True)
        pawnio_card.setProperty("componentAccent", "pawnio")
        pawnio_layout = QHBoxLayout(pawnio_card)
        pawnio_layout.setContentsMargins(0, 0, 12, 0)
        pawnio_layout.setSpacing(0)

        pawnio_accent = QFrame(pawnio_card)
        pawnio_accent.setObjectName("componentAccentBar")
        pawnio_accent.setFixedWidth(4)
        pawnio_layout.addWidget(pawnio_accent)

        pawnio_text = QVBoxLayout()
        pawnio_text.setSpacing(2)
        pawnio_title = QLabel("PawnIO v1.2.0", pawnio_card)
        pawnio_title.setObjectName("serviceComponentTitle")
        pawnio_text.addWidget(pawnio_title)
        pawnio_layout.addLayout(pawnio_text, stretch=1)
        pawnio_layout.addWidget(self.install_pawnio_button)

        components_layout.addWidget(lhm_card)
        components_layout.addWidget(pawnio_card)

        sidebar_layout.addWidget(section_header("SERVICE"))
        sidebar_layout.addWidget(status_box)
        sidebar_layout.addWidget(section_header("DETAILS"))
        sidebar_layout.addWidget(details_box)
        sidebar_layout.addWidget(section_header("ACTIONS"))
        sidebar_layout.addWidget(actions_box)
        sidebar_layout.addWidget(section_header("COMPONENTS"))
        sidebar_layout.addWidget(components_box)
        sidebar_layout.addStretch(1)

        left_scroll.setWidget(self._sidebar)
        content_layout.addWidget(left_scroll)

        divider = QFrame(self)
        divider.setObjectName("serviceDivider")
        divider.setFixedWidth(1)
        content_layout.addWidget(divider)

        self._diagnostics_panel = QFrame(self)
        self._diagnostics_panel.setObjectName("serviceDiagnosticsPanel")
        diagnostics_layout = QVBoxLayout(self._diagnostics_panel)
        diagnostics_layout.setContentsMargins(16, 0, 16, 16)
        diagnostics_layout.setSpacing(10)

        diagnostics_header = QHBoxLayout()
        diagnostics_title = QLabel("Diagnostics Log", self._diagnostics_panel)
        diagnostics_title.setObjectName("serviceDiagnosticsTitle")
        diagnostics_header.addWidget(diagnostics_title)
        diagnostics_header.addStretch(1)

        self.clear_diagnostics_button = QPushButton("Clear", self)
        self.clear_diagnostics_button.setObjectName("serviceRefreshBtn")
        self.clear_diagnostics_button.clicked.connect(
            lambda: self.diagnostics_view.clear()
        )
        diagnostics_header.addWidget(self.clear_diagnostics_button)

        self.copy_diagnostics_button = QPushButton("Copy All", self)
        self.copy_diagnostics_button.setObjectName("serviceRefreshBtn")
        self.copy_diagnostics_button.clicked.connect(
            self._copy_diagnostics_to_clipboard
        )
        diagnostics_header.addWidget(self.copy_diagnostics_button)
        diagnostics_layout.addLayout(diagnostics_header)

        self.diagnostics_view = QPlainTextEdit(self)
        self.diagnostics_view.setObjectName("diagnosticsView")
        self.diagnostics_view.setReadOnly(True)
        self.diagnostics_view.setMinimumHeight(260)
        diagnostics_layout.addWidget(self.diagnostics_view, 1)

        content_layout.addWidget(self._diagnostics_panel)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh_data)
        self._diagnostic_lines: list[tuple[str, str, str]] = []
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
        if action == "install" and self._task_installed and confirm_message is None:
            confirm_message = (
                "Reinstall the scheduled task with the latest service settings?\n\n"
                "This repairs older installs that could not report daemon status "
                "correctly to the desktop app."
            )

        if confirm_message and not self._confirm(confirm_message):
            return

        success, message = self._command_runner(action)
        self.refresh_data()
        self._show_message(message, is_error=not success)
        self._maybe_show_elevation_guidance(success, message)

    def _run_installer(self, executable_name: str) -> None:
        success, message = self._installer_runner(executable_name)
        self._show_message(message, is_error=not success)
        self._maybe_show_elevation_guidance(success, message)

    def _set_minimize_to_tray_preference(self, enabled: bool) -> None:
        self._minimize_to_tray_setter(enabled)
        self._show_message("Saved desktop app preference.", is_error=False)

    def _open_service_log(self) -> None:
        """Open the service log file in the system default text editor."""
        import os
        from pysysfan.platforms.windows_service import SERVICE_LOG_PATH

        if not SERVICE_LOG_PATH.is_file():
            self._show_message(
                "No service log file found yet. "
                "The log is created when the service starts.",
                is_error=True,
            )
            return
        try:
            os.startfile(str(SERVICE_LOG_PATH))  # noqa: S606
        except OSError as exc:
            self._show_message(f"Could not open log file: {exc}", is_error=True)

    def _apply_status(self, service_status: Any, daemon_state) -> None:
        task_installed = bool(getattr(service_status, "task_installed", False))
        task_enabled = bool(getattr(service_status, "task_enabled", False))
        daemon_running = bool(getattr(service_status, "daemon_running", False))
        daemon_healthy = bool(getattr(service_status, "daemon_healthy", False))
        self._task_installed = task_installed

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

        self.install_button.setEnabled(True)
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

    def _maybe_show_elevation_guidance(self, success: bool, message: str) -> None:
        """Show a clear modal prompt when Windows elevation is required."""
        if not success or ELEVATION_REQUESTED_SENTINEL not in message:
            return

        QMessageBox.information(
            self,
            "Administrator Permission Needed",
            message,
        )

    @staticmethod
    def _format_bool(value: Any) -> str:
        return "Yes" if value else "No"
