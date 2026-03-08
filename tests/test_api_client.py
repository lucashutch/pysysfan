"""Tests for pysysfan.api.client — Python API client."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from pysysfan.api.client import PySysFanClient


@pytest.fixture
def test_token():
    """Test token."""
    return "test-token-12345"


@pytest.fixture
def mock_home_dir(test_token, tmp_path):
    """Create a mock home directory with token file."""
    pysysfan_dir = tmp_path / ".pysysfan"
    pysysfan_dir.mkdir()
    token_file = pysysfan_dir / "api_token"
    token_file.write_text(test_token)
    return tmp_path


@pytest.fixture
def client(mock_home_dir):
    """Create a test client."""
    with patch.object(Path, "home", return_value=mock_home_dir):
        return PySysFanClient(base_url="http://localhost:8765")


class TestClientInitialization:
    """Tests for PySysFanClient initialization."""

    def test_loads_token_from_file(self, mock_home_dir):
        """Client should load token from default file location."""
        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient()
            assert client.token == "test-token-12345"

    def test_uses_provided_token(self):
        """Client should use provided token instead of loading from file."""
        client = PySysFanClient(token="custom-token")
        assert client.token == "custom-token"

    def test_raises_error_when_token_not_found(self, tmp_path):
        """Client should raise FileNotFoundError when token file missing."""
        with patch.object(Path, "home", return_value=tmp_path):
            with pytest.raises(FileNotFoundError) as exc_info:
                PySysFanClient()
            assert "API token not found" in str(exc_info.value)

    def test_strips_whitespace_from_token(self, tmp_path):
        """Client should strip whitespace from token file."""
        pysysfan_dir = tmp_path / ".pysysfan"
        pysysfan_dir.mkdir()
        token_file = pysysfan_dir / "api_token"
        token_file.write_text("  token-with-spaces  \n")

        with patch.object(Path, "home", return_value=tmp_path):
            client = PySysFanClient()
            assert client.token == "token-with-spaces"


class TestClientHeaders:
    """Tests for request headers."""

    def test_auth_header_format(self):
        """Authorization header should be Bearer format."""
        client = PySysFanClient(token="my-token")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer my-token"


class TestHealthEndpoint:
    """Tests for health check."""

    @patch("pysysfan.api.client.requests.get")
    def test_health_no_auth_required(self, mock_get, mock_home_dir):
        """Health check should not require authentication."""
        mock_get.return_value.json.return_value = {"status": "ok"}

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            result = client.health()

        mock_get.assert_called_once_with("http://localhost:8765/api/health")
        assert result["status"] == "ok"


class TestTokenVerification:
    """Tests for token verification."""

    @patch("pysysfan.api.client.requests.request")
    def test_verify_token_sends_post(self, mock_request, mock_home_dir):
        """Token verification should send POST request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"valid": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            result = client.verify_token()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/auth/verify" in call_args[0][1]
        assert result["valid"] is True


class TestStatusEndpoints:
    """Tests for status endpoints."""

    @patch("pysysfan.api.client.requests.request")
    def test_get_status_sends_get(self, mock_request, mock_home_dir):
        """Get status should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"pid": 1234, "running": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            result = client.get_status()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/status" in call_args[0][1]
        assert result["pid"] == 1234

    @patch("pysysfan.api.client.requests.get")
    def test_is_daemon_running_true_when_healthy(self, mock_get, mock_home_dir):
        """is_daemon_running should return True when health check succeeds."""
        mock_get.return_value.json.return_value = {"status": "ok"}

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            assert client.is_daemon_running() is True

    @patch("pysysfan.api.client.requests.get")
    def test_is_daemon_running_false_on_error(self, mock_get, mock_home_dir):
        """is_daemon_running should return False when health check fails."""
        from requests import RequestException

        mock_get.side_effect = RequestException("Connection refused")

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            assert client.is_daemon_running() is False

    @patch("pysysfan.api.client.requests.request")
    def test_is_authenticated_true_when_valid(self, mock_request, mock_home_dir):
        """is_authenticated should return True when token is valid."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"valid": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            assert client.is_authenticated() is True

    @patch("pysysfan.api.client.requests.request")
    def test_is_authenticated_false_on_error(self, mock_request, mock_home_dir):
        """is_authenticated should return False when token invalid."""
        from requests import RequestException

        mock_request.side_effect = RequestException("Unauthorized")

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            assert client.is_authenticated() is False


class TestSensorEndpoints:
    """Tests for sensor endpoints."""

    @patch("pysysfan.api.client.requests.request")
    def test_get_sensors_sends_get(self, mock_request, mock_home_dir):
        """Get sensors should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "temperatures": [],
            "fans": [],
            "controls": [],
        }
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            result = client.get_sensors()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/sensors" in call_args[0][1]
        assert "temperatures" in result

    @patch("pysysfan.api.client.requests.request")
    def test_get_temperatures_sends_get(self, mock_request, mock_home_dir):
        """Get temperatures should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"temperatures": []}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.get_temperatures()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/sensors/temperatures" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_get_fans_sends_get(self, mock_request, mock_home_dir):
        """Get fans should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"fans": []}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.get_fans()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/sensors/fans" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_get_controls_sends_get(self, mock_request, mock_home_dir):
        """Get controls should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"controls": []}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.get_controls()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/sensors/controls" in call_args[0][1]


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    @patch("pysysfan.api.client.requests.request")
    def test_get_config_sends_get(self, mock_request, mock_home_dir):
        """Get config should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"general": {}, "fans": {}, "curves": {}}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.get_config()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/config" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_update_config_sends_put(self, mock_request, mock_home_dir):
        """Update config should send PUT request with JSON body."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            config = {"general": {"poll_interval": 2.0}}
            client.update_config(config)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "PUT"
        assert "/api/config" in call_args[0][1]
        assert call_args[1]["json"] == config

    @patch("pysysfan.api.client.requests.request")
    def test_reload_config_sends_post(self, mock_request, mock_home_dir):
        """Reload config should send POST request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.reload_config()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/config/reload" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_validate_config_sends_get(self, mock_request, mock_home_dir):
        """Validate config should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"valid": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.validate_config()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/config/validate" in call_args[0][1]


class TestCurvesEndpoints:
    """Tests for curves endpoints."""

    @patch("pysysfan.api.client.requests.request")
    def test_list_curves_sends_get(self, mock_request, mock_home_dir):
        """List curves should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"curves": {}}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.list_curves()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/curves" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_get_curve_sends_get(self, mock_request, mock_home_dir):
        """Get curve should send GET request with curve name."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"name": "balanced", "points": []}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.get_curve("balanced")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/curves/balanced" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_create_curve_sends_post(self, mock_request, mock_home_dir):
        """Create curve should send POST request with curve data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            points = [[30, 30], [60, 60]]
            client.create_curve("test", points, hysteresis=3.0)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/curves/test" in call_args[0][1]
        assert call_args[1]["json"]["points"] == points
        assert call_args[1]["json"]["hysteresis"] == 3.0

    @patch("pysysfan.api.client.requests.request")
    def test_delete_curve_sends_delete(self, mock_request, mock_home_dir):
        """Delete curve should send DELETE request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.delete_curve("old_curve")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "DELETE"
        assert "/api/curves/old_curve" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_preview_curve_sends_post(self, mock_request, mock_home_dir):
        """Preview curve should send POST request with curve data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"temperature": 50.0, "speed_percent": 60.0}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            points = [[30, 30], [60, 60]]
            client.preview_curve(points, temperature=45.0)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/curves/preview" in call_args[0][1]


class TestFansEndpoints:
    """Tests for fans endpoints."""

    @patch("pysysfan.api.client.requests.request")
    def test_list_fans_sends_get(self, mock_request, mock_home_dir):
        """List fans should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"fans": {}}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.list_fans()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/fans" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_get_fan_sends_get(self, mock_request, mock_home_dir):
        """Get fan should send GET request with fan name."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"name": "cpu_fan"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.get_fan("cpu_fan")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/fans/cpu_fan" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_update_fan_sends_put(self, mock_request, mock_home_dir):
        """Update fan should send PUT request with fan data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.update_fan("cpu_fan", curve="performance", aggregation="max")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "PUT"
        assert "/api/fans/cpu_fan" in call_args[0][1]
        assert call_args[1]["json"]["curve"] == "performance"
        assert call_args[1]["json"]["aggregation"] == "max"

    @patch("pysysfan.api.client.requests.request")
    def test_override_fan_sends_post(self, mock_request, mock_home_dir):
        """Override fan should send POST request with speed data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.override_fan("cpu_fan", speed_percent=75.0, duration_seconds=30)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/fans/cpu_fan/override" in call_args[0][1]
        assert call_args[1]["json"]["speed_percent"] == 75.0
        assert call_args[1]["json"]["duration_seconds"] == 30


class TestServiceEndpoints:
    """Tests for service management endpoints."""

    @patch("pysysfan.api.client.requests.request")
    def test_get_service_status_sends_get(self, mock_request, mock_home_dir):
        """Service status should send GET request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"task_installed": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.get_service_status()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/service/status" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_install_service_passes_optional_config_path(
        self, mock_request, mock_home_dir
    ):
        """Service install should send the optional config path as query params."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.install_service("/tmp/config.yaml")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/service/install" in call_args[0][1]
        assert call_args[1]["params"] == {"config_path": "/tmp/config.yaml"}

    @patch("pysysfan.api.client.requests.request")
    def test_stop_service_sends_post(self, mock_request, mock_home_dir):
        """Service stop should send POST request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "method": "sigterm"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.stop_service()

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert "/api/service/stop" in call_args[0][1]

    @patch("pysysfan.api.client.requests.request")
    def test_get_service_logs_passes_line_count(self, mock_request, mock_home_dir):
        """Service logs should send the requested line count as query params."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"logs": [], "total_lines": 0}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        with patch.object(Path, "home", return_value=mock_home_dir):
            client = PySysFanClient(base_url="http://localhost:8765")
            client.get_service_logs(250)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/api/service/logs" in call_args[0][1]
        assert call_args[1]["params"] == {"lines": 250}


class TestClientBaseUrl:
    """Tests for base URL handling."""

    def test_trailing_slash_removed(self):
        """Trailing slash should be removed from base_url."""
        client = PySysFanClient(base_url="http://localhost:8765/", token="test")
        assert client.base_url == "http://localhost:8765"
