"""Tests for the PySide6 service management page."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMessageBox

from pysysfan.gui.desktop.service_page import ServicePage


class FakeServiceClient:
    """Small fake daemon client for service page tests."""

    def __init__(self):
        self.status = {
            "task_installed": True,
            "task_enabled": True,
            "task_status": "Running",
            "task_last_run": "2026-03-09T08:00:00",
            "daemon_running": True,
            "daemon_pid": 1234,
            "daemon_healthy": True,
        }
        self.logs = {
            "logs": ["line one", "line two"],
            "total_lines": 2,
        }
        self.actions: list[str] = []

    def get_service_status(self):
        return self.status

    def get_service_logs(self, lines: int = 100):
        return self.logs | {"requested_lines": lines}

    def install_service(self):
        self.actions.append("install")
        return {"success": True, "message": "Service installed"}

    def uninstall_service(self):
        self.actions.append("uninstall")
        return {"success": True, "message": "Service uninstalled"}

    def enable_service(self):
        self.actions.append("enable")
        return {"success": True, "message": "Service enabled"}

    def disable_service(self):
        self.actions.append("disable")
        return {"success": True, "message": "Service disabled"}

    def start_service(self):
        self.actions.append("start")
        self.status["daemon_running"] = True
        return {"success": True, "message": "Daemon started"}

    def stop_service(self):
        self.actions.append("stop")
        self.status["daemon_running"] = False
        return {
            "success": True,
            "message": "Daemon stopped via graceful_api",
            "method": "graceful_api",
        }

    def restart_service(self):
        self.actions.append("restart")
        return {"success": True, "message": "Daemon restarted"}


def test_service_page_refresh_populates_status_and_logs(qtbot) -> None:
    """Refreshing the service page should populate labels and logs."""
    fake_client = FakeServiceClient()
    page = ServicePage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.connection_label.text() == "Connection: Connected"
    assert page.task_installed_label.text() == "Task installed: Yes"
    assert page.task_enabled_label.text() == "Task enabled: Yes"
    assert page.task_status_label.text() == "Task status: Running"
    assert page.daemon_running_label.text() == "Daemon: Running (healthy)"
    assert page.logs_view.toPlainText() == "line one\nline two"
    assert page.logs_summary_label.text() == "Showing 2 of 2 lines"


def test_service_page_surfaces_refresh_errors(qtbot) -> None:
    """Service page should surface refresh failures instead of crashing."""

    def broken_factory():
        raise RuntimeError("daemon offline")

    page = ServicePage(client_factory=broken_factory)
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.connection_label.text() == "Connection: Disconnected"
    assert page.message_label.text() == "daemon offline"
    assert not page.message_label.isHidden()


def test_service_page_stop_action_refreshes_status(qtbot) -> None:
    """Stopping the daemon should call the client and refresh the status widgets."""
    fake_client = FakeServiceClient()
    page = ServicePage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)
    page.refresh_data()

    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        page.stop_button.click()

    assert fake_client.actions == ["stop"]
    assert page.daemon_running_label.text() == "Daemon: Stopped"
    assert page.message_label.text() == "Daemon stopped via graceful_api (graceful_api)"
