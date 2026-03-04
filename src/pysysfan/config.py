"""Configuration management for pysysfan."""

from __future__ import annotations
import os
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pysysfan.platforms.base import HardwareScanResult

DEFAULT_CONFIG_DIR = Path.home() / ".pysysfan"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"


@dataclass
class FanConfig:
    fan_id: str
    curve: str
    temp_id: str
    header_name: str | None = None


@dataclass
class CurveConfig:
    points: list[tuple[float, float]]
    hysteresis: float = 2.0


@dataclass
class UpdateConfig:
    """Settings for automatic update checks."""

    auto_check: bool = True
    notify_only: bool = True


@dataclass
class Config:
    poll_interval: float = 2.0
    fans: dict[str, FanConfig] = field(default_factory=dict)
    curves: dict[str, CurveConfig] = field(default_factory=dict)
    update: UpdateConfig = field(default_factory=UpdateConfig)

    @classmethod
    def load(cls, path: Path | str) -> Config:
        """Load configuration from a YAML file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        poll_interval = data.get("general", {}).get("poll_interval", 2.0)

        fans = {}
        for name, fan_data in data.get("fans", {}).items():
            # Support backwards compatibility for old config keys for a smooth transition if needed,
            # but default to the new ones
            fans[name] = FanConfig(
                fan_id=fan_data.get("fan_id", fan_data.get("sensor")),
                curve=fan_data["curve"],
                temp_id=fan_data.get("temp_id", fan_data.get("source")),
                header_name=fan_data.get("header"),
            )

        curves = {}
        for name, curve_data in data.get("curves", {}).items():
            curves[name] = CurveConfig(
                points=[(float(p[0]), float(p[1])) for p in curve_data["points"]],
                hysteresis=curve_data.get("hysteresis", 2.0),
            )

        # Basic presets
        if "silent" not in curves:
            curves["silent"] = CurveConfig([(30, 20), (50, 40), (80, 100)])
        if "balanced" not in curves:
            curves["balanced"] = CurveConfig([(30, 30), (60, 60), (85, 100)])
        if "performance" not in curves:
            curves["performance"] = CurveConfig([(30, 50), (50, 80), (75, 100)])

        # Update settings
        update_data = data.get("update", {})
        update_cfg = UpdateConfig(
            auto_check=update_data.get("auto_check", True),
            notify_only=update_data.get("notify_only", True),
        )

        return cls(
            poll_interval=poll_interval, fans=fans, curves=curves, update=update_cfg
        )

    def save(self, path: Path | str):
        """Save configuration to a YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "general": {"poll_interval": self.poll_interval},
            "fans": {
                name: {
                    "fan_id": f.fan_id,
                    "curve": f.curve,
                    "temp_id": f.temp_id,
                    **({"header": f.header_name} if f.header_name else {}),
                }
                for name, f in self.fans.items()
            },
            "curves": {
                name: {
                    "points": [
                        list(p) for p in c.points
                    ],  # tuples → lists for clean YAML
                    "hysteresis": c.hysteresis,
                }
                for name, c in self.curves.items()
            },
            "update": {
                "auto_check": self.update.auto_check,
                "notify_only": self.update.notify_only,
            },
        }

        with open(path, "w") as f:
            yaml.dump(data, f, sort_keys=False)


def get_default_config() -> Config:
    """Returns a sensible default configuration."""
    config = Config()
    # No fans by default as we don't know the hardware IDs yet
    # Presets are added during load/init
    return config


def init_default_config(path: Path | str = DEFAULT_CONFIG_PATH):
    """Creates a default config file if it doesn't exist."""
    if os.path.exists(path):
        return

    config = get_default_config()
    # Add an example fan to the default config for documentation
    config.fans["example_cpu_fan"] = FanConfig(
        fan_id="/motherboard/nct6791d/control/0",
        curve="balanced",
        temp_id="/amdcpu/0/temperature/0",
        header_name="CPU Fan 1",
    )
    config.save(path)


def _sanitize_config_name(name: str) -> str:
    """Convert sensor name to valid YAML key.

    Examples:
        "CPU Fan" -> "cpu_fan"
        "Fan #1" -> "fan_1"
        "System Fan #2" -> "system_fan_2"
    """
    # Remove special characters except spaces and hash
    name = re.sub(r"[^\w\s#]", "", name)
    # Replace spaces and hash with underscores
    name = re.sub(r"[\s#]+", "_", name)
    # Convert to lowercase
    name = name.lower().strip("_")
    # Remove consecutive underscores
    name = re.sub(r"_+", "_", name)
    return name


def _generate_unique_name(base_name: str, existing_names: set[str]) -> str:
    """Generate a unique config key by appending a number if needed."""
    if base_name not in existing_names:
        return base_name

    counter = 2
    while f"{base_name}_{counter}" in existing_names:
        counter += 1
    return f"{base_name}_{counter}"


def auto_populate_config(
    scan_result: HardwareScanResult, default_curve: str = "balanced"
) -> Config:
    """Generate configuration from hardware scan results.

    Maps all detected fans to the primary CPU temperature sensor.
    Assigns the specified default curve to all fans.

    Args:
        scan_result: Hardware scan containing detected sensors and controls
        default_curve: Default curve name to assign to fans (default: "balanced")

    Returns:
        Config populated with all detected fans

    Raises:
        ValueError: If no temperature sensors are found
    """
    config = Config()

    # Find primary temperature sensor (prefer CPU)
    primary_temp = None
    for temp in scan_result.temperatures:
        if "cpu" in temp.hardware_type.lower() or "cpu" in temp.identifier.lower():
            primary_temp = temp
            break

    # Fallback to first available temperature sensor
    if primary_temp is None:
        if scan_result.temperatures:
            primary_temp = scan_result.temperatures[0]
        else:
            raise ValueError(
                "No temperature sensors found. Cannot create config without temperature sources."
            )

    # Generate fan configurations
    used_names: set[str] = set()
    for control in scan_result.controls:
        # Generate sanitized name
        base_name = _sanitize_config_name(control.sensor_name)
        unique_name = _generate_unique_name(base_name, used_names)
        used_names.add(unique_name)

        config.fans[unique_name] = FanConfig(
            fan_id=control.identifier,
            curve=default_curve,
            temp_id=primary_temp.identifier,
            header_name=control.sensor_name,
        )

    # Ensure default curves exist
    if "silent" not in config.curves:
        config.curves["silent"] = CurveConfig([(30, 20), (50, 40), (70, 70), (85, 100)])
    if "balanced" not in config.curves:
        config.curves["balanced"] = CurveConfig(
            [(30, 30), (60, 60), (75, 85), (85, 100)]
        )
    if "performance" not in config.curves:
        config.curves["performance"] = CurveConfig(
            [(30, 50), (50, 70), (65, 90), (75, 100)]
        )

    return config
