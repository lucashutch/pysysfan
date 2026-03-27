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
from pysysfan.platforms._process import hidden_process_kwargs
from pysysfan.profiles import DEFAULT_PROFILE_NAME, ProfileManager
from pysysfan.state_file import DEFAULT_STATE_PATH, DaemonStateFile, read_state
from pysysfan.temperature import get_valid_aggregation_methods


ELEVATION_REQUESTED_SENTINEL = "Windows asked for Administrator permission"

_STATE_CACHE_PATH: Path | None = None
_STATE_CACHE_MTIME_NS: int | None = None
_STATE_CACHE_VALUE: DaemonStateFile | None = None

_HISTORY_CACHE_PATH: Path | None = None
_HISTORY_CACHE_MTIME_NS: int | None = None
_HISTORY_CACHE_SIZE: int | None = None
_HISTORY_CACHE_VALUE: list[HistorySample] | None = None


def _hidden_process_kwargs() -> dict[str, object]:
    """Return subprocess kwargs that suppress console windows on Windows."""
    return hidden_process_kwargs()


def _find_executable(executable_name: str) -> str | None:
    """Return a best-effort path to an installed console executable."""
    for candidate in (executable_name, f"{executable_name}.exe"):
        executable = shutil.which(candidate)
        if executable is not None:
            return executable

    launcher_path = Path(sys.executable)
    for candidate in (
        launcher_path.with_name(executable_name),
        launcher_path.with_name(f"{executable_name}.exe"),
    ):
        if candidate.is_file():
            return str(candidate)

    return None


def _elevation_requested_message(command_label: str) -> str:
    """Return a clear follow-up message after a UAC prompt was requested."""
    return (
        f"{ELEVATION_REQUESTED_SENTINEL} for {command_label}. "
        "Approve the Windows UAC prompt to continue. "
        "If no prompt appears, close PySysFan and relaunch it as Administrator."
    )


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
    global _STATE_CACHE_PATH, _STATE_CACHE_MTIME_NS, _STATE_CACHE_VALUE

    state_path = Path(state_path)
    try:
        stat = state_path.stat()
    except OSError:
        _STATE_CACHE_PATH = state_path
        _STATE_CACHE_MTIME_NS = None
        _STATE_CACHE_VALUE = None
        return None

    mtime_ns = stat.st_mtime_ns
    if _STATE_CACHE_PATH == state_path and _STATE_CACHE_MTIME_NS == mtime_ns:
        return _STATE_CACHE_VALUE

    value = read_state(state_path)
    _STATE_CACHE_PATH = state_path
    _STATE_CACHE_MTIME_NS = mtime_ns
    _STATE_CACHE_VALUE = value
    return value


def read_daemon_history(
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> list[HistorySample]:
    """Read recent daemon history samples from the shared NDJSON file."""
    global \
        _HISTORY_CACHE_PATH, \
        _HISTORY_CACHE_MTIME_NS, \
        _HISTORY_CACHE_VALUE, \
        _HISTORY_CACHE_SIZE

    history_path = Path(history_path)
    try:
        stat = history_path.stat()
    except OSError:
        _HISTORY_CACHE_PATH = history_path
        _HISTORY_CACHE_MTIME_NS = None
        _HISTORY_CACHE_VALUE = []
        _HISTORY_CACHE_SIZE = None
        return []

    mtime_ns = stat.st_mtime_ns
    file_size = stat.st_size
    if (
        _HISTORY_CACHE_PATH == history_path
        and _HISTORY_CACHE_MTIME_NS == mtime_ns
        and _HISTORY_CACHE_SIZE == file_size
    ):
        return list(_HISTORY_CACHE_VALUE or [])

    value = read_history(history_path)
    _HISTORY_CACHE_PATH = history_path
    _HISTORY_CACHE_MTIME_NS = mtime_ns
    _HISTORY_CACHE_SIZE = file_size
    _HISTORY_CACHE_VALUE = list(value)
    return list(value)


def run_service_command(action: str) -> tuple[bool, str]:
    """Run a `pysysfan service <action>` command.

    When Administrator privileges are not already present on Windows, this will
    request elevation via UAC and return immediately.
    """
    return run_cli_command(
        ["service", action],
        elevate=True,
    )


def run_installer_command(executable_name: str) -> tuple[bool, str]:
    """Run one of the installer entrypoints, requesting elevation if required."""
    executable = _find_executable(executable_name)
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
        return True, _elevation_requested_message(executable_name)

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


def run_cli_command(
    args: Sequence[str],
    *,
    elevate: bool = False,
    executable_name: str = "pysysfan",
) -> tuple[bool, str]:
    """Run an installed CLI executable, optionally requesting elevation."""
    executable = _find_executable(executable_name)
    if executable is None:
        return run_python_module("pysysfan.cli", args, elevate=elevate)

    if elevate and sys.platform == "win32" and not check_admin():
        params = subprocess.list2cmdline(list(args))
        code = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            None,
            1,
        )
        if code <= 32:
            return False, f"Failed to request elevation for {' '.join(args)}"
        return True, _elevation_requested_message(
            f"`{executable_name} {' '.join(args)}`"
        )

    completed = subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode == 0:
        return True, output or f"Completed: {' '.join(args)}"
    return False, output or f"Failed: {' '.join(args)}"


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
        return True, _elevation_requested_message(f"`pysysfan {' '.join(args)}`")

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
