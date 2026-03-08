"""Tests for pysysfan.api.server SSE stream endpoint."""

import pytest
from unittest.mock import MagicMock, patch

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


class TestSensorStreamEndpoint:
    """Tests for GET /api/stream SSE endpoint."""

    def test_stream_requires_auth(self, client):
        """Stream endpoint should require authentication."""
        response = client.get("/api/stream")
        assert response.status_code == 401

    def test_stream_endpoint_exists(self, client, auth_headers):
        """Stream endpoint should exist in the API."""
        routes = [r.path for r in client.app.routes]
        assert "/api/stream" in routes
