"""Configuration, curves, and fan routes for the daemon API."""

from __future__ import annotations

import asyncio
from types import ModuleType
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, status


def register_config_routes(
    app: FastAPI,
    *,
    daemon: Any,
    auth_dependency: Callable[..., Any],
    server_module: ModuleType,
) -> None:
    """Register configuration, curve, and fan-management routes."""

    @app.get("/api/config")
    async def get_config(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Get current configuration as JSON."""
        from pysysfan.config import Config

        try:
            config = Config.load(daemon.config_path)
            return server_module.config_to_dict(config)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load config: {exc}",
            )

    @app.put("/api/config")
    async def update_config(
        config_data: dict, token: str = Depends(auth_dependency)
    ) -> dict[str, bool]:
        """Update entire configuration."""
        try:
            config = server_module._build_config_from_payload(
                config_data,
                existing_config=daemon._cfg,
            )
            config.save(daemon.config_path)
            daemon.reload_config()
            return {"success": True}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update config: {exc}",
            )

    @app.post("/api/config/reload")
    async def reload_config(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """Trigger daemon config reload."""
        success = daemon.reload_config()
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config reload failed",
            )
        return {"success": True}

    @app.get("/api/config/validate")
    async def validate_config(token: str = Depends(auth_dependency)) -> dict[str, Any]:
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
        except Exception as exc:
            return {"valid": False, "error": str(exc)}

    @app.get("/api/curves")
    async def list_curves(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """List all configured fan curves."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        return {
            "curves": {
                name: {
                    "name": name,
                    "points": curve.points,
                    "hysteresis": curve.hysteresis,
                }
                for name, curve in daemon._cfg.curves.items()
            }
        }

    @app.get("/api/curves/{name}")
    async def get_curve(
        name: str, token: str = Depends(auth_dependency)
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
        return {"name": name, "points": curve.points, "hysteresis": curve.hysteresis}

    @app.post("/api/curves/preview")
    async def preview_curve(
        preview_data: dict, token: str = Depends(auth_dependency)
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
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to evaluate curve: {exc}",
            )

    @app.post("/api/curves/validate")
    async def validate_curve(
        curve_data: dict, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Validate curve configuration without saving."""
        from pysysfan.api.validation import validate_curve as _validate_curve
        from pysysfan.api.validation import validate_hysteresis as _validate_hysteresis

        points = curve_data.get("points", [])
        hysteresis = curve_data.get("hysteresis", 3.0)
        errors = _validate_curve(points)
        errors.extend(_validate_hysteresis(hysteresis))
        return {"valid": len(errors) == 0, "errors": errors}

    @app.post("/api/curves/{name}")
    async def create_or_update_curve(
        name: str, curve_data: dict, token: str = Depends(auth_dependency)
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

        daemon._cfg.curves[name] = server_module._build_curve_config(curve_data)

        try:
            daemon._cfg.save(daemon.config_path)
            daemon.reload_config()
            return {"success": True, "name": name}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to save curve: {exc}",
            )

    @app.delete("/api/curves/{name}")
    async def delete_curve(
        name: str, token: str = Depends(auth_dependency)
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
        try:
            daemon._cfg.save(daemon.config_path)
            daemon.reload_config()
            return {"success": True, "deleted": name}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to delete curve: {exc}",
            )

    @app.get("/api/fans")
    async def list_fans(token: str = Depends(auth_dependency)) -> dict[str, Any]:
        """List all configured fans."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        return {
            "fans": {
                name: {
                    "name": name,
                    "fan_id": fan.fan_id,
                    "curve": fan.curve,
                    "temp_ids": fan.temp_ids,
                    "aggregation": fan.aggregation,
                    "allow_fan_off": fan.allow_fan_off,
                }
                for name, fan in daemon._cfg.fans.items()
            }
        }

    @app.get("/api/fans/{name}")
    async def get_fan(
        name: str, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
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
        name: str, fan_data: dict, token: str = Depends(auth_dependency)
    ) -> dict[str, Any]:
        """Update fan configuration."""
        if daemon._cfg is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Configuration not loaded",
            )

        try:
            daemon._cfg.fans[name] = server_module._build_fan_config(
                fan_data,
                existing_fan=daemon._cfg.fans.get(name),
            )
            daemon._cfg.save(daemon.config_path)
            daemon.reload_config()
            return {"success": True, "name": name}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update fan: {exc}",
            )

    @app.post("/api/fans/{name}/override")
    async def override_fan(
        name: str, override_data: dict, token: str = Depends(auth_dependency)
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
            daemon._hw.set_fan_speed(daemon._cfg.fans[name].fan_id, speed)

            async def reset_speed() -> None:
                await asyncio.sleep(duration)

            asyncio.create_task(reset_speed())
            return {
                "success": True,
                "fan": name,
                "speed_percent": speed,
                "duration_seconds": duration,
            }
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to override fan speed: {exc}",
            )
