"""Core status and sensor routes for the daemon API."""

from __future__ import annotations

import asyncio
import json
import time
from types import ModuleType
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from pysysfan.api.state import StateManager


def register_core_routes(
    app: FastAPI,
    *,
    daemon: Any,
    state: StateManager,
    auth_dependency: Callable[..., Any],
    server_module: ModuleType,
) -> None:
    """Register health, auth, status, sensors, and streaming routes."""

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        """Health check endpoint - no authentication required."""
        return {"status": "ok", "timestamp": time.time()}

    @app.post("/api/auth/verify")
    async def verify(token: str = Depends(auth_dependency)) -> dict[str, bool]:
        """Verify that the provided Bearer token is valid."""
        return {"valid": True}

    @app.get("/api/status")
    async def get_status(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Get full daemon state snapshot."""
        snapshot = state.get_snapshot()
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Daemon state not available",
            )
        return {
            "pid": snapshot.pid,
            "config_path": snapshot.config_path,
            "started_at": snapshot.started_at,
            "running": snapshot.running,
            "uptime_seconds": snapshot.uptime_seconds,
            "last_poll_time": snapshot.last_poll_time,
            "last_error": snapshot.last_error,
            "poll_interval": snapshot.poll_interval,
            "fans_configured": snapshot.fans_configured,
            "curves_configured": snapshot.curves_configured,
            "active_profile": snapshot.active_profile,
            "current_temps": snapshot.current_temps,
            "current_fan_speeds": snapshot.current_fan_speeds,
            "current_targets": snapshot.current_targets,
            "auto_reload_enabled": snapshot.auto_reload_enabled,
            "api_enabled": snapshot.api_enabled,
            "api_port": snapshot.api_port,
        }

    @app.get("/api/sensors")
    async def get_sensors(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Get all sensor readings from hardware."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        return server_module._sensors_payload(
            daemon._hw.get_temperatures(),
            daemon._hw.get_fan_speeds(),
            daemon._hw.get_controls(),
        )

    @app.get("/api/sensors/temperatures")
    async def get_temperatures(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Get temperature sensor readings."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        return {
            "temperatures": [
                {
                    "identifier": sensor.identifier,
                    "hardware_name": sensor.hardware_name,
                    "sensor_name": sensor.sensor_name,
                    "value": sensor.value,
                }
                for sensor in daemon._hw.get_temperatures()
            ],
            "timestamp": time.time(),
        }

    @app.get("/api/sensors/fans")
    async def get_fan_speeds(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Get fan RPM sensor readings."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        return {
            "fans": [
                {
                    "identifier": sensor.identifier,
                    "hardware_name": sensor.hardware_name,
                    "sensor_name": sensor.sensor_name,
                    "rpm": sensor.value,
                }
                for sensor in daemon._hw.get_fan_speeds()
            ],
            "timestamp": time.time(),
        }

    @app.get("/api/sensors/controls")
    async def get_controls(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Get fan control sensor readings."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        return {
            "controls": [
                {
                    "identifier": control.identifier,
                    "hardware_name": control.hardware_name,
                    "sensor_name": control.sensor_name,
                    "current_value": control.current_value,
                    "has_control": control.has_control,
                }
                for control in daemon._hw.get_controls()
            ],
            "timestamp": time.time(),
        }

    @app.get("/api/stream")
    async def sensor_stream(
        token: str = Depends(auth_dependency),
    ) -> EventSourceResponse:
        """Server-Sent Events endpoint for live sensor updates."""

        async def event_generator():
            while True:
                try:
                    if daemon._hw is None:
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": "Hardware not initialized"}),
                        }
                        break

                    sensors = server_module._sensors_payload(
                        daemon._hw.get_temperatures(),
                        daemon._hw.get_fan_speeds(),
                        daemon._hw.get_controls(),
                    )
                    yield {"event": "sensors", "data": json.dumps(sensors)}

                    poll_interval = daemon._cfg.poll_interval if daemon._cfg else 2.0
                    await asyncio.sleep(poll_interval)
                except Exception as exc:
                    yield {"event": "error", "data": json.dumps({"error": str(exc)})}
                    break

        return EventSourceResponse(event_generator())
