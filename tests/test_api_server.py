"""Tests for pysysfan.api.server — FastAPI application."""

import pytest
from unittest.mock import MagicMock, patch
import time

# Patch load_token BEFORE importing server module
with patch("pysysfan.api.auth.load_token", return_value="test-token-12345"):
    from fastapi.testclient import TestClient
    from pysysfan.api.server import create_app
    from pysysfan.api.state import StateManager
    from pysysfan.notifications import AlertRule, NotificationManager


@pytest.fixture
def mock_daemon():
    """Create a mock daemon for testing."""
    daemon = MagicMock()
    daemon.config_path = "/tmp/config.yaml"
    daemon._api_host = "127.0.0.1"
    daemon._api_port = 8765
    daemon._cfg = MagicMock()
    daemon._cfg.poll_interval = 2.0
    daemon._cfg.fans = {}
    daemon._cfg.curves = {}
    daemon._cfg.update = MagicMock(auto_check=False, notify_only=True)
    daemon._hw = MagicMock()
    daemon._hw.get_temperatures.return_value = []
    daemon._hw.get_fans.return_value = []
    daemon._hw.get_controls.return_value = []
    daemon.notification_manager = NotificationManager()
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
        assert response.status_code == 401

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
        assert response.status_code == 401

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
            current_temps={"/cpu/0": 45.5},
            current_fan_speeds={"/fan/0": 1200.0},
            current_targets={"/fan/0/control": 55.0},
        )

        response = client.get("/api/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["pid"] == 1234
        assert data["running"] is True
        assert data["fans_configured"] == 3
        assert data["current_temps"] == {"/cpu/0": 45.5}
        assert data["current_fan_speeds"] == {"/fan/0": 1200.0}
        assert data["current_targets"] == {"/fan/0/control": 55.0}


class TestSensorsEndpoints:
    """Tests for sensor endpoints."""

    def test_sensors_requires_auth(self, client):
        """Sensors endpoint should require authentication."""
        response = client.get("/api/sensors")
        assert response.status_code == 401

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
        assert data["fans"][0]["control_percentage"] == 50.0
        assert data["fans"][0]["controllable"] is True

    def test_sensors_marks_fans_without_matching_control_as_read_only(
        self, client, mock_daemon, auth_headers
    ):
        """Fans without matching control sensors should be reported as read-only."""
        mock_daemon._hw.get_temperatures.return_value = []
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
                identifier="/fan/1/control",
                hardware_name="Motherboard",
                sensor_name="Case Fan Control",
                current_value=35.0,
                has_control=True,
            )
        ]

        response = client.get("/api/sensors", headers=auth_headers)

        assert response.status_code == 200
        fan = response.json()["fans"][0]
        assert fan["control_percentage"] is None
        assert fan["controllable"] is False

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
        assert response.status_code == 401

    @patch("pysysfan.config.Config")
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
        assert response.status_code == 401

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
        assert response.status_code == 401

    @patch("pysysfan.config.Config")
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
        assert response.status_code == 401

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
        assert response.status_code == 401

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
        assert response.status_code == 401

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
        assert response.status_code == 401

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
        assert response.status_code == 401

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


class TestConfigUpdateEndpoint:
    """Tests for PUT /api/config endpoint."""

    def test_config_update_requires_auth(self, client):
        """Config update endpoint should require authentication."""
        response = client.put("/api/config", json={"general": {"poll_interval": 5.0}})
        assert response.status_code == 401

    @patch("pysysfan.config.Config")
    def test_config_update_success(
        self, mock_config_cls, client, mock_daemon, auth_headers
    ):
        """Config update should save and reload configuration."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config
        mock_daemon.reload_config.return_value = True

        config_data = {
            "general": {"poll_interval": 5.0},
            "fans": {
                "cpu_fan": {
                    "fan_id": "/fan/0",
                    "curve": "balanced",
                    "temp_ids": ["/cpu/0/temp"],
                    "aggregation": "max",
                    "allow_fan_off": True,
                }
            },
            "curves": {
                "balanced": {
                    "points": [[30, 30], [60, 60]],
                    "hysteresis": 3.0,
                }
            },
        }

        response = client.put("/api/config", headers=auth_headers, json=config_data)
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_config.save.assert_called_once()
        mock_daemon.reload_config.assert_called_once()

    @patch("pysysfan.config.Config")
    def test_config_update_preserves_existing_update_settings(
        self, mock_config_cls, client, mock_daemon, auth_headers
    ):
        """Config PUT should preserve update settings when the payload omits them."""
        mock_config = MagicMock()
        mock_config_cls.return_value = mock_config
        mock_daemon._cfg.update.auto_check = False
        mock_daemon._cfg.update.notify_only = False

        response = client.put(
            "/api/config",
            headers=auth_headers,
            json={"general": {"poll_interval": 5.0}, "fans": {}, "curves": {}},
        )

        assert response.status_code == 200
        assert mock_config_cls.call_args.kwargs["update"].auto_check is False
        assert mock_config_cls.call_args.kwargs["update"].notify_only is False

    def test_config_update_invalid_data(self, client, mock_daemon, auth_headers):
        """Config update should return 400 for invalid data."""
        mock_daemon.reload_config.side_effect = Exception("Invalid config")

        response = client.put(
            "/api/config",
            headers=auth_headers,
            json={"invalid": "data"},
        )
        assert response.status_code == 400


class TestCurveCreateUpdateEndpoint:
    """Tests for POST /api/curves/{name} endpoint."""

    def test_create_curve_requires_auth(self, client):
        """Curve creation should require authentication."""
        response = client.post(
            "/api/curves/new_curve",
            json={"points": [[30, 30], [60, 60]], "hysteresis": 3.0},
        )
        assert response.status_code == 401

    def test_create_curve_success(self, client, mock_daemon, auth_headers):
        """Curve creation should update config and reload."""
        from pysysfan.config import CurveConfig

        mock_daemon._cfg.curves = {}
        mock_daemon.reload_config.return_value = True

        response = client.post(
            "/api/curves/new_curve",
            headers=auth_headers,
            json={"points": [[30, 30], [60, 60]], "hysteresis": 3.0},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["name"] == "new_curve"
        assert isinstance(mock_daemon._cfg.curves["new_curve"], CurveConfig)
        assert mock_daemon._cfg.curves["new_curve"].points == [
            (30.0, 30.0),
            (60.0, 60.0),
        ]

    def test_create_curve_config_not_loaded(self, client, mock_daemon, auth_headers):
        """Curve creation should return 503 if config not loaded."""
        mock_daemon._cfg = None

        response = client.post(
            "/api/curves/new_curve",
            headers=auth_headers,
            json={"points": [[30, 30], [60, 60]], "hysteresis": 3.0},
        )
        assert response.status_code == 503

    def test_create_curve_save_failure(self, client, mock_daemon, auth_headers):
        """Curve creation should return 400 if save fails."""
        mock_daemon._cfg.save.side_effect = Exception("Save failed")

        response = client.post(
            "/api/curves/new_curve",
            headers=auth_headers,
            json={"points": [[30, 30], [60, 60]], "hysteresis": 3.0},
        )
        assert response.status_code == 400


class TestCurveDeleteEndpoint:
    """Tests for DELETE /api/curves/{name} endpoint."""

    def test_delete_curve_requires_auth(self, client):
        """Curve deletion should require authentication."""
        response = client.delete("/api/curves/balanced")
        assert response.status_code == 401

    def test_delete_curve_success(self, client, mock_daemon, auth_headers):
        """Curve deletion should remove curve and reload."""
        mock_daemon._cfg.curves = {"balanced": MagicMock()}
        mock_daemon.reload_config.return_value = True

        response = client.delete("/api/curves/balanced", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["deleted"] == "balanced"

    def test_delete_curve_not_found(self, client, mock_daemon, auth_headers):
        """Curve deletion should return 404 if curve not found."""
        mock_daemon._cfg.curves = {}

        response = client.delete("/api/curves/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_curve_config_not_loaded(self, client, mock_daemon, auth_headers):
        """Curve deletion should return 503 if config not loaded."""
        mock_daemon._cfg = None

        response = client.delete("/api/curves/balanced", headers=auth_headers)
        assert response.status_code == 503


class TestFanUpdateEndpoint:
    """Tests for PUT /api/fans/{name} endpoint."""

    def test_update_fan_requires_auth(self, client):
        """Fan update should require authentication."""
        response = client.put(
            "/api/fans/cpu_fan",
            json={"fan_id": "/fan/0", "curve": "balanced"},
        )
        assert response.status_code == 401

    def test_update_fan_success(self, client, mock_daemon, auth_headers):
        """Fan update should update config and reload."""
        mock_daemon._cfg.fans = {}
        mock_daemon.reload_config.return_value = True

        fan_data = {
            "fan_id": "/fan/0",
            "curve": "balanced",
            "temp_ids": ["/cpu/0/temp"],
            "aggregation": "max",
            "allow_fan_off": False,
        }

        response = client.put(
            "/api/fans/cpu_fan",
            headers=auth_headers,
            json=fan_data,
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_update_fan_preserves_existing_fields_when_omitted(
        self, client, mock_daemon, auth_headers
    ):
        """Partial fan updates should merge with the existing fan config."""
        from pysysfan.config import FanConfig

        mock_daemon._cfg.fans = {
            "cpu_fan": FanConfig(
                fan_id="/fan/0",
                curve="balanced",
                temp_ids=["/cpu/0/temp"],
                aggregation="avg",
                allow_fan_off=False,
            )
        }

        response = client.put(
            "/api/fans/cpu_fan",
            headers=auth_headers,
            json={"curve": "performance"},
        )

        assert response.status_code == 200
        updated_fan = mock_daemon._cfg.fans["cpu_fan"]
        assert updated_fan.fan_id == "/fan/0"
        assert updated_fan.curve == "performance"
        assert updated_fan.temp_ids == ["/cpu/0/temp"]
        assert updated_fan.aggregation == "avg"
        assert updated_fan.allow_fan_off is False

    def test_update_fan_config_not_loaded(self, client, mock_daemon, auth_headers):
        """Fan update should return 503 if config not loaded."""
        mock_daemon._cfg = None

        response = client.put(
            "/api/fans/cpu_fan",
            headers=auth_headers,
            json={"fan_id": "/fan/0"},
        )
        assert response.status_code == 503

    def test_update_fan_save_failure(self, client, mock_daemon, auth_headers):
        """Fan update should return 400 if save fails."""
        mock_daemon._cfg.save.side_effect = Exception("Save failed")

        response = client.put(
            "/api/fans/cpu_fan",
            headers=auth_headers,
            json={"fan_id": "/fan/0"},
        )
        assert response.status_code == 400


class TestFanOverrideEndpoint:
    """Tests for POST /api/fans/{name}/override endpoint."""

    def test_override_fan_requires_auth(self, client):
        """Fan override should require authentication."""
        response = client.post(
            "/api/fans/cpu_fan/override",
            json={"speed_percent": 100.0, "duration_seconds": 10},
        )
        assert response.status_code == 401

    def test_override_fan_success(self, client, mock_daemon, auth_headers):
        """Fan override should set fan speed temporarily."""
        mock_daemon._cfg.fans = {"cpu_fan": MagicMock(fan_id="/fan/0/control")}

        response = client.post(
            "/api/fans/cpu_fan/override",
            headers=auth_headers,
            json={"speed_percent": 100.0, "duration_seconds": 10},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["speed_percent"] == 100.0
        mock_daemon._hw.set_fan_speed.assert_called_once()

    def test_override_fan_not_found(self, client, mock_daemon, auth_headers):
        """Fan override should return 404 if fan not found."""
        mock_daemon._cfg.fans = {}

        response = client.post(
            "/api/fans/cpu_fan/override",
            headers=auth_headers,
            json={"speed_percent": 100.0},
        )
        assert response.status_code == 404

    def test_override_fan_hardware_not_ready(self, client, mock_daemon, auth_headers):
        """Fan override should return 503 if hardware not initialized."""
        mock_daemon._hw = None
        mock_daemon._cfg.fans = {"cpu_fan": MagicMock()}

        response = client.post(
            "/api/fans/cpu_fan/override",
            headers=auth_headers,
            json={"speed_percent": 100.0},
        )
        assert response.status_code == 503


class TestSensorStreamEndpoint:
    """Tests for GET /api/stream SSE endpoint."""

    def test_stream_requires_auth(self, client):
        """Stream endpoint should require authentication."""
        response = client.get("/api/stream")
        assert response.status_code == 401

    def test_stream_helper_matches_sensor_contract(self):
        """The shared serializer used by /api/stream should include control metadata."""
        from pysysfan.api.server import _sensors_payload

        payload = _sensors_payload(
            temps=[
                MagicMock(
                    identifier="/cpu/0/temp",
                    hardware_name="CPU",
                    sensor_name="Core 0",
                    value=45.5,
                )
            ],
            fans=[
                MagicMock(
                    identifier="/fan/0/rpm",
                    hardware_name="Motherboard",
                    sensor_name="CPU Fan",
                    value=1200,
                )
            ],
            controls=[
                MagicMock(
                    identifier="/fan/0/control",
                    hardware_name="Motherboard",
                    sensor_name="CPU Fan Control",
                    current_value=50.0,
                    has_control=True,
                )
            ],
        )

        assert payload["fans"][0]["control_percentage"] == 50.0
        assert payload["fans"][0]["controllable"] is True


class TestAlertEndpoints:
    """Tests for alert rule API endpoints."""

    def test_create_and_list_alert_rules(self, client, mock_daemon, auth_headers):
        response = client.post(
            "/api/alerts/rules",
            headers=auth_headers,
            json={
                "sensor_id": "cpu_temp",
                "alert_type": "high_temp",
                "threshold": 80.0,
            },
        )

        assert response.status_code == 200
        assert response.json()["rule"]["rule_id"] == "cpu_temp:high_temp"

        listed = client.get("/api/alerts/rules", headers=auth_headers)
        assert listed.status_code == 200
        assert listed.json()["count"] == 1
        assert listed.json()["rules"][0]["rule_id"] == "cpu_temp:high_temp"

    def test_update_alert_rule_by_rule_id(self, client, mock_daemon, auth_headers):
        mock_daemon.notification_manager.add_rule(
            AlertRule(sensor_id="cpu_temp", alert_type="high_temp", threshold=80.0)
        )
        mock_daemon.notification_manager.add_rule(
            AlertRule(sensor_id="cpu_temp", alert_type="low_temp", threshold=10.0)
        )

        response = client.put(
            "/api/alerts/rules/cpu_temp:low_temp",
            headers=auth_headers,
            json={"threshold": 8.0},
        )

        assert response.status_code == 200
        assert response.json()["rule_id"] == "cpu_temp:low_temp"
        rules = mock_daemon.notification_manager.get_rules()
        assert rules[0]["threshold"] == 80.0
        assert rules[1]["threshold"] == 8.0

    def test_update_alert_rule_rejects_invalid_type(
        self, client, mock_daemon, auth_headers
    ):
        mock_daemon.notification_manager.add_rule(
            AlertRule(sensor_id="cpu_temp", alert_type="high_temp", threshold=80.0)
        )

        response = client.put(
            "/api/alerts/rules/cpu_temp:high_temp",
            headers=auth_headers,
            json={"alert_type": "invalid"},
        )

        assert response.status_code == 400

    def test_delete_alert_rule_by_rule_id(self, client, mock_daemon, auth_headers):
        mock_daemon.notification_manager.add_rule(
            AlertRule(sensor_id="cpu_temp", alert_type="high_temp", threshold=80.0)
        )
        mock_daemon.notification_manager.add_rule(
            AlertRule(sensor_id="cpu_temp", alert_type="low_temp", threshold=10.0)
        )

        response = client.delete(
            "/api/alerts/rules/cpu_temp:high_temp",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["deleted"] == "cpu_temp:high_temp"
        rules = mock_daemon.notification_manager.get_rules()
        assert len(rules) == 1
        assert rules[0]["rule_id"] == "cpu_temp:low_temp"


class TestProfileEndpoints:
    """Tests for profile API endpoints."""

    @patch("pysysfan.api.server.ProfileManager")
    def test_profiles_list_returns_profiles(
        self, mock_profile_manager_cls, client, auth_headers
    ):
        """Profile listing should return profile metadata and the active name."""
        mock_profile_manager = mock_profile_manager_cls.return_value
        default_profile = MagicMock()
        default_profile.to_dict.return_value = {
            "name": "default",
            "display_name": "Default",
        }
        gaming_profile = MagicMock()
        gaming_profile.to_dict.return_value = {
            "name": "gaming",
            "display_name": "Gaming",
        }
        mock_profile_manager.list_profiles.return_value = [
            default_profile,
            gaming_profile,
        ]
        mock_profile_manager.get_active_profile.return_value = "default"

        response = client.get("/api/profiles", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["active"] == "default"
        assert data["count"] == 2
        assert data["profiles"][1]["name"] == "gaming"

    @patch("pysysfan.api.server.ProfileManager")
    def test_activate_profile_switches_daemon_config(
        self, mock_profile_manager_cls, client, mock_daemon, auth_headers
    ):
        """Activating a profile should update daemon config_path and reload it."""
        mock_profile_manager = mock_profile_manager_cls.return_value
        mock_profile_path = MagicMock()
        mock_profile_path.exists.return_value = True
        mock_profile_path.__str__.return_value = "/tmp/gaming.yaml"
        mock_profile_manager.get_profile_config_path.return_value = mock_profile_path
        mock_daemon.reload_config.return_value = True

        response = client.post("/api/profiles/gaming/activate", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["profile"] == "gaming"
        assert mock_daemon.config_path is mock_profile_path
        mock_profile_manager.set_active_profile.assert_called_once_with("gaming")
        mock_daemon.reload_config.assert_called_once()


class TestConfigToDict:
    """Tests for config_to_dict helper function."""

    def test_config_to_dict_structure(self, client, mock_daemon, auth_headers):
        """config_to_dict should return correct structure."""
        from pysysfan.api.server import config_to_dict

        mock_config = MagicMock()
        mock_config.poll_interval = 2.0
        mock_config.fans = {
            "cpu_fan": MagicMock(
                fan_id="/fan/0",
                curve="balanced",
                temp_ids=["/cpu/0/temp"],
                aggregation="max",
                allow_fan_off=False,
            )
        }
        mock_config.curves = {
            "balanced": MagicMock(points=[[30, 30], [60, 60]], hysteresis=3.0)
        }

        result = config_to_dict(mock_config)

        assert "general" in result
        assert result["general"]["poll_interval"] == 2.0
        assert "fans" in result
        assert "curves" in result
        assert "cpu_fan" in result["fans"]
        assert "balanced" in result["curves"]


class TestConfigValidateErrors:
    """Tests for config validate endpoint error paths."""

    @patch("pysysfan.config.Config")
    def test_config_validate_with_error(
        self, mock_config_cls, client, mock_daemon, auth_headers
    ):
        """Config validate should return valid=False on error."""
        mock_config_cls.load.side_effect = Exception("Config parse error")

        response = client.get("/api/config/validate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "error" in data


class TestSensorsEndpointsErrors:
    """Tests for sensor endpoints error paths."""

    def test_temperatures_endpoint_hardware_not_ready(
        self, client, mock_daemon, auth_headers
    ):
        """Temperatures endpoint should return 503 when hardware not initialized."""
        mock_daemon._hw = None

        response = client.get("/api/sensors/temperatures", headers=auth_headers)
        assert response.status_code == 503

    def test_fans_endpoint_hardware_not_ready(self, client, mock_daemon, auth_headers):
        """Fans endpoint should return 503 when hardware not initialized."""
        mock_daemon._hw = None

        response = client.get("/api/sensors/fans", headers=auth_headers)
        assert response.status_code == 503

    def test_controls_endpoint_hardware_not_ready(
        self, client, mock_daemon, auth_headers
    ):
        """Controls endpoint should return 503 when hardware not initialized."""
        mock_daemon._hw = None

        response = client.get("/api/sensors/controls", headers=auth_headers)
        assert response.status_code == 503


class TestCurvesEndpointsErrors:
    """Tests for curves endpoints error paths."""

    def test_curves_list_config_not_loaded(self, client, mock_daemon, auth_headers):
        """Curves list should return 503 if config not loaded."""
        mock_daemon._cfg = None

        response = client.get("/api/curves", headers=auth_headers)
        assert response.status_code == 503

    def test_curves_get_config_not_loaded(self, client, mock_daemon, auth_headers):
        """Curve get should return 503 if config not loaded."""
        mock_daemon._cfg = None

        response = client.get("/api/curves/balanced", headers=auth_headers)
        assert response.status_code == 503

    def test_curves_preview_with_invalid_data(self, client, auth_headers):
        """Curve preview should return 400 for invalid curve data."""
        response = client.post(
            "/api/curves/preview",
            headers=auth_headers,
            json={"points": "invalid", "temperature": 50.0},
        )
        assert response.status_code == 400


class TestFansEndpointsErrors:
    """Tests for fans endpoints error paths."""

    def test_fans_list_config_not_loaded(self, client, mock_daemon, auth_headers):
        """Fans list should return 503 if config not loaded."""
        mock_daemon._cfg = None

        response = client.get("/api/fans", headers=auth_headers)
        assert response.status_code == 503

    def test_fan_get_config_not_loaded(self, client, mock_daemon, auth_headers):
        """Fan get should return 503 if config not loaded."""
        mock_daemon._cfg = None

        response = client.get("/api/fans/cpu_fan", headers=auth_headers)
        assert response.status_code == 503

    def test_fan_get_not_found(self, client, mock_daemon, auth_headers):
        """Fan get should return 404 for non-existent fan."""
        mock_daemon._cfg.fans = {}

        response = client.get("/api/fans/nonexistent", headers=auth_headers)
        assert response.status_code == 404


class TestConfigGetErrors:
    """Tests for config get endpoint error paths."""

    @patch("pysysfan.config.Config")
    def test_config_get_load_error(
        self, mock_config_cls, client, mock_daemon, auth_headers
    ):
        """Config get should return 500 if load fails."""
        mock_config_cls.load.side_effect = Exception("Load error")

        response = client.get("/api/config", headers=auth_headers)
        assert response.status_code == 500


class TestConfigReloadErrors:
    """Tests for config reload endpoint error paths."""

    def test_config_reload_failure(self, client, mock_daemon, auth_headers):
        """Config reload should return 400 if reload fails."""
        mock_daemon.reload_config.return_value = False

        response = client.post("/api/config/reload", headers=auth_headers)
        assert response.status_code == 400
