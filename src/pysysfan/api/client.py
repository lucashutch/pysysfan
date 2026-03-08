"""Python client for pysysfan daemon API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import requests


class PySysFanClient:
    """Python client for pysysfan daemon API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        token: str | None = None,
    ):
        """Initialize the API client.

        Args:
            base_url: The base URL of the API server.
            token: API authentication token. If None, loads from default location.
        """
        self.base_url = base_url.rstrip("/")
        self.token = token or self._load_token()

    def _load_token(self) -> str:
        """Load token from default location.

        Returns:
            The API token string.

        Raises:
            FileNotFoundError: If token file doesn't exist.
        """
        token_file = Path.home() / ".pysysfan" / "api_token"
        if not token_file.exists():
            raise FileNotFoundError(
                "API token not found. Is daemon running? Run: pysysfan run"
            )
        return token_file.read_text(encoding="utf-8").strip()

    def _headers(self) -> dict[str, str]:
        """Get request headers with authorization."""
        return {"Authorization": f"Bearer {self.token}"}

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make an authenticated request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path.
            **kwargs: Additional arguments for requests.request.

        Returns:
            JSON response as dictionary.

        Raises:
            requests.HTTPError: If the request fails.
        """
        url = f"{self.base_url}{path}"

        # Merge headers
        headers = kwargs.pop("headers", {})
        headers.update(self._headers())

        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    # Health
    def health(self) -> dict[str, Any]:
        """Check API health (no auth required).

        Returns:
            Health status dictionary.
        """
        return requests.get(f"{self.base_url}/api/health").json()

    def verify_token(self) -> dict[str, bool]:
        """Verify the API token is valid.

        Returns:
            Dictionary with 'valid' key.
        """
        return self._request("POST", "/api/auth/verify")

    # Status
    def get_status(self) -> dict[str, Any]:
        """Get full daemon state.

        Returns:
            Complete daemon state snapshot.
        """
        return self._request("GET", "/api/status")

    def is_daemon_running(self) -> bool:
        """Check if daemon is running and healthy.

        Returns:
            True if daemon responds to health check.
        """
        try:
            self.health()
            return True
        except requests.RequestException:
            return False

    def is_authenticated(self) -> bool:
        """Check if the client can authenticate with the daemon.

        Returns:
            True if token is valid.
        """
        try:
            result = self.verify_token()
            return result.get("valid", False)
        except requests.RequestException:
            return False

    # Sensors
    def get_sensors(self) -> dict[str, Any]:
        """Get all sensor readings.

        Returns:
            Dictionary with temperatures, fans, and controls.
        """
        return self._request("GET", "/api/sensors")

    def get_temperatures(self) -> dict[str, Any]:
        """Get temperature sensor readings.

        Returns:
            Dictionary with temperature sensors.
        """
        return self._request("GET", "/api/sensors/temperatures")

    def get_fans(self) -> dict[str, Any]:
        """Get fan RPM sensor readings.

        Returns:
            Dictionary with fan sensors.
        """
        return self._request("GET", "/api/sensors/fans")

    def get_controls(self) -> dict[str, Any]:
        """Get fan control sensor readings.

        Returns:
            Dictionary with control sensors.
        """
        return self._request("GET", "/api/sensors/controls")

    # Config
    def get_config(self) -> dict[str, Any]:
        """Get current configuration.

        Returns:
            Configuration as dictionary.
        """
        return self._request("GET", "/api/config")

    def update_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Update configuration.

        Args:
            config: New configuration dictionary.

        Returns:
            Success response.
        """
        return self._request("PUT", "/api/config", json=config)

    def reload_config(self) -> dict[str, Any]:
        """Trigger config reload.

        Returns:
            Success response.
        """
        return self._request("POST", "/api/config/reload")

    def validate_config(self) -> dict[str, Any]:
        """Validate current configuration.

        Returns:
            Validation result.
        """
        return self._request("GET", "/api/config/validate")

    # Curves
    def list_curves(self) -> dict[str, Any]:
        """List all fan curves.

        Returns:
            Dictionary of curve configurations.
        """
        return self._request("GET", "/api/curves")

    def get_curve(self, name: str) -> dict[str, Any]:
        """Get specific curve.

        Args:
            name: Curve name.

        Returns:
            Curve configuration.
        """
        return self._request("GET", f"/api/curves/{name}")

    def create_curve(
        self, name: str, points: list[list[float]], hysteresis: float = 3.0
    ) -> dict[str, Any]:
        """Create or update a fan curve.

        Args:
            name: Curve name.
            points: List of [temperature, speed] pairs.
            hysteresis: Hysteresis in degrees Celsius.

        Returns:
            Success response.
        """
        data = {"points": points, "hysteresis": hysteresis}
        return self._request("POST", f"/api/curves/{name}", json=data)

    def update_curve(
        self, name: str, points: list[list[float]], hysteresis: float = 3.0
    ) -> dict[str, Any]:
        """Update an existing fan curve (alias for create_curve).

        Args:
            name: Curve name.
            points: List of [temperature, speed] pairs.
            hysteresis: Hysteresis in degrees Celsius.

        Returns:
            Success response.
        """
        return self.create_curve(name, points, hysteresis)

    def delete_curve(self, name: str) -> dict[str, Any]:
        """Delete a fan curve.

        Args:
            name: Curve name.

        Returns:
            Success response.
        """
        return self._request("DELETE", f"/api/curves/{name}")

    def preview_curve(
        self, points: list[list[float]], temperature: float, hysteresis: float = 3.0
    ) -> dict[str, Any]:
        """Evaluate curve at a temperature.

        Args:
            points: List of [temperature, speed] pairs.
            temperature: Temperature to evaluate at.
            hysteresis: Hysteresis in degrees Celsius.

        Returns:
            Evaluation result with speed_percent.
        """
        data = {"points": points, "temperature": temperature, "hysteresis": hysteresis}
        return self._request("POST", "/api/curves/preview", json=data)

    # Fans
    def list_fans(self) -> dict[str, Any]:
        """List all configured fans.

        Returns:
            Dictionary of fan configurations.
        """
        return self._request("GET", "/api/fans")

    def get_fan(self, name: str) -> dict[str, Any]:
        """Get specific fan configuration.

        Args:
            name: Fan name.

        Returns:
            Fan configuration.
        """
        return self._request("GET", f"/api/fans/{name}")

    def update_fan(
        self,
        name: str,
        fan_id: str | None = None,
        curve: str | None = None,
        temp_ids: list[str] | None = None,
        aggregation: str | None = None,
        allow_fan_off: bool | None = None,
    ) -> dict[str, Any]:
        """Update fan configuration.

        Args:
            name: Fan name.
            fan_id: Fan control identifier.
            curve: Curve name.
            temp_ids: List of temperature sensor identifiers.
            aggregation: Aggregation method.
            allow_fan_off: Whether fan can be turned off.

        Returns:
            Success response.
        """
        data: dict[str, Any] = {}
        if fan_id is not None:
            data["fan_id"] = fan_id
        if curve is not None:
            data["curve"] = curve
        if temp_ids is not None:
            data["temp_ids"] = temp_ids
        if aggregation is not None:
            data["aggregation"] = aggregation
        if allow_fan_off is not None:
            data["allow_fan_off"] = allow_fan_off

        return self._request("PUT", f"/api/fans/{name}", json=data)

    def override_fan(
        self, name: str, speed_percent: float, duration_seconds: float = 10.0
    ) -> dict[str, Any]:
        """Manually override fan speed temporarily.

        Args:
            name: Fan name.
            speed_percent: Target speed (0-100).
            duration_seconds: How long to maintain override.

        Returns:
            Success response.
        """
        data = {"speed_percent": speed_percent, "duration_seconds": duration_seconds}
        return self._request("POST", f"/api/fans/{name}/override", json=data)

    # Service
    def get_service_status(self) -> dict[str, Any]:
        """Get the Windows service and daemon status snapshot.

        Returns:
            Service status dictionary.
        """
        return self._request("GET", "/api/service/status")

    def install_service(self, config_path: str | None = None) -> dict[str, Any]:
        """Install the scheduled task for pysysfan.

        Args:
            config_path: Optional config path to pass to the installer.

        Returns:
            Success response.
        """
        params = {"config_path": config_path} if config_path is not None else None
        return self._request("POST", "/api/service/install", params=params)

    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall the scheduled task.

        Returns:
            Success response.
        """
        return self._request("POST", "/api/service/uninstall")

    def enable_service(self) -> dict[str, Any]:
        """Enable the scheduled task.

        Returns:
            Success response.
        """
        return self._request("POST", "/api/service/enable")

    def disable_service(self) -> dict[str, Any]:
        """Disable the scheduled task.

        Returns:
            Success response.
        """
        return self._request("POST", "/api/service/disable")

    def start_service(self) -> dict[str, Any]:
        """Start the daemon via the service layer.

        Returns:
            Success response.
        """
        return self._request("POST", "/api/service/start")

    def stop_service(self) -> dict[str, Any]:
        """Stop the daemon via the service layer.

        Returns:
            Success response, including the stop method when available.
        """
        return self._request("POST", "/api/service/stop")

    def restart_service(self) -> dict[str, Any]:
        """Restart the daemon via the service layer.

        Returns:
            Success response.
        """
        return self._request("POST", "/api/service/restart")

    def get_service_logs(self, lines: int = 100) -> dict[str, Any]:
        """Fetch recent daemon log lines.

        Args:
            lines: Number of trailing log lines to request.

        Returns:
            Dictionary containing logs and total line count.
        """
        return self._request("GET", "/api/service/logs", params={"lines": lines})

    # Streaming
    def stream_sensors(self) -> Iterator[dict[str, Any]]:
        """Stream sensor updates via SSE.

        Yields:
            Sensor data dictionaries.

        Note:
            Requires sseclient-py: pip install sseclient-py
        """
        try:
            import sseclient
        except ImportError:
            raise ImportError(
                "Streaming requires sseclient-py. Install: pip install sseclient-py"
            )

        url = f"{self.base_url}/api/stream"
        headers = self._headers()

        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        client = sseclient.SSEClient(response)

        for event in client.events():
            if event.event == "sensors":
                yield json.loads(event.data)
            elif event.event == "error":
                error_data = json.loads(event.data)
                raise RuntimeError(
                    f"Stream error: {error_data.get('error', 'Unknown')}"
                )
