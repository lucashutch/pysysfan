"""Tests for pysysfan API service endpoints."""

from unittest.mock import MagicMock, patch

import pytest

# Patch load_token BEFORE importing server module
with patch("pysysfan.api.auth.load_token", return_value="test-token-12345"):
    from fastapi.testclient import TestClient
    from pysysfan.api.server import create_app
    from pysysfan.api.state import StateManager


@pytest.fixture
def mock_daemon():
    """Create a mock daemon for testing."""
    daemon = MagicMock()
    daemon.config_path = "/tmp/config.yaml"
    daemon._cfg = MagicMock()
    daemon._cfg.poll_interval = 2.0
    daemon._cfg.fans = {}
    daemon._cfg.curves = {}
    daemon._hw = MagicMock()
    daemon._hw.get_temperatures.return_value = []
    daemon._hw.get_fans.return_value = []
    daemon._hw.get_controls.return_value = []
    return daemon


@pytest.fixture
def state_manager():
    """Create a state manager for testing."""
    return StateManager()


@pytest.fixture
def test_token():
    """Test token for authentication."""
    return "test-token-12345"


@pytest.fixture(autouse=True)
def mock_token_for_all_tests(test_token):
    """Mock load_token for all tests in this module."""
    with patch("pysysfan.api.middleware.load_token", return_value=test_token):
        yield


@pytest.fixture
def app(mock_daemon, state_manager, test_token):
    """Create the FastAPI app with mocked token."""
    app = create_app(mock_daemon, state_manager)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers(test_token):
    """Return authorization headers."""
    return {"Authorization": f"Bearer {test_token}"}


class TestServiceStatusEndpoint:
    """Tests for /api/service/status endpoint."""

    @patch("pysysfan.api.server.windows_service.get_task_status")
    @patch("pysysfan.api.server.windows_service.get_task_details")
    @patch("pysysfan.api.server.find_daemon_process")
    def test_get_service_status_not_installed(
        self, mock_find, mock_details, mock_status, client, auth_headers
    ):
        """Should return task_installed=False when task not found."""
        mock_status.return_value = None
        mock_details.return_value = None
        mock_find.return_value = None

        response = client.get("/api/service/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["task_installed"] is False
        assert data["daemon_running"] is False

    @patch("pysysfan.api.server.windows_service.get_task_status")
    @patch("pysysfan.api.server.windows_service.get_task_details")
    @patch("pysysfan.api.server.find_daemon_process")
    def test_get_service_status_installed(
        self, mock_find, mock_details, mock_status, client, auth_headers
    ):
        """Should return full status when task installed."""
        mock_status.return_value = "Ready"
        mock_details.return_value = {
            "Status": "Ready",
            "Last Run Time": "01/01/2026 12:00:00 PM",
        }
        mock_find.return_value = None

        response = client.get("/api/service/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["task_installed"] is True
        assert data["task_status"] == "Ready"
        assert data["task_enabled"] is True

    @patch("pysysfan.api.server.windows_service.get_task_status")
    @patch("pysysfan.api.server.windows_service.get_task_details")
    @patch("pysysfan.api.server.find_daemon_process")
    def test_get_service_status_daemon_running(
        self, mock_find, mock_details, mock_status, client, auth_headers
    ):
        """Should detect running daemon process."""
        mock_status.return_value = "Running"
        mock_details.return_value = {"Status": "Running"}

        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_find.return_value = mock_proc

        response = client.get("/api/service/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["daemon_running"] is True
        assert data["daemon_pid"] == 1234

    def test_get_service_status_requires_auth(self, client):
        """Status endpoint should require authentication."""
        response = client.get("/api/service/status")
        assert response.status_code == 401


class TestServiceInstallEndpoint:
    """Tests for /api/service/install endpoint."""

    @patch("pysysfan.api.server.windows_service.install_task")
    def test_install_service(self, mock_install, client, auth_headers):
        """Should install service successfully."""
        response = client.post(
            "/api/service/install",
            headers=auth_headers,
            json={"config_path": "/path/to/config.yaml"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_install.assert_called_once()

    @patch("pysysfan.api.server.windows_service.install_task")
    def test_install_service_config_not_found(self, mock_install, client, auth_headers):
        """Should return 404 when config not found."""
        mock_install.side_effect = FileNotFoundError("Config not found")

        response = client.post("/api/service/install", headers=auth_headers)
        assert response.status_code == 404

    @patch("pysysfan.api.server.windows_service.install_task")
    def test_install_service_failure(self, mock_install, client, auth_headers):
        """Should return 500 on install failure."""
        mock_install.side_effect = RuntimeError("schtasks failed")

        response = client.post("/api/service/install", headers=auth_headers)
        assert response.status_code == 500

    def test_install_service_requires_auth(self, client):
        """Install endpoint should require authentication."""
        response = client.post("/api/service/install")
        assert response.status_code == 401


class TestServiceUninstallEndpoint:
    """Tests for /api/service/uninstall endpoint."""

    @patch("pysysfan.api.server.windows_service.uninstall_task")
    def test_uninstall_service(self, mock_uninstall, client, auth_headers):
        """Should uninstall service successfully."""
        response = client.post("/api/service/uninstall", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_uninstall.assert_called_once()

    @patch("pysysfan.api.server.windows_service.uninstall_task")
    def test_uninstall_service_not_installed(
        self, mock_uninstall, client, auth_headers
    ):
        """Should return 404 when service not installed."""
        mock_uninstall.side_effect = FileNotFoundError("Not installed")

        response = client.post("/api/service/uninstall", headers=auth_headers)
        assert response.status_code == 404

    @patch("pysysfan.api.server.windows_service.uninstall_task")
    def test_uninstall_service_failure(self, mock_uninstall, client, auth_headers):
        """Should return 500 on uninstall failure."""
        mock_uninstall.side_effect = RuntimeError("schtasks failed")

        response = client.post("/api/service/uninstall", headers=auth_headers)
        assert response.status_code == 500

    def test_uninstall_service_requires_auth(self, client):
        """Uninstall endpoint should require authentication."""
        response = client.post("/api/service/uninstall")
        assert response.status_code == 401


class TestServiceEnableEndpoint:
    """Tests for /api/service/enable endpoint."""

    @patch("pysysfan.api.server.windows_service.enable_task")
    def test_enable_service(self, mock_enable, client, auth_headers):
        """Should enable service successfully."""
        response = client.post("/api/service/enable", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_enable.assert_called_once()

    @patch("pysysfan.api.server.windows_service.enable_task")
    def test_enable_service_not_installed(self, mock_enable, client, auth_headers):
        """Should return 404 when service not installed."""
        mock_enable.side_effect = FileNotFoundError("Not installed")

        response = client.post("/api/service/enable", headers=auth_headers)
        assert response.status_code == 404

    @patch("pysysfan.api.server.windows_service.enable_task")
    def test_enable_service_failure(self, mock_enable, client, auth_headers):
        """Should return 500 on enable failure."""
        mock_enable.side_effect = RuntimeError("schtasks failed")

        response = client.post("/api/service/enable", headers=auth_headers)
        assert response.status_code == 500

    def test_enable_service_requires_auth(self, client):
        """Enable endpoint should require authentication."""
        response = client.post("/api/service/enable")
        assert response.status_code == 401


class TestServiceDisableEndpoint:
    """Tests for /api/service/disable endpoint."""

    @patch("pysysfan.api.server.windows_service.disable_task")
    def test_disable_service(self, mock_disable, client, auth_headers):
        """Should disable service successfully."""
        response = client.post("/api/service/disable", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_disable.assert_called_once()

    @patch("pysysfan.api.server.windows_service.disable_task")
    def test_disable_service_not_installed(self, mock_disable, client, auth_headers):
        """Should return 404 when service not installed."""
        mock_disable.side_effect = FileNotFoundError("Not installed")

        response = client.post("/api/service/disable", headers=auth_headers)
        assert response.status_code == 404

    @patch("pysysfan.api.server.windows_service.disable_task")
    def test_disable_service_failure(self, mock_disable, client, auth_headers):
        """Should return 500 on disable failure."""
        mock_disable.side_effect = RuntimeError("schtasks failed")

        response = client.post("/api/service/disable", headers=auth_headers)
        assert response.status_code == 500

    def test_disable_service_requires_auth(self, client):
        """Disable endpoint should require authentication."""
        response = client.post("/api/service/disable")
        assert response.status_code == 401


class TestServiceStartEndpoint:
    """Tests for /api/service/start endpoint."""

    @patch("pysysfan.api.server.find_daemon_process")
    @patch("pysysfan.api.server.windows_service.start_task")
    def test_start_service(self, mock_start, mock_find, client, auth_headers):
        """Should start service successfully."""
        mock_find.return_value = None  # Not running

        response = client.post("/api/service/start", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_start.assert_called_once()

    @patch("pysysfan.api.server.find_daemon_process")
    @patch("pysysfan.api.server.windows_service.start_task")
    def test_start_service_already_running(
        self, mock_start, mock_find, client, auth_headers
    ):
        """Should return success when already running."""
        mock_find.return_value = MagicMock(pid=1234)

        response = client.post("/api/service/start", headers=auth_headers)
        assert response.status_code == 200
        assert "already running" in response.json()["message"]
        mock_start.assert_not_called()

    @patch("pysysfan.api.server.find_daemon_process")
    @patch("pysysfan.api.server.windows_service.start_task")
    def test_start_service_not_installed(
        self, mock_start, mock_find, client, auth_headers
    ):
        """Should return 404 when service not installed."""
        mock_find.return_value = None
        mock_start.side_effect = FileNotFoundError("Not installed")

        response = client.post("/api/service/start", headers=auth_headers)
        assert response.status_code == 404

    def test_start_service_requires_auth(self, client):
        """Start endpoint should require authentication."""
        response = client.post("/api/service/start")
        assert response.status_code == 401


class TestServiceStopEndpoint:
    """Tests for /api/service/stop endpoint."""

    @patch("pysysfan.api.server.stop_daemon_graceful")
    def test_stop_service(self, mock_stop, client, auth_headers):
        """Should stop service successfully."""
        from pysysfan.api.service_control import StopMethod

        mock_stop.return_value = (True, StopMethod.GRACEFUL_API)

        response = client.post("/api/service/stop", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["method"] == "graceful_api"

    @patch("pysysfan.api.server.stop_daemon_graceful")
    def test_stop_service_failure(self, mock_stop, client, auth_headers):
        """Should return 500 when stop fails."""
        from pysysfan.api.service_control import StopMethod

        mock_stop.return_value = (False, StopMethod.FAILED)

        response = client.post("/api/service/stop", headers=auth_headers)
        assert response.status_code == 500

    def test_stop_service_requires_auth(self, client):
        """Stop endpoint should require authentication."""
        response = client.post("/api/service/stop")
        assert response.status_code == 401


class TestServiceRestartEndpoint:
    """Tests for /api/service/restart endpoint."""

    @patch("pysysfan.api.server.stop_daemon_graceful")
    @patch("pysysfan.api.server.windows_service.start_task")
    def test_restart_service(self, mock_start, mock_stop, client, auth_headers):
        """Should restart service successfully."""
        from pysysfan.api.service_control import StopMethod

        mock_stop.return_value = (True, StopMethod.GRACEFUL_API)

        response = client.post("/api/service/restart", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_stop.assert_called_once()
        mock_start.assert_called_once()

    @patch("pysysfan.api.server.stop_daemon_graceful")
    def test_restart_service_stop_failure(self, mock_stop, client, auth_headers):
        """Should return 500 when stop fails."""
        from pysysfan.api.service_control import StopMethod

        mock_stop.return_value = (False, StopMethod.FAILED)

        response = client.post("/api/service/restart", headers=auth_headers)
        assert response.status_code == 500

    @patch("pysysfan.api.server.stop_daemon_graceful")
    @patch("pysysfan.api.server.windows_service.start_task")
    def test_restart_service_not_installed(
        self, mock_start, mock_stop, client, auth_headers
    ):
        """Should return 404 when service not installed."""
        from pysysfan.api.service_control import StopMethod

        mock_stop.return_value = (True, StopMethod.GRACEFUL_API)
        mock_start.side_effect = FileNotFoundError("Not installed")

        response = client.post("/api/service/restart", headers=auth_headers)
        assert response.status_code == 404

    def test_restart_service_requires_auth(self, client):
        """Restart endpoint should require authentication."""
        response = client.post("/api/service/restart")
        assert response.status_code == 401


class TestServiceLogsEndpoint:
    """Tests for /api/service/logs endpoint."""

    @patch("pysysfan.api.server.get_recent_logs")
    def test_get_logs(self, mock_logs, client, auth_headers):
        """Should return logs successfully."""
        mock_logs.return_value = ["Line 1", "Line 2", "Line 3"]

        response = client.get("/api/service/logs?lines=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == ["Line 1", "Line 2", "Line 3"]
        assert data["total_lines"] == 3

    @patch("pysysfan.api.server.get_recent_logs")
    def test_get_logs_default_lines(self, mock_logs, client, auth_headers):
        """Should use default lines parameter."""
        mock_logs.return_value = []

        response = client.get("/api/service/logs", headers=auth_headers)
        assert response.status_code == 200
        mock_logs.assert_called_once_with(100)  # Default value

    def test_get_logs_requires_auth(self, client):
        """Logs endpoint should require authentication."""
        response = client.get("/api/service/logs")
        assert response.status_code == 401


class TestServiceShutdownEndpoint:
    """Tests for /api/service/shutdown endpoint."""

    def test_shutdown_service(self, client, mock_daemon, auth_headers):
        """Should shutdown daemon successfully."""
        mock_daemon.stop = MagicMock()

        response = client.post("/api/service/shutdown", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_daemon.stop.assert_called_once()

    def test_shutdown_service_requires_auth(self, client):
        """Shutdown endpoint should require authentication."""
        response = client.post("/api/service/shutdown")
        assert response.status_code == 401
