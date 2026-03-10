"""Tests for the PySide6 service management page."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMessageBox

from pysysfan.gui.desktop.service_page import ServicePage
from pysysfan.state_file import DaemonStateFile, write_state


def _service_status(*, task_installed: bool = True, daemon_running: bool = True):
    return SimpleNamespace(
        task_installed=task_installed,
        task_enabled=task_installed,
        task_status="Running" if task_installed else None,
        task_last_run="2026-03-09T08:00:00" if task_installed else None,
        daemon_running=daemon_running,
        daemon_pid=1234 if daemon_running else None,
        daemon_healthy=daemon_running,
    )


def _daemon_state() -> DaemonStateFile:
    return DaemonStateFile(
        timestamp=time.time(),
        pid=1234,
        running=True,
        uptime_seconds=30.0,
        active_profile="gaming",
        poll_interval=1.0,
        config_path="C:/Users/test/.pysysfan/profiles/gaming.yaml",
    )


def test_service_page_refresh_populates_status_and_diagnostics(qtbot, tmp_path) -> None:
    """Refreshing should populate labels and diagnostics from local helpers."""
    state_path = tmp_path / "daemon_state.json"
    write_state(_daemon_state(), state_path)
    page = ServicePage(
        state_path=state_path,
        service_status_getter=lambda: _service_status(),
        task_details_getter=lambda: {"Status": "Ready", "Next Run Time": "N/A"},
    )
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.connection_label.text() == "Service state: Ready"
    assert page.task_installed_label.text() == "Task installed: Yes"
    assert page.task_enabled_label.text() == "Task enabled: Yes"
    assert page.daemon_running_label.text() == "Daemon: Running (healthy)"
    assert page.daemon_profile_label.text() == "Daemon profile: gaming"
    assert "Task Scheduler" in page.diagnostics_view.toPlainText()
    assert "Daemon State" in page.diagnostics_view.toPlainText()


def test_service_page_sets_button_states_from_status(qtbot, tmp_path) -> None:
    """Button availability should reflect Task Scheduler and daemon state."""
    page = ServicePage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _service_status(
            task_installed=True, daemon_running=False
        ),
        task_details_getter=lambda: {},
    )
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.install_button.isEnabled() is True
    assert page.uninstall_button.isEnabled() is True
    assert page.start_button.isEnabled() is True
    assert page.stop_button.isEnabled() is False
    assert page.restart_button.isEnabled() is False


def test_service_page_shows_popup_for_admin_elevation(qtbot, tmp_path) -> None:
    """Service actions should explain when Windows requests elevation."""
    page = ServicePage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _service_status(
            task_installed=False,
            daemon_running=False,
        ),
        task_details_getter=lambda: {},
        command_runner=lambda action: (
            True,
            "Windows asked for Administrator permission for `pysysfan service install`. "
            "Approve the Windows UAC prompt to continue. If no prompt appears, "
            "close PySysFan and relaunch it as Administrator.",
        ),
    )
    qtbot.addWidget(page)

    with patch.object(QMessageBox, "information") as mock_information:
        page.install_button.click()

    mock_information.assert_called_once()


def test_service_page_confirms_repair_when_task_already_installed(
    qtbot, tmp_path
) -> None:
    """Repair installs should confirm before replacing an existing task."""
    calls: list[str] = []
    page = ServicePage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _service_status(
            task_installed=True,
            daemon_running=False,
        ),
        task_details_getter=lambda: {},
        command_runner=lambda action: (calls.append(action) or True, "Repaired"),
    )
    qtbot.addWidget(page)
    page.refresh_data()

    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.No,
    ):
        page.install_button.click()

    assert calls == []


def test_service_page_runs_stop_action(qtbot, tmp_path) -> None:
    """Stopping should confirm and use the injected command runner."""
    calls: list[str] = []
    page = ServicePage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _service_status(),
        task_details_getter=lambda: {},
        command_runner=lambda action: (calls.append(action) or True, "Stopped"),
    )
    qtbot.addWidget(page)
    page.refresh_data()

    with patch.object(
        QMessageBox,
        "question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        page.stop_button.click()

    assert calls == ["stop"]
    assert page.message_label.text() == "Stopped"


def test_service_page_runs_installer_commands(qtbot, tmp_path) -> None:
    """Installer buttons should use the injected installer runner."""
    calls: list[str] = []
    page = ServicePage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _service_status(
            task_installed=False, daemon_running=False
        ),
        task_details_getter=lambda: {},
        installer_runner=lambda executable: (calls.append(executable) or True, "OK"),
    )
    qtbot.addWidget(page)

    page.install_lhm_button.click()
    page.install_pawnio_button.click()

    assert calls == ["pysysfan-install-lhm", "pysysfan-install-pawnio"]
    assert page.message_label.text() == "OK"


def test_service_page_updates_minimize_to_tray_preference(qtbot, tmp_path) -> None:
    """The desktop preference toggle should persist through injected helpers."""
    calls: list[bool] = []
    with patch(
        "pysysfan.gui.desktop.service_page.QSystemTrayIcon.isSystemTrayAvailable",
        return_value=True,
    ):
        page = ServicePage(
            state_path=tmp_path / "missing.json",
            service_status_getter=lambda: _service_status(
                task_installed=False,
                daemon_running=False,
            ),
            task_details_getter=lambda: {},
            minimize_to_tray_getter=lambda: False,
            minimize_to_tray_setter=lambda enabled: calls.append(enabled),
        )
    qtbot.addWidget(page)

    assert page.minimize_to_tray_checkbox.isChecked() is False

    page.minimize_to_tray_checkbox.click()

    assert calls == [True]
    assert page.message_label.text() == "Saved desktop app preference."


def test_service_page_only_polls_while_visible(qtbot, tmp_path) -> None:
    """The Service page should only run its refresh timer while visible."""
    page = ServicePage(
        state_path=tmp_path / "missing.json",
        service_status_getter=lambda: _service_status(),
        task_details_getter=lambda: {},
    )
    qtbot.addWidget(page)

    assert page._refresh_timer.isActive() is False

    page.show()
    qtbot.waitUntil(page._refresh_timer.isActive)

    page.hide()
    qtbot.waitUntil(lambda: not page._refresh_timer.isActive())
