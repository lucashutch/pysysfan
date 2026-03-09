"""Tests for Windows service status integration with the daemon state file."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pysysfan.platforms.windows_service import get_service_status
from pysysfan.state_file import DaemonStateFile


def _daemon_state() -> DaemonStateFile:
    return DaemonStateFile(
        timestamp=100.0,
        pid=4321,
        running=True,
        uptime_seconds=12.0,
        active_profile="default",
        poll_interval=1.0,
        config_path="C:/Users/test/.pysysfan/config.yaml",
    )


class TestGetServiceStatus:
    @patch("pysysfan.platforms.windows_service.read_state")
    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_reads_daemon_state(self, mock_run, mock_read_state):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Status: Running\n"),
            MagicMock(returncode=0, stdout="Last Run Time: 2026-03-09 08:00\n"),
        ]
        mock_read_state.return_value = _daemon_state()

        status = get_service_status()

        assert status.task_installed is True
        assert status.daemon_running is True
        assert status.daemon_pid == 4321
        assert status.daemon_healthy is True

    @patch("pysysfan.platforms.windows_service.read_state", return_value=None)
    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_handles_missing_state_file(self, mock_run, mock_read_state):
        mock_run.return_value = MagicMock(returncode=1)

        status = get_service_status()

        assert status.task_installed is False
        assert status.daemon_running is False
        assert status.daemon_pid is None
        assert status.daemon_healthy is False
