"""Local desktop backend helpers for the PySide6 GUI.

These helpers provide the direct file/config/service access used by the desktop
GUI after removal of the local HTTP API.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from pysysfan.config import Config, DEFAULT_CONFIG_PATH
from pysysfan.curves import FanCurve, InvalidCurveError, parse_curve
from pysysfan.history_file import (
    DEFAULT_HISTORY_PATH,
    HistorySample,
    read_history,
)
from pysysfan.profiles import DEFAULT_PROFILE_NAME, ProfileManager
from pysysfan.state_file import DEFAULT_STATE_PATH, DaemonStateFile, read_state
from pysysfan.temperature import get_valid_aggregation_methods


def _hidden_process_kwargs() -> dict[str, object]:
    """Return subprocess kwargs that suppress console windows on Windows."""
    if sys.platform != "win32":
        return {}

    kwargs: dict[str, object] = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_factory is not None:
        startupinfo = startupinfo_factory()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    return kwargs


def check_admin() -> bool:
    """Return whether the current process has Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_profile_names(profile_manager: ProfileManager) -> list[str]:
    """Return available profile names sorted with the active profile first."""
    profiles = profile_manager.list_profiles()
    names = sorted({profile.name for profile in profiles})
    active = profile_manager.get_active_profile()
    if active in names:
        names.remove(active)
        names.insert(0, active)
    return names


def load_profile_config(
    profile_manager: ProfileManager,
    profile_name: str | None = None,
) -> tuple[str, Path, Config]:
    """Load the selected profile config and return its name, path, and model."""
    name = profile_name or profile_manager.get_active_profile()
    config_path = profile_manager.get_profile_config_path(name)
    if not config_path.exists() and name == DEFAULT_PROFILE_NAME:
        config_path = DEFAULT_CONFIG_PATH
    return name, config_path, Config.load(config_path)


def validate_config_model(config: Config) -> list[str]:
    """Validate a config model using the same rules as the daemon."""
    errors: list[str] = []
    valid_methods = get_valid_aggregation_methods()

    for fan_name, fan in config.fans.items():
        try:
            special = parse_curve(fan.curve)
            if special is None and fan.curve not in config.curves:
                errors.append(
                    f"Fan '{fan_name}' references unknown curve '{fan.curve}'"
                )
        except InvalidCurveError as exc:
            errors.append(f"Fan '{fan_name}' has invalid curve '{fan.curve}': {exc}")

        if fan.aggregation not in valid_methods:
            errors.append(
                f"Fan '{fan_name}' has invalid aggregation '{fan.aggregation}'. "
                f"Valid options: {valid_methods}"
            )

        if not fan.temp_ids:
            errors.append(f"Fan '{fan_name}' has no temperature sensors configured")

    if config.poll_interval <= 0:
        errors.append(f"poll_interval must be positive (got {config.poll_interval})")
    if config.poll_interval < 0.1:
        errors.append(
            f"poll_interval {config.poll_interval}s is too short (minimum 0.1s)"
        )

    return errors


def build_curve_preview_series(
    points: Sequence[Sequence[float] | tuple[float, float]],
    hysteresis: float,
    *,
    start_temp: int = 20,
    end_temp: int = 100,
) -> list[tuple[float, float]]:
    """Build a preview series for plotting a curve."""
    normalized_points = [(float(temp), float(speed)) for temp, speed in points]
    curve = FanCurve("preview", normalized_points, hysteresis=hysteresis)
    return [
        (float(temp), curve.evaluate(float(temp)))
        for temp in range(start_temp, end_temp + 1)
    ]


def read_daemon_state(state_path: Path = DEFAULT_STATE_PATH) -> DaemonStateFile | None:
    """Read the latest daemon state snapshot if one is available."""
    return read_state(state_path)


def read_daemon_history(
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> list[HistorySample]:
    """Read recent daemon history samples from the shared NDJSON file."""
    return read_history(history_path)


def run_service_command(action: str) -> tuple[bool, str]:
    """Run a `pysysfan service <action>` command.

    When Administrator privileges are not already present on Windows, this will
    request elevation via UAC and return immediately.
    """
    return run_python_module(
        "pysysfan.cli",
        ["service", action],
        elevate=True,
    )


def run_installer_command(executable_name: str) -> tuple[bool, str]:
    """Run one of the installer entrypoints, requesting elevation if required."""
    executable = shutil.which(executable_name) or shutil.which(f"{executable_name}.exe")
    if executable is None:
        return False, f"Executable not found in PATH: {executable_name}"

    if sys.platform == "win32" and not check_admin():
        code = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            "",
            None,
            1,
        )
        if code <= 32:
            return False, f"Failed to request elevation for {executable_name}"
        return (
            True,
            f"Elevation requested for {executable_name}. Refresh when it completes.",
        )

    completed = subprocess.run(
        [executable],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode == 0:
        return True, output or f"Completed: {executable_name}"
    return False, output or f"Failed: {executable_name}"


def run_python_module(
    module_name: str,
    args: Sequence[str],
    *,
    elevate: bool = False,
) -> tuple[bool, str]:
    """Run a Python module in a subprocess, optionally requesting elevation."""
    full_args = ["-m", module_name, *args]

    if elevate and sys.platform == "win32" and not check_admin():
        params = subprocess.list2cmdline(full_args)
        code = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1,
        )
        if code <= 32:
            return False, f"Failed to request elevation for {' '.join(args)}"
        return (
            True,
            f"Elevation requested for `pysysfan {' '.join(args)}`. Refresh when it completes.",
        )

    completed = subprocess.run(
        [sys.executable, *full_args],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode == 0:
        return True, output or f"Completed: {' '.join(args)}"
    return False, output or f"Failed: {' '.join(args)}"
