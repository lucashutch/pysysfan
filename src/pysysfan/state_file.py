"""Helpers for persisting daemon runtime state to disk.

The daemon writes a small JSON snapshot each control cycle so local tools such as
future GUI pages can read the latest temperatures, fan speeds, targets, profile,
and alerts without needing an HTTP server.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pysysfan.config import DEFAULT_CONFIG_DIR

DEFAULT_STATE_PATH = DEFAULT_CONFIG_DIR / "daemon_state.json"
DEFAULT_STATE_MAX_AGE_SECONDS = 10.0


@dataclass(slots=True)
class TemperatureState:
    """Serializable temperature sensor snapshot."""

    identifier: str
    hardware_name: str
    sensor_name: str
    value: float | None


@dataclass(slots=True)
class FanSpeedState:
    """Serializable fan speed snapshot."""

    identifier: str
    control_identifier: str | None
    hardware_name: str
    sensor_name: str
    rpm: float | None
    current_control_pct: float | None
    controllable: bool


@dataclass(slots=True)
class AlertState:
    """Serializable alert-history item."""

    rule_id: str
    sensor_id: str
    alert_type: str
    message: str
    value: float
    threshold: float
    timestamp: float


@dataclass(slots=True)
class DaemonStateFile:
    """Persisted daemon runtime snapshot."""

    timestamp: float
    pid: int
    running: bool
    uptime_seconds: float
    active_profile: str
    poll_interval: float
    config_path: str
    config_error: str | None = None
    fans_configured: int = 0
    curves_configured: int = 0
    temperatures: list[TemperatureState] = field(default_factory=list)
    fan_speeds: list[FanSpeedState] = field(default_factory=list)
    fan_targets: dict[str, float] = field(default_factory=dict)
    recent_alerts: list[AlertState] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DaemonStateFile:
        """Build a state snapshot from a decoded JSON payload."""

        return cls(
            timestamp=float(payload["timestamp"]),
            pid=int(payload["pid"]),
            running=bool(payload["running"]),
            uptime_seconds=float(payload["uptime_seconds"]),
            active_profile=str(payload.get("active_profile", "default")),
            poll_interval=float(payload.get("poll_interval", 1.0)),
            config_path=str(payload.get("config_path", "")),
            config_error=payload.get("config_error"),
            fans_configured=int(payload.get("fans_configured", 0)),
            curves_configured=int(payload.get("curves_configured", 0)),
            temperatures=[
                TemperatureState(**item) for item in payload.get("temperatures", [])
            ],
            fan_speeds=[
                FanSpeedState(control_identifier=None, **item)
                if "control_identifier" not in item
                else FanSpeedState(**item)
                for item in payload.get("fan_speeds", [])
            ],
            fan_targets={
                str(key): float(value)
                for key, value in payload.get("fan_targets", {}).items()
            },
            recent_alerts=[
                AlertState(**item) for item in payload.get("recent_alerts", [])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the snapshot to a JSON-serializable dictionary."""

        return asdict(self)


def write_state(state: DaemonStateFile, path: Path = DEFAULT_STATE_PATH) -> None:
    """Atomically write a daemon state snapshot to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.write("\n")
        temp_path = Path(handle.name)

    os.replace(temp_path, path)


def delete_state(path: Path = DEFAULT_STATE_PATH) -> None:
    """Remove the daemon state file if it exists."""

    try:
        path.unlink()
    except FileNotFoundError:
        return


def read_state(
    path: Path = DEFAULT_STATE_PATH,
    *,
    max_age_seconds: float = DEFAULT_STATE_MAX_AGE_SECONDS,
    now: float | None = None,
) -> DaemonStateFile | None:
    """Read a daemon state snapshot from disk.

    Returns ``None`` when the file is missing, unreadable, corrupt, or stale.
    """

    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = DaemonStateFile.from_dict(payload)
    except (OSError, ValueError, TypeError, KeyError):
        return None

    if max_age_seconds < 0:
        return state

    current_time = time.time() if now is None else now
    if current_time - state.timestamp > max_age_seconds:
        return None

    return state


__all__ = [
    "AlertState",
    "DaemonStateFile",
    "DEFAULT_STATE_MAX_AGE_SECONDS",
    "DEFAULT_STATE_PATH",
    "FanSpeedState",
    "TemperatureState",
    "delete_state",
    "read_state",
    "write_state",
]
