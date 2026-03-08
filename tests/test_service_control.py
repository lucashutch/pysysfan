"""Tests for pysysfan.api.service_control — Safe stop strategies."""

from unittest.mock import MagicMock, patch

import psutil

from pysysfan.api.service_control import (
    StopMethod,
    build_local_api_base_url,
    find_daemon_process,
    get_recent_logs,
    stop_daemon_graceful,
)


class TestFindDaemonProcess:
    """Tests for find_daemon_process function."""

    @patch("psutil.process_iter")
    def test_find_daemon_with_run_command(self, mock_iter):
        """Should find daemon when process has 'pysysfan' and 'run' in cmdline."""
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "cmdline": ["python", "-m", "pysysfan", "run"]}
        mock_iter.return_value = [mock_proc]

        result = find_daemon_process()
        assert result == mock_proc

    @patch("psutil.process_iter")
    def test_find_daemon_not_found(self, mock_iter):
        """Should return None when no daemon process found."""
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "cmdline": ["python", "-m", "some_other_app"]}
        mock_iter.return_value = [mock_proc]

        result = find_daemon_process()
        assert result is None

    @patch("psutil.process_iter")
    def test_find_daemon_no_cmdline(self, mock_iter):
        """Should skip processes with empty cmdline."""
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "cmdline": []}
        mock_iter.return_value = [mock_proc]

        result = find_daemon_process()
        assert result is None

    @patch("psutil.process_iter")
    def test_find_daemon_access_denied(self, mock_iter):
        """Should handle AccessDenied exceptions gracefully."""
        # Create a mock process that raises AccessDenied when accessing info
        mock_proc = MagicMock()
        mock_proc.info.get.side_effect = psutil.AccessDenied()
        mock_iter.return_value = [mock_proc]

        # This should not raise an exception
        result = find_daemon_process()
        assert result is None


class TestStopDaemonGraceful:
    """Tests for stop_daemon_graceful function."""

    @patch("pysysfan.api.service_control.find_daemon_process")
    @patch("pysysfan.api.auth.load_token")
    @patch("requests.post")
    def test_stop_via_api_graceful(self, mock_post, mock_load_token, mock_find):
        """Should stop daemon via API when available."""
        mock_load_token.return_value = "test-token"
        mock_post.return_value.status_code = 200
        mock_find.return_value = None  # Process exits after API call

        success, method = stop_daemon_graceful()

        assert success is True
        assert method == StopMethod.GRACEFUL_API
        mock_post.assert_called_once()
        assert (
            mock_post.call_args.args[0] == "http://127.0.0.1:8765/api/service/shutdown"
        )

    @patch("pysysfan.api.service_control.find_daemon_process")
    @patch("pysysfan.api.auth.load_token")
    @patch("requests.post")
    def test_stop_uses_configured_api_host_and_port(
        self, mock_post, mock_load_token, mock_find
    ):
        """Should map wildcard bind hosts back to local loopback."""
        mock_load_token.return_value = "test-token"
        mock_post.return_value.status_code = 200
        mock_find.return_value = None

        success, method = stop_daemon_graceful(api_host="0.0.0.0", api_port=9000)

        assert success is True
        assert method == StopMethod.GRACEFUL_API
        assert (
            mock_post.call_args.args[0] == "http://127.0.0.1:9000/api/service/shutdown"
        )

    @patch("pysysfan.api.service_control.find_daemon_process")
    @patch("pysysfan.api.auth.load_token")
    @patch("requests.post")
    def test_stop_api_timeout_fallback_to_sigterm(
        self, mock_post, mock_load_token, mock_find
    ):
        """Should fall back to SIGTERM when API call times out."""
        mock_load_token.return_value = "test-token"
        mock_post.return_value.status_code = 200

        # Simulate daemon still running after timeout
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_find.side_effect = [
            mock_proc,
            mock_proc,
            None,
        ]  # Running, running, stopped

        success, method = stop_daemon_graceful(timeout=0.1)

        assert success is True
        # Either graceful_api (if exited) or sigterm
        assert method in [StopMethod.GRACEFUL_API, StopMethod.SIGTERM]

    @patch("pysysfan.api.service_control.find_daemon_process")
    @patch("pysysfan.api.auth.load_token")
    def test_stop_no_api_token(self, mock_load_token, mock_find):
        """Should fall back to SIGTERM when no API token."""
        mock_load_token.return_value = None

        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_find.return_value = mock_proc

        success, method = stop_daemon_graceful()

        assert success is True
        mock_proc.terminate.assert_called_once()

    @patch("pysysfan.api.service_control.find_daemon_process")
    def test_stop_sigterm_already_exited(self, mock_find):
        """Should handle NoSuchProcess during SIGTERM."""
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.terminate.side_effect = psutil.NoSuchProcess(1234)
        mock_find.return_value = mock_proc

        success, method = stop_daemon_graceful()

        assert success is True
        assert method == StopMethod.SIGTERM

    @patch("pysysfan.api.service_control.find_daemon_process")
    def test_stop_sigterm_timeout_fallback_to_kill(self, mock_find):
        """Should fall back to kill when SIGTERM times out."""
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        # First wait (SIGTERM) times out, second wait (kill) succeeds
        mock_proc.wait.side_effect = [psutil.TimeoutExpired(0.1), None]

        # First call finds for terminate, second for kill (still running)
        mock_find.return_value = mock_proc

        success, method = stop_daemon_graceful(timeout=0.1)

        assert success is True
        assert method == StopMethod.TASKKILL
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @patch("pysysfan.api.service_control.find_daemon_process")
    def test_stop_no_daemon_running(self, mock_find):
        """Should return success when no daemon found."""
        mock_find.return_value = None

        success, method = stop_daemon_graceful()

        assert success is True
        assert method == StopMethod.GRACEFUL_API

    @patch("pysysfan.api.service_control.find_daemon_process")
    def test_stop_force_kill_failure(self, mock_find):
        """Should return failed when all methods fail."""
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.terminate.side_effect = Exception("Terminate failed")
        mock_proc.kill.side_effect = Exception("Kill failed")
        mock_find.return_value = mock_proc

        success, method = stop_daemon_graceful()

        assert success is False
        assert method == StopMethod.FAILED


class TestGetRecentLogs:
    """Tests for get_recent_logs function."""

    @patch("pysysfan.api.service_control.Path.home")
    def test_get_logs_success(self, mock_home, tmp_path):
        """Should return recent log lines."""
        log_file = tmp_path / ".pysysfan" / "daemon.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\n")
        mock_home.return_value = tmp_path

        logs = get_recent_logs(lines=2)

        assert len(logs) == 2
        assert logs[0] == "Line 3"
        assert logs[1] == "Line 4"

    @patch("pysysfan.api.service_control.Path.home")
    def test_get_logs_file_not_found(self, mock_home, tmp_path):
        """Should return empty list when log file doesn't exist."""
        mock_home.return_value = tmp_path

        logs = get_recent_logs()

        assert logs == []

    @patch("pysysfan.api.service_control.Path.home")
    def test_get_logs_read_error(self, mock_home, tmp_path):
        """Should handle file read errors gracefully."""
        log_file = tmp_path / ".pysysfan" / "daemon.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("Test line")
        mock_home.return_value = tmp_path

        # Make file unreadable (Windows doesn't support chmod 000, so we mock)
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            logs = get_recent_logs()

        assert logs == []


class TestStopMethod:
    """Tests for StopMethod enum."""

    def test_stop_method_values(self):
        """StopMethod should have expected values."""
        assert StopMethod.GRACEFUL_API.value == "graceful_api"
        assert StopMethod.SIGTERM.value == "sigterm"
        assert StopMethod.TASKKILL.value == "taskkill"
        assert StopMethod.FAILED.value == "failed"


class TestBuildLocalAPIBaseURL:
    """Tests for build_local_api_base_url."""

    def test_preserves_specific_host(self):
        """Specific hosts should be used directly."""
        assert build_local_api_base_url("localhost", 8765) == "http://localhost:8765"

    def test_normalizes_wildcard_host(self):
        """Wildcard bind addresses should be converted to loopback."""
        assert build_local_api_base_url("0.0.0.0", 9000) == "http://127.0.0.1:9000"
