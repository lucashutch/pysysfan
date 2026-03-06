"""FastAPI server for daemon management."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from pysysfan.api.middleware import verify_token
from pysysfan.api.state import StateManager

logger = logging.getLogger(__name__)


def create_app(daemon, state: StateManager) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        daemon: The FanDaemon instance to expose via API.
        state: The StateManager for daemon state access.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="PySysFan API",
        version="1.0.0",
        docs_url=None,  # Disable Swagger UI in production
        redoc_url=None,
    )

    # CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://localhost:*", "tauri://localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.daemon = daemon
    app.state.state_manager = state

    # Health endpoint (no auth)
    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        """Health check endpoint - no authentication required."""
        return {"status": "ok", "timestamp": time.time()}

    # Token verification endpoint (no auth - just validates format)
    @app.post("/api/auth/verify")
    async def verify(token: str = Depends(verify_token)) -> dict[str, bool]:
        """Verify that the provided Bearer token is valid."""
        return {"valid": True}

    # Status endpoint
    @app.get("/api/status")
    async def get_status(token: str = Depends(verify_token)) -> dict[str, Any]:
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

    # Sensors endpoints
    @app.get("/api/sensors")
    async def get_sensors(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Get all sensor readings from hardware."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        temps = daemon._hw.get_temperatures()
        fans = daemon._hw.get_fans()
        controls = daemon._hw.get_controls()

        return {
            "temperatures": [
                {
                    "identifier": s.identifier,
                    "hardware_name": s.hardware_name,
                    "sensor_name": s.sensor_name,
                    "value": s.value,
                }
                for s in temps
            ],
            "fans": [
                {
                    "identifier": s.identifier,
                    "hardware_name": s.hardware_name,
                    "sensor_name": s.sensor_name,
                    "rpm": s.value,
                    "control_percentage": None,  # Match with control
                    "controllable": True,  # Check against controls
                }
                for s in fans
            ],
            "controls": [
                {
                    "identifier": c.identifier,
                    "hardware_name": c.hardware_name,
                    "sensor_name": c.sensor_name,
                    "current_value": c.current_value,
                    "has_control": c.has_control,
                }
                for c in controls
            ],
            "timestamp": time.time(),
        }

    @app.get("/api/sensors/temperatures")
    async def get_temperatures(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Get temperature sensor readings."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        temps = daemon._hw.get_temperatures()
        return {
            "temperatures": [
                {
                    "identifier": s.identifier,
                    "hardware_name": s.hardware_name,
                    "sensor_name": s.sensor_name,
                    "value": s.value,
                }
                for s in temps
            ],
            "timestamp": time.time(),
        }

    @app.get("/api/sensors/fans")
    async def get_fan_speeds(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Get fan RPM sensor readings."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        fans = daemon._hw.get_fans()
        return {
            "fans": [
                {
                    "identifier": s.identifier,
                    "hardware_name": s.hardware_name,
                    "sensor_name": s.sensor_name,
                    "rpm": s.value,
                }
                for s in fans
            ],
            "timestamp": time.time(),
        }

    @app.get("/api/sensors/controls")
    async def get_controls(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Get fan control sensor readings."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        controls = daemon._hw.get_controls()
        return {
            "controls": [
                {
                    "identifier": c.identifier,
                    "hardware_name": c.hardware_name,
                    "sensor_name": c.sensor_name,
                    "current_value": c.current_value,
                    "has_control": c.has_control,
                }
                for c in controls
            ],
            "timestamp": time.time(),
        }

    # Config endpoints
    @app.get("/api/config")
    async def get_config(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Get current configuration as JSON."""
        from pysysfan.config import Config

        try:
            config = Config.load(daemon.config_path)
            return config_to_dict(config)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load config: {e}",
            )

    @app.put("/api/config")
    async def update_config(
        config_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, bool]:
        """Update entire configuration."""
        from pysysfan.config import Config, FanConfig, CurveConfig

        try:
            # Parse config data manually
            poll_interval = config_data.get("general", {}).get("poll_interval", 2.0)

            fans = {}
            for name, fan_data in config_data.get("fans", {}).items():
                fans[name] = FanConfig(
                    fan_id=fan_data.get("fan_id", ""),
                    curve=fan_data.get("curve", "balanced"),
                    temp_ids=fan_data.get("temp_ids", []),
                    aggregation=fan_data.get("aggregation", "max"),
                    allow_fan_off=fan_data.get("allow_fan_off", True),
                )

            curves = {}
            for name, curve_data in config_data.get("curves", {}).items():
                points = curve_data.get("points", [])
                curves[name] = CurveConfig(
                    points=[(float(p[0]), float(p[1])) for p in points],
                    hysteresis=curve_data.get("hysteresis", 2.0),
                )

            config = Config(
                poll_interval=poll_interval,
                fans=fans,
                curves=curves,
            )
            config.save(daemon.config_path)

            # Trigger reload
            daemon.reload_config()

            return {"success": True}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update config: {e}",
            )

    @app.post("/api/config/reload")
    async def reload_config(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Trigger daemon config reload."""
        success = daemon.reload_config()
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config reload failed",
            )
        return {"success": True}

    @app.get("/api/config/validate")
    async def validate_config(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Validate current configuration without applying."""
        from pysysfan.config import Config

        try:
            config = Config.load(daemon.config_path)
            return {
                "valid": True,
                "fans": len(config.fans),
                "curves": len(config.curves),
                "poll_interval": config.poll_interval,
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

    # Fan Curves endpoints
    @app.get("/api/curves")
    async def list_curves(token: str = Depends(verify_token)) -> dict[str, Any]:
        """List all configured fan curves."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        curves_data = {}
        for name, curve in daemon._cfg.curves.items():
            curves_data[name] = {
                "name": name,
                "points": curve.points,
                "hysteresis": curve.hysteresis,
            }

        return {"curves": curves_data}

    @app.get("/api/curves/{name}")
    async def get_curve(
        name: str, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Get specific curve configuration."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        if name not in daemon._cfg.curves:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Curve '{name}' not found",
            )

        curve = daemon._cfg.curves[name]
        return {
            "name": name,
            "points": curve.points,
            "hysteresis": curve.hysteresis,
        }

    @app.post("/api/curves/{name}")
    async def create_or_update_curve(
        name: str, curve_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Create or update a fan curve."""

        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        # Update curve in config
        daemon._cfg.curves[name] = type(
            "CurveConfig",
            (),
            {
                "points": curve_data.get("points", []),
                "hysteresis": curve_data.get("hysteresis", 3.0),
            },
        )()

        # Save and reload
        try:
            daemon._cfg.save(daemon.config_path)
            daemon.reload_config()
            return {"success": True, "name": name}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to save curve: {e}",
            )

    @app.delete("/api/curves/{name}")
    async def delete_curve(
        name: str, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Delete a fan curve."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        if name not in daemon._cfg.curves:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Curve '{name}' not found",
            )

        del daemon._cfg.curves[name]

        # Save and reload
        try:
            daemon._cfg.save(daemon.config_path)
            daemon.reload_config()
            return {"success": True, "deleted": name}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete curve: {e}",
            )

    @app.post("/api/curves/preview")
    async def preview_curve(
        preview_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Evaluate a curve at a given temperature."""
        from pysysfan.curves import FanCurve

        points = preview_data.get("points", [])
        hysteresis = preview_data.get("hysteresis", 3.0)
        temperature = preview_data.get("temperature", 50.0)

        try:
            curve = FanCurve(name="preview", points=points, hysteresis=hysteresis)
            result = curve.evaluate(temperature)
            return {
                "temperature": temperature,
                "speed_percent": result,
                "points": points,
                "hysteresis": hysteresis,
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to evaluate curve: {e}",
            )

    # Fans endpoints
    @app.get("/api/fans")
    async def list_fans(token: str = Depends(verify_token)) -> dict[str, Any]:
        """List all configured fans."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        fans_data = {}
        for name, fan in daemon._cfg.fans.items():
            fans_data[name] = {
                "name": name,
                "fan_id": fan.fan_id,
                "curve": fan.curve,
                "temp_ids": fan.temp_ids,
                "aggregation": fan.aggregation,
                "allow_fan_off": fan.allow_fan_off,
            }

        return {"fans": fans_data}

    @app.get("/api/fans/{name}")
    async def get_fan(name: str, token: str = Depends(verify_token)) -> dict[str, Any]:
        """Get specific fan configuration."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        if name not in daemon._cfg.fans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fan '{name}' not found",
            )

        fan = daemon._cfg.fans[name]
        return {
            "name": name,
            "fan_id": fan.fan_id,
            "curve": fan.curve,
            "temp_ids": fan.temp_ids,
            "aggregation": fan.aggregation,
            "allow_fan_off": fan.allow_fan_off,
        }

    @app.put("/api/fans/{name}")
    async def update_fan(
        name: str, fan_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Update fan configuration."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        # Create fan config
        from pysysfan.config import FanConfig

        try:
            fan_config = FanConfig(
                fan_id=fan_data.get("fan_id", ""),
                curve=fan_data.get("curve", "balanced"),
                temp_ids=fan_data.get("temp_ids", []),
                aggregation=fan_data.get("aggregation", "max"),
                allow_fan_off=fan_data.get("allow_fan_off", False),
            )
            daemon._cfg.fans[name] = fan_config

            # Save and reload
            daemon._cfg.save(daemon.config_path)
            daemon.reload_config()
            return {"success": True, "name": name}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update fan: {e}",
            )

    @app.post("/api/fans/{name}/override")
    async def override_fan(
        name: str, override_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Manually override fan speed temporarily."""
        if daemon._hw is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hardware not initialized",
            )

        if daemon._cfg is None or name not in daemon._cfg.fans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fan '{name}' not found",
            )

        speed = override_data.get("speed_percent", 50.0)
        duration = override_data.get("duration_seconds", 10)

        try:
            fan_id = daemon._cfg.fans[name].fan_id
            daemon._hw.set_fan_speed(fan_id, speed)

            # Schedule reset after duration
            async def reset_speed():
                await asyncio.sleep(duration)
                # Note: The daemon loop will reset this on next iteration

            asyncio.create_task(reset_speed())

            return {
                "success": True,
                "fan": name,
                "speed_percent": speed,
                "duration_seconds": duration,
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to override fan speed: {e}",
            )

    # SSE stream for real-time updates
    @app.get("/api/stream")
    async def sensor_stream(token: str = Depends(verify_token)) -> EventSourceResponse:
        """Server-Sent Events endpoint for live sensor updates."""

        async def event_generator():
            while True:
                try:
                    # Get sensor readings
                    if daemon._hw is None:
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": "Hardware not initialized"}),
                        }
                        break

                    temps = daemon._hw.get_temperatures()
                    fans = daemon._hw.get_fans()
                    controls = daemon._hw.get_controls()

                    sensors = {
                        "temperatures": [
                            {
                                "identifier": s.identifier,
                                "hardware_name": s.hardware_name,
                                "sensor_name": s.sensor_name,
                                "value": s.value,
                            }
                            for s in temps
                        ],
                        "fans": [
                            {
                                "identifier": s.identifier,
                                "hardware_name": s.hardware_name,
                                "sensor_name": s.sensor_name,
                                "rpm": s.value,
                            }
                            for s in fans
                        ],
                        "controls": [
                            {
                                "identifier": c.identifier,
                                "hardware_name": c.hardware_name,
                                "sensor_name": c.sensor_name,
                                "current_value": c.current_value,
                                "has_control": c.has_control,
                            }
                            for c in controls
                        ],
                        "timestamp": time.time(),
                    }

                    yield {"event": "sensors", "data": json.dumps(sensors)}

                    # Wait for poll interval
                    poll_interval = daemon._cfg.poll_interval if daemon._cfg else 2.0
                    await asyncio.sleep(poll_interval)

                except Exception as e:
                    yield {"event": "error", "data": json.dumps({"error": str(e)})}
                    break

        return EventSourceResponse(event_generator())

    return app


def config_to_dict(config) -> dict[str, Any]:
    """Convert Config object to dictionary."""
    return {
        "general": {"poll_interval": config.poll_interval},
        "fans": {
            name: {
                "fan_id": fan.fan_id,
                "curve": fan.curve,
                "temp_ids": fan.temp_ids,
                "aggregation": fan.aggregation,
                "allow_fan_off": fan.allow_fan_off,
            }
            for name, fan in config.fans.items()
        },
        "curves": {
            name: {"points": curve.points, "hysteresis": curve.hysteresis}
            for name, curve in config.curves.items()
        },
    }
