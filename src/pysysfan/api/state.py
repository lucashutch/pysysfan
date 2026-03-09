"""Thread-safe daemon state management.

This module provides a thread-safe container for daemon state that can be
snapshotted and shared with the API layer without blocking the control loop.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DaemonState:
    """Immutable snapshot of daemon state.

    This dataclass represents a point-in-time snapshot of the daemon's
    operational state. It is owned by the daemon control loop and should
    only be read by the API layer.

    All fields are read-only to ensure thread safety.
    """

    pid: int
    config_path: str
    started_at: float

    running: bool
    uptime_seconds: float
    last_poll_time: float
    last_error: str | None

    poll_interval: float
    fans_configured: int
    curves_configured: int
    active_profile: str

    current_temps: dict[str, float] = field(default_factory=dict)
    current_fan_speeds: dict[str, float] = field(default_factory=dict)
    current_targets: dict[str, float] = field(default_factory=dict)

    auto_reload_enabled: bool = True
    api_enabled: bool = False
    api_port: int = 8765


class StateManager:
    """Thread-safe container for daemon state.

    The daemon control loop owns this manager and calls update_state()
    on each poll cycle. The API layer calls get_snapshot() to get a
    read-only copy without blocking the control loop.

    Example:
        >>> manager = StateManager()
        >>> manager.update_state(daemon_pid=1234, running=True, ...)
        >>> snapshot = manager.get_snapshot()
        >>> print(snapshot.uptime_seconds)
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._state: DaemonState | None = None

    def update_state(self, **kwargs: Any) -> None:
        """Update daemon state with new values.

        This method should only be called by the daemon control loop.
        It creates a new DaemonState instance with the provided values.

        Args:
            **kwargs: Fields to update in the state
        """
        with self._lock:
            if self._state is None:
                self._state = DaemonState(
                    pid=kwargs.get("pid", 0),
                    config_path=kwargs.get("config_path", ""),
                    started_at=kwargs.get("started_at", time.time()),
                    running=kwargs.get("running", False),
                    uptime_seconds=kwargs.get("uptime_seconds", 0.0),
                    last_poll_time=kwargs.get("last_poll_time", time.time()),
                    last_error=kwargs.get("last_error", None),
                    poll_interval=kwargs.get("poll_interval", 2.0),
                    fans_configured=kwargs.get("fans_configured", 0),
                    curves_configured=kwargs.get("curves_configured", 0),
                    active_profile=kwargs.get("active_profile", "default"),
                    current_temps=kwargs.get("current_temps", {}),
                    current_fan_speeds=kwargs.get("current_fan_speeds", {}),
                    current_targets=kwargs.get("current_targets", {}),
                    auto_reload_enabled=kwargs.get("auto_reload_enabled", True),
                    api_enabled=kwargs.get("api_enabled", False),
                    api_port=kwargs.get("api_port", 8765),
                )
            else:
                new_state = DaemonState(
                    pid=kwargs.get("pid", self._state.pid),
                    config_path=kwargs.get("config_path", self._state.config_path),
                    started_at=kwargs.get("started_at", self._state.started_at),
                    running=kwargs.get("running", self._state.running),
                    uptime_seconds=kwargs.get(
                        "uptime_seconds", self._state.uptime_seconds
                    ),
                    last_poll_time=kwargs.get("last_poll_time", time.time()),
                    last_error=kwargs.get("last_error", self._state.last_error),
                    poll_interval=kwargs.get(
                        "poll_interval", self._state.poll_interval
                    ),
                    fans_configured=kwargs.get(
                        "fans_configured", self._state.fans_configured
                    ),
                    curves_configured=kwargs.get(
                        "curves_configured", self._state.curves_configured
                    ),
                    active_profile=kwargs.get(
                        "active_profile", self._state.active_profile
                    ),
                    current_temps=kwargs.get(
                        "current_temps", self._state.current_temps
                    ),
                    current_fan_speeds=kwargs.get(
                        "current_fan_speeds", self._state.current_fan_speeds
                    ),
                    current_targets=kwargs.get(
                        "current_targets", self._state.current_targets
                    ),
                    auto_reload_enabled=kwargs.get(
                        "auto_reload_enabled", self._state.auto_reload_enabled
                    ),
                    api_enabled=kwargs.get("api_enabled", self._state.api_enabled),
                    api_port=kwargs.get("api_port", self._state.api_port),
                )
                self._state = new_state

    def get_snapshot(self) -> DaemonState | None:
        """Get a read-only snapshot of the current state.

        This method is thread-safe and can be called from the API layer.

        Returns:
            DaemonState snapshot, or None if state hasn't been initialized
        """
        with self._lock:
            return self._state

    def clear_error(self) -> None:
        """Clear the last error field."""
        with self._lock:
            if self._state:
                self.update_state(last_error=None)
