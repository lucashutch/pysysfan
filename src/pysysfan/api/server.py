"""FastAPI server for daemon management."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import requests
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from pysysfan.api.middleware import verify_token
from pysysfan.api.service_control import (
    find_daemon_process,
    get_recent_logs,
    stop_daemon_graceful,
)
from pysysfan.api.state import StateManager
from pysysfan.platforms import windows_service
from pysysfan.profiles import ProfileManager

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

    @app.post("/api/curves/validate")
    async def validate_curve(
        curve_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Validate curve configuration without saving."""
        from pysysfan.api.validation import validate_curve as _validate_curve
        from pysysfan.api.validation import validate_hysteresis as _validate_hysteresis

        points = curve_data.get("points", [])
        hysteresis = curve_data.get("hysteresis", 3.0)

        errors = _validate_curve(points)
        errors.extend(_validate_hysteresis(hysteresis))

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    @app.post("/api/curves/{name}")
    async def create_or_update_curve(
        name: str, curve_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Create or update a fan curve."""
        from pysysfan.api.validation import validate_curve as _validate_curve
        from pysysfan.api.validation import validate_hysteresis as _validate_hysteresis

        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        points = curve_data.get("points", [])
        hysteresis = curve_data.get("hysteresis", 3.0)

        errors = _validate_curve(points)
        errors.extend(_validate_hysteresis(hysteresis))

        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(errors),
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

    # Service management endpoints
    @app.get("/api/service/status")
    async def get_service_status(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Get full service status model."""
        import datetime

        # Task status
        task_status = windows_service.get_task_status()
        task_details = windows_service.get_task_details()

        task_installed = task_status is not None
        task_enabled = (
            task_details.get("Status") != "Disabled" if task_details else False
        )

        # Parse last run time
        task_last_run = None
        if task_details and "Last Run Time" in task_details:
            try:
                time_str = task_details["Last Run Time"]
                if time_str and time_str != "N/A":
                    task_last_run = datetime.datetime.strptime(
                        time_str,
                        "%m/%d/%Y %I:%M:%S %p",
                    )
            except (ValueError, TypeError):
                pass

        # Daemon process status
        daemon_proc = find_daemon_process()
        daemon_running = daemon_proc is not None
        daemon_pid = daemon_proc.pid if daemon_proc else None

        # Daemon health (API responds)
        daemon_healthy = False
        if daemon_running:
            try:
                response = requests.get("http://localhost:8765/api/health", timeout=2.0)
                daemon_healthy = response.status_code == 200
            except Exception:
                pass

        return {
            "task_installed": task_installed,
            "task_enabled": task_enabled,
            "task_status": task_status,
            "task_last_run": task_last_run.isoformat() if task_last_run else None,
            "daemon_running": daemon_running,
            "daemon_pid": daemon_pid,
            "daemon_healthy": daemon_healthy,
        }

    @app.post("/api/service/install")
    async def install_service(
        config_path: str | None = None,
        token: str = Depends(verify_token),
    ) -> dict[str, Any]:
        """Install pysysfan as startup service with explicit config path."""
        try:
            windows_service.install_task(config_path=config_path)
            return {"success": True, "message": "Service installed"}
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/service/uninstall")
    async def uninstall_service(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Remove pysysfan startup service."""
        try:
            windows_service.uninstall_task()
            return {"success": True, "message": "Service uninstalled"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/service/enable")
    async def enable_service(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Enable the scheduled task."""
        try:
            windows_service.enable_task()
            return {"success": True, "message": "Service enabled"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/service/disable")
    async def disable_service(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Disable the scheduled task."""
        try:
            windows_service.disable_task()
            return {"success": True, "message": "Service disabled"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/service/start")
    async def start_service(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Start the daemon now."""
        # Check if already running
        if find_daemon_process():
            return {"success": True, "message": "Daemon already running"}

        try:
            windows_service.start_task()
            return {"success": True, "message": "Daemon started"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/service/stop")
    async def stop_service(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Stop the daemon with graceful fallback."""
        success, method = stop_daemon_graceful()

        if success:
            return {
                "success": True,
                "message": f"Daemon stopped via {method.value}",
                "method": method.value,
            }
        else:
            raise HTTPException(500, "Failed to stop daemon")

    @app.post("/api/service/restart")
    async def restart_service(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Restart the daemon."""
        # Stop
        success, method = stop_daemon_graceful()
        if not success:
            raise HTTPException(500, "Failed to stop daemon")

        # Wait a moment
        await asyncio.sleep(1.0)

        # Start
        try:
            windows_service.start_task()
            return {"success": True, "message": "Daemon restarted"}
        except FileNotFoundError:
            raise HTTPException(404, "Service not installed")
        except Exception as e:
            raise HTTPException(500, f"Failed to start daemon: {e}")

    @app.get("/api/service/logs")
    async def get_service_logs(
        lines: int = 100,
        token: str = Depends(verify_token),
    ) -> dict[str, Any]:
        """Get recent daemon logs."""
        log_lines = get_recent_logs(lines)

        return {
            "logs": log_lines,
            "total_lines": len(log_lines),
        }

    # Profile management endpoints
    @app.get("/api/profiles")
    async def list_profiles(token: str = Depends(verify_token)) -> dict[str, Any]:
        """List all available profiles with metadata."""
        try:
            pm = ProfileManager()
            profiles = pm.list_profiles()
            active = pm.get_active_profile()

            return {
                "profiles": [p.to_dict() for p in profiles],
                "active": active,
                "count": len(profiles),
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list profiles: {e}",
            )

    @app.get("/api/profiles/active")
    async def get_active_profile(token: str = Depends(verify_token)) -> dict[str, Any]:
        """Get the name of the currently active profile."""
        try:
            pm = ProfileManager()
            active = pm.get_active_profile()

            return {"active": active}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get active profile: {e}",
            )

    @app.post("/api/profiles/{name}/activate")
    async def activate_profile(
        name: str, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Switch to a different profile.

        Activates the profile and reloads the daemon configuration.
        """
        try:
            pm = ProfileManager()

            # Validate profile exists
            if not pm.get_profile_config_path(name).exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Profile '{name}' not found",
                )

            # Set active profile
            pm.set_active_profile(name)

            # Update daemon config path and reload
            new_config_path = pm.get_profile_config_path(name)
            daemon.config_path = new_config_path

            # Reload config
            success = daemon.reload_config()

            if success:
                return {
                    "success": True,
                    "message": f"Switched to profile: {name}",
                    "profile": name,
                    "config_path": str(new_config_path),
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to reload configuration for new profile",
                )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to activate profile: {e}",
            )

    @app.post("/api/profiles/{name}")
    async def create_profile(
        name: str, profile_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Create a new profile.

        Request body can include:
        - display_name: Human-readable name
        - description: Profile description
        - copy_from: Name of profile to copy from
        """
        try:
            pm = ProfileManager()

            # Check if profile already exists
            if pm.get_profile_config_path(name).exists():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Profile '{name}' already exists",
                )

            # Create the profile
            profile = pm.create_profile(
                name=name,
                display_name=profile_data.get("display_name"),
                description=profile_data.get("description", ""),
                copy_from=profile_data.get("copy_from"),
            )

            return {
                "success": True,
                "profile": profile.to_dict(),
            }

        except HTTPException:
            raise
        except FileExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create profile: {e}",
            )

    @app.delete("/api/profiles/{name}")
    async def delete_profile(
        name: str, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Delete a profile."""
        try:
            pm = ProfileManager()

            # Cannot delete default profile
            if name == "default":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the default profile",
                )

            # Cannot delete active profile
            if name == pm.get_active_profile():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the active profile. Switch to another profile first.",
                )

            pm.delete_profile(name)

            return {
                "success": True,
                "message": f"Profile '{name}' deleted",
                "deleted": name,
            }

        except HTTPException:
            raise
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile '{name}' not found",
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete profile: {e}",
            )

    @app.get("/api/profiles/{name}/config")
    async def get_profile_config(
        name: str, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Get a profile's configuration."""
        try:
            pm = ProfileManager()
            profile = pm.get_profile(name)

            return config_to_dict(profile.config)

        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile '{name}' not found",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get profile config: {e}",
            )

    @app.put("/api/profiles/{name}/config")
    async def update_profile_config(
        name: str, config_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Update a profile's configuration."""
        from pysysfan.config import Config, FanConfig, CurveConfig

        try:
            pm = ProfileManager()

            # Verify profile exists
            if not pm.get_profile_config_path(name).exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Profile '{name}' not found",
                )

            # Parse config data
            poll_interval = config_data.get("general", {}).get("poll_interval", 2.0)

            fans = {}
            for fan_name, fan_data in config_data.get("fans", {}).items():
                fans[fan_name] = FanConfig(
                    fan_id=fan_data.get("fan_id", ""),
                    curve=fan_data.get("curve", "balanced"),
                    temp_ids=fan_data.get("temp_ids", []),
                    aggregation=fan_data.get("aggregation", "max"),
                    allow_fan_off=fan_data.get("allow_fan_off", True),
                )

            curves = {}
            for curve_name, curve_data in config_data.get("curves", {}).items():
                points = curve_data.get("points", [])
                curves[curve_name] = CurveConfig(
                    points=[(float(p[0]), float(p[1])) for p in points],
                    hysteresis=curve_data.get("hysteresis", 2.0),
                )

            config = Config(
                poll_interval=poll_interval,
                fans=fans,
                curves=curves,
            )

            # Update the profile
            pm.update_profile(name, config=config)

            # If this is the active profile, reload the daemon
            is_active = name == pm.get_active_profile()
            if is_active:
                daemon.config_path = pm.get_profile_config_path(name)
                daemon.reload_config()

            return {
                "success": True,
                "profile": name,
                "is_active": is_active,
                "reloaded": is_active,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update profile config: {e}",
            )

    # Profile rules endpoints
    @app.get("/api/profiles/rules")
    async def list_profile_rules(
        token: str = Depends(verify_token),
    ) -> dict[str, Any]:
        """List all profile auto-switch rules."""
        try:
            rules = daemon.rule_engine.rules
            return {
                "rules": [r.to_dict() for r in rules],
                "count": len(rules),
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list profile rules: {e}",
            )

    @app.post("/api/profiles/rules")
    async def create_profile_rule(
        rule_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Create a new profile auto-switch rule."""
        from pysysfan.profile_rules import ProfileRule

        try:
            rule = ProfileRule(
                rule_type=rule_data.get("rule_type", "manual"),
                profile_name=rule_data.get("profile_name", ""),
                enabled=rule_data.get("enabled", True),
                start_hour=rule_data.get("start_hour"),
                end_hour=rule_data.get("end_hour"),
                days=rule_data.get("days"),
                process_names=rule_data.get("process_names"),
            )
            daemon.rule_engine.add_rule(rule)
            return {"success": True, "rule": rule.to_dict()}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create profile rule: {e}",
            )

    @app.put("/api/profiles/rules/{rule_id}")
    async def update_profile_rule(
        rule_id: str,
        rule_data: dict,
        token: str = Depends(verify_token),
    ) -> dict[str, Any]:
        """Update an existing profile rule."""
        try:
            update_kwargs = {
                k: v for k, v in rule_data.items() if k != "id" and v is not None
            }
            success = daemon.rule_engine.update_rule(rule_id, **update_kwargs)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Profile rule '{rule_id}' not found",
                )
            return {"success": True, "rule_id": rule_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update profile rule: {e}",
            )

    @app.delete("/api/profiles/rules/{rule_id}")
    async def delete_profile_rule(
        rule_id: str, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Delete a profile rule."""
        success = daemon.rule_engine.remove_rule(rule_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile rule '{rule_id}' not found",
            )
        return {"success": True, "deleted": rule_id}

    @app.post("/api/profiles/rules/{rule_id}/test")
    async def test_profile_rule(
        rule_id: str, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Test if a profile rule matches current conditions."""
        rule = daemon.rule_engine.get_rule(rule_id)
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile rule '{rule_id}' not found",
            )

        from pysysfan.profile_rules import evaluate_time_rule, evaluate_process_rule

        if rule.rule_type == "time":
            matches = evaluate_time_rule(rule)
        elif rule.rule_type == "process":
            matches = evaluate_process_rule(rule)
        else:
            matches = False

        return {
            "rule_id": rule_id,
            "matches": matches,
            "profile_name": rule.profile_name,
        }

    # Alert management endpoints
    @app.get("/api/alerts/rules")
    async def list_alert_rules(
        token: str = Depends(verify_token),
    ) -> dict[str, Any]:
        """List all alert rules."""
        rules = daemon.notification_manager.get_rules()
        return {"rules": rules, "count": len(rules)}

    @app.post("/api/alerts/rules")
    async def create_alert_rule(
        rule_data: dict, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Create a new alert rule."""
        from pysysfan.notifications import AlertRule

        try:
            rule = AlertRule(
                sensor_id=rule_data.get("sensor_id", ""),
                alert_type=rule_data.get("alert_type", "high_temp"),
                threshold=rule_data.get("threshold", 80.0),
                enabled=rule_data.get("enabled", True),
                cooldown_seconds=rule_data.get("cooldown_seconds", 60.0),
            )
            daemon.notification_manager.add_rule(rule)
            return {"success": True, "rule": rule_data}
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create alert rule: {e}",
            )

    @app.put("/api/alerts/rules/{sensor_id}")
    async def update_alert_rule(
        sensor_id: str,
        rule_data: dict,
        token: str = Depends(verify_token),
    ) -> dict[str, Any]:
        """Update an existing alert rule."""
        success = daemon.notification_manager.update_rule(
            sensor_id=sensor_id,
            alert_type=rule_data.get("alert_type"),
            threshold=rule_data.get("threshold"),
            enabled=rule_data.get("enabled"),
            cooldown_seconds=rule_data.get("cooldown_seconds"),
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert rule for sensor '{sensor_id}' not found",
            )
        return {"success": True, "sensor_id": sensor_id}

    @app.delete("/api/alerts/rules/{sensor_id}")
    async def delete_alert_rule(
        sensor_id: str, token: str = Depends(verify_token)
    ) -> dict[str, Any]:
        """Delete an alert rule."""
        success = daemon.notification_manager.remove_rule(sensor_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert rule for sensor '{sensor_id}' not found",
            )
        return {"success": True, "deleted": sensor_id}

    @app.get("/api/alerts/history")
    async def get_alert_history(
        limit: int = 50,
        token: str = Depends(verify_token),
    ) -> dict[str, Any]:
        """Get alert history."""
        history = daemon.notification_manager.get_history(limit=limit)
        return {"alerts": history, "count": len(history)}

    @app.delete("/api/alerts/history")
    async def clear_alert_history(
        token: str = Depends(verify_token),
    ) -> dict[str, bool]:
        """Clear alert history."""
        daemon.notification_manager.clear_history()
        return {"success": True}

    # Shutdown endpoint for graceful API stop
    @app.post("/api/service/shutdown")
    async def shutdown_service(token: str = Depends(verify_token)) -> dict[str, bool]:
        """Shutdown the daemon gracefully via API."""
        if hasattr(daemon, "stop"):
            daemon.stop()
        return {"success": True}

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
