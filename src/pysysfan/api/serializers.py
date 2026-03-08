"""Shared API serialization and config-construction helpers."""

from __future__ import annotations

import time
from typing import Any


def _match_control_for_fan(fan_sensor: Any, controls: list[Any]) -> Any | None:
    """Return the control sensor corresponding to a fan RPM sensor."""
    fan_prefix = fan_sensor.identifier.rsplit("/", 1)[0]
    for control in controls:
        control_prefix = control.identifier.rsplit("/", 1)[0]
        if control_prefix == fan_prefix:
            return control
    return None


def _fan_sensor_to_dict(fan_sensor: Any, controls: list[Any]) -> dict[str, Any]:
    """Serialize a fan sensor with matched control metadata."""
    matched_control = _match_control_for_fan(fan_sensor, controls)
    return {
        "identifier": fan_sensor.identifier,
        "hardware_name": fan_sensor.hardware_name,
        "sensor_name": fan_sensor.sensor_name,
        "rpm": fan_sensor.value,
        "control_percentage": (
            matched_control.current_value if matched_control is not None else None
        ),
        "controllable": (
            matched_control.has_control if matched_control is not None else False
        ),
    }


def _sensors_payload(
    temps: list[Any], fans: list[Any], controls: list[Any]
) -> dict[str, Any]:
    """Serialize the current hardware snapshot into the API sensor shape."""
    return {
        "temperatures": [
            {
                "identifier": sensor.identifier,
                "hardware_name": sensor.hardware_name,
                "sensor_name": sensor.sensor_name,
                "value": sensor.value,
            }
            for sensor in temps
        ],
        "fans": [_fan_sensor_to_dict(sensor, controls) for sensor in fans],
        "controls": [
            {
                "identifier": control.identifier,
                "hardware_name": control.hardware_name,
                "sensor_name": control.sensor_name,
                "current_value": control.current_value,
                "has_control": control.has_control,
            }
            for control in controls
        ],
        "timestamp": time.time(),
    }


def _build_curve_config(curve_data: dict[str, Any]):
    """Create a real CurveConfig from API payload data."""
    from pysysfan.config import CurveConfig

    points = curve_data.get("points", [])
    return CurveConfig(
        points=[(float(point[0]), float(point[1])) for point in points],
        hysteresis=float(curve_data.get("hysteresis", 2.0)),
    )


def _build_fan_config(fan_data: dict[str, Any], existing_fan: Any | None = None):
    """Create a FanConfig, preserving unspecified fields during partial updates."""
    from pysysfan.config import FanConfig

    return FanConfig(
        fan_id=fan_data.get("fan_id", getattr(existing_fan, "fan_id", "")),
        curve=fan_data.get("curve", getattr(existing_fan, "curve", "balanced")),
        temp_ids=fan_data.get("temp_ids", getattr(existing_fan, "temp_ids", [])),
        aggregation=fan_data.get(
            "aggregation", getattr(existing_fan, "aggregation", "max")
        ),
        header_name=getattr(existing_fan, "header_name", None),
        allow_fan_off=fan_data.get(
            "allow_fan_off", getattr(existing_fan, "allow_fan_off", True)
        ),
    )


def _build_config_from_payload(
    config_data: dict[str, Any], existing_config: Any | None = None
):
    """Create a real Config from API payload data, preserving update settings."""
    from pysysfan.config import Config, UpdateConfig

    existing_update = getattr(existing_config, "update", UpdateConfig())
    update_data = config_data.get("update", {})
    update_config = UpdateConfig(
        auto_check=update_data.get("auto_check", existing_update.auto_check),
        notify_only=update_data.get("notify_only", existing_update.notify_only),
    )

    fans = {
        name: _build_fan_config(fan_data)
        for name, fan_data in config_data.get("fans", {}).items()
    }
    curves = {
        name: _build_curve_config(curve_data)
        for name, curve_data in config_data.get("curves", {}).items()
    }

    return Config(
        poll_interval=float(config_data.get("general", {}).get("poll_interval", 2.0)),
        fans=fans,
        curves=curves,
        update=update_config,
    )


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
