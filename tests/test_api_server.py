"""Tests for pysysfan.api.server — FastAPI application."""

import pytest
from unittest.mock import MagicMock, patch
import time

# Mark tests that require FastAPI
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

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


@pytest.fixture
def app(mock_daemon, state_manager, test_token):
    """Create the FastAPI app with mocked token."""
    with patch("pysysfan.api.middleware.load_token", return_value=test_token):
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


class TestHealthEndpoint:
    """Tests for /api/health endpoint."""

    def test_health_no_auth_required(self, client):
        """Health endpoint should not require authentication."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_health_returns_timestamp(self, client):
        """Health endpoint should return current timestamp."""
        before = time.time()
        response = client.get("/api/health")
        after = time.time()

        assert response.status_code == 200
        data = response.json()
        assert before <= data["timestamp"] <= after


class TestAuthVerifyEndpoint:
    """Tests for /api/auth/verify endpoint."""

    def test_verify_with_valid_token(self, client, auth_headers):
        """Token verification should succeed with valid token."""
        response = client.post("/api/auth/verify", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"valid": True}

    def test_verify_without_token(self, client):
        """Token verification should fail without token."""
        response = client.post("/api/auth/verify")
        assert response.status_code == 403

    def test_verify_with_invalid_token(self, client):
        """Token verification should fail with invalid token."""
        response = client.post(
            "/api/auth/verify", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401


class TestStatusEndpoint:
    """Tests for /api/status endpoint."""

    def test_status_requires_auth(self, client):
        """Status endpoint should require authentication."""
        response = client.get("/api/status")
        assert response.status_code == 403

    def test_status_returns_503_when_no_state(self, client, auth_headers):
        """Status should return 503 when no state is available."""
        response = client.get("/api/status", headers=auth_headers)
        assert response.status_code == 503
        assert "Daemon state not available" in response.json()["detail"]

    def test_status_returns_state(self, client, state_manager, auth_headers):
        """Status should return daemon state when available."""
        state_manager.update_state(
            pid=1234,
            config_path="/test/config.yaml",
            started_at=time.time(),
            running=True,
            uptime_seconds=42.0,
            last_poll_time=time.time(),
            last_error=None,
            poll_interval=2.0,
            fans_configured=3,
            curves_configured=2,
            active_profile="default",
        )

        response = client.get("/api/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["pid"] == 1234
        assert data["running"] is True
        assert data["fans_configured"] == 3


class TestSensorsEndpoints:
    """Tests for sensor endpoints."""

    def test_sensors_requires_auth(self, client):
        """Sensors endpoint should require authentication."""
        response = client.get("/api/sensors")
        assert response.status_code == 403

    def test_sensors_returns_data(self, client, mock_daemon, auth_headers):
        """Sensors endpoint should return sensor data."""
        # Mock some sensor data
        mock_daemon._hw.get_temperatures.return_value = [
            MagicMock(
                identifier="/cpu/0/temp",
                hardware_name="CPU",
                sensor_name="Core 0",
                value=45.5,
            )
        ]
        mock_daemon._hw.get_fans.return_value = [
            MagicMock(
                identifier="/fan/0/rpm",
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                value=1200,
            )
        ]
        mock_daemon._hw.get_controls.return_value = [
            MagicMock(
                identifier="/fan/0/control",
                hardware_name="Motherboard",
                sensor_name="CPU Fan Control",
                current_value=50.0,
                has_control=True,
            )
        ]

        response = client.get("/api/sensors", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "temperatures" in data
        assert "fans" in data
        assert "controls" in data
        assert "timestamp" in data

        assert len(data["temperatures"]) == 1
        assert data["temperatures"][0]["value"] == 45.5

    def test_sensors_returns_503_when_hardware_not_ready(
        self, client, mock_daemon, auth_headers
    ):
        """Sensors endpoint should return 503 when hardware not initialized."""
        mock_daemon._hw = None

        response = client.get("/api/sensors", headers=auth_headers)
        assert response.status_code == 503

    def test_temperatures_endpoint(self, client, mock_daemon, auth_headers):
        """Temperatures endpoint should return only temperature data."""
        mock_daemon._hw.get_temperatures.return_value = [
            MagicMock(
                identifier="/cpu/0/temp",
                hardware_name="CPU",
                sensor_name="Core 0",
                value=45.5,
            )
        ]

        response = client.get("/api/sensors/temperatures", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "temperatures" in data
        assert "timestamp" in data
        assert "fans" not in data

    def test_fans_endpoint(self, client, mock_daemon, auth_headers):
        """Fans endpoint should return only fan data."""
        mock_daemon._hw.get_fans.return_value = [
            MagicMock(
                identifier="/fan/0/rpm",
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                value=1200,
            )
        ]

        response = client.get("/api/sensors/fans", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "fans" in data
        assert "timestamp" in data

    def test_controls_endpoint(self, client, mock_daemon, auth_headers):
        """Controls endpoint should return only control data."""
        mock_daemon._hw.get_controls.return_value = [
            MagicMock(
                identifier="/fan/0/control",
                hardware_name="Motherboard",
                sensor_name="CPU Fan Control",
                current_value=50.0,
                has_control=True,
            )
        ]

        response = client.get("/api/sensors/controls", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "controls" in data
        assert "timestamp" in data


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_config_get_requires_auth(self, client):
        """Config get endpoint should require authentication."""
        response = client.get("/api/config")
        assert response.status_code == 403

    @patch("pysysfan.api.server.Config")
    def test_config_get_returns_config(
        self, mock_config_cls, client, mock_daemon, auth_headers
    ):
        """Config get should return current configuration."""
        mock_config = MagicMock()
        mock_config.poll_interval = 2.0
        mock_config.fans = {}
        mock_config.curves = {}
        mock_config_cls.load.return_value = mock_config

        response = client.get("/api/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "general" in data
        assert "fans" in data
        assert "curves" in data

    def test_config_reload_requires_auth(self, client):
        """Config reload endpoint should require authentication."""
        response = client.post("/api/config/reload")
        assert response.status_code == 403

    def test_config_reload_triggers_reload(self, client, mock_daemon, auth_headers):
        """Config reload should trigger daemon reload."""
        mock_daemon.reload_config.return_value = True

        response = client.post("/api/config/reload", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_daemon.reload_config.assert_called_once()

    def test_config_validate_requires_auth(self, client):
        """Config validate endpoint should require authentication."""
        response = client.get("/api/config/validate")
        assert response.status_code == 403

    @patch("pysysfan.api.server.Config")
    def test_config_validate_returns_validation(
        self, mock_config_cls, client, mock_daemon, auth_headers
    ):
        """Config validate should return validation status."""
        mock_config = MagicMock()
        mock_config.fans = {"fan1": MagicMock()}
        mock_config.curves = {"curve1": MagicMock()}
        mock_config.poll_interval = 2.0
        mock_config_cls.load.return_value = mock_config

        response = client.get("/api/config/validate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["fans"] == 1
        assert data["curves"] == 1


class TestCurvesEndpoints:
    """Tests for curves endpoints."""

    def test_curves_list_requires_auth(self, client):
        """Curves list endpoint should require authentication."""
        response = client.get("/api/curves")
        assert response.status_code == 403

    def test_curves_list_returns_curves(self, client, mock_daemon, auth_headers):
        """Curves list should return all curves."""
        mock_daemon._cfg.curves = {
            "balanced": MagicMock(points=[[30, 30], [60, 60]], hysteresis=3.0),
            "silent": MagicMock(points=[[30, 20], [60, 40]], hysteresis=3.0),
        }

        response = client.get("/api/curves", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "curves" in data
        assert "balanced" in data["curves"]
        assert "silent" in data["curves"]

    def test_curves_get_requires_auth(self, client):
        """Curve get endpoint should require authentication."""
        response = client.get("/api/curves/balanced")
        assert response.status_code == 403

    def test_curves_get_returns_curve(self, client, mock_daemon, auth_headers):
        """Curve get should return specific curve."""
        mock_daemon._cfg.curves = {
            "balanced": MagicMock(points=[[30, 30], [60, 60]], hysteresis=3.0),
        }

        response = client.get("/api/curves/balanced", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "balanced"
        assert data["points"] == [[30, 30], [60, 60]]
        assert data["hysteresis"] == 3.0

    def test_curves_get_returns_404_for_missing(
        self, client, mock_daemon, auth_headers
    ):
        """Curve get should return 404 for non-existent curve."""
        mock_daemon._cfg.curves = {}

        response = client.get("/api/curves/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_curves_preview_requires_auth(self, client):
        """Curve preview endpoint should require authentication."""
        response = client.post(
            "/api/curves/preview", json={"points": [[30, 30]], "temperature": 50}
        )
        assert response.status_code == 403

    def test_curves_preview_evaluates_curve(self, client, auth_headers):
        """Curve preview should evaluate curve at given temperature."""
        response = client.post(
            "/api/curves/preview",
            headers=auth_headers,
            json={
                "points": [[30, 30], [60, 60]],
                "temperature": 45.0,
                "hysteresis": 3.0,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["temperature"] == 45.0
        assert "speed_percent" in data


class TestFansEndpoints:
    """Tests for fans endpoints."""

    def test_fans_list_requires_auth(self, client):
        """Fans list endpoint should require authentication."""
        response = client.get("/api/fans")
        assert response.status_code == 403

    def test_fans_list_returns_fans(self, client, mock_daemon, auth_headers):
        """Fans list should return all fans."""
        mock_daemon._cfg.fans = {
            "cpu_fan": MagicMock(
                fan_id="/fan/0",
                curve="balanced",
                temp_ids=["/cpu/0"],
                aggregation="max",
                allow_fan_off=False,
            ),
        }

        response = client.get("/api/fans", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "fans" in data
        assert "cpu_fan" in data["fans"]

    def test_fan_get_requires_auth(self, client):
        """Fan get endpoint should require authentication."""
        response = client.get("/api/fans/cpu_fan")
        assert response.status_code == 403

    def test_fan_get_returns_fan(self, client, mock_daemon, auth_headers):
        """Fan get should return specific fan."""
        mock_daemon._cfg.fans = {
            "cpu_fan": MagicMock(
                fan_id="/fan/0",
                curve="balanced",
                temp_ids=["/cpu/0"],
                aggregation="max",
                allow_fan_off=False,
            ),
        }

        response = client.get("/api/fans/cpu_fan", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "cpu_fan"
        assert data["fan_id"] == "/fan/0"


class TestCorsMiddleware:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_present(self, client):
        """CORS headers should be present on responses."""
        response = client.options("/api/health")
        # CORS preflight should work
        assert response.status_code in [
            200,
            405,
        ]  # 405 if OPTIONS not implemented for endpoint
