"""Configuration management for pysysfan."""

from __future__ import annotations
import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path

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
