"""Windows Task Scheduler integration for pysysfan startup service."""

from __future__ import annotations

import getpass
import os
import subprocess
import shutil
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pysysfan.config import DEFAULT_CONFIG_PATH
from pysysfan.state_file import read_state

logger = logging.getLogger(__name__)

TASK_NAME = "pysysfan"
SERVICE_LAUNCHER_NAME = "pysysfan-service.cmd"


def _hidden_process_kwargs() -> dict[str, object]:
    """Return subprocess kwargs that suppress console windows on Windows."""
    if subprocess.os.name != "nt":
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


def _is_windows_store_stub(exe_path: str) -> bool:
    """Return True if the exe is a Windows Store app execution alias.

    These stubs live under ``AppData\\Local\\Microsoft\\WindowsApps\\`` and
    fail with "Unable to create process" when launched from a scheduled task
    because they require an interactive app-execution context.
    """
    return "windowsapps" in exe_path.lower()


def _uv_tool_dir() -> Path | None:
    """Return the UV tool directory by running ``uv tool dir``, or None if unavailable."""
    uv = shutil.which("uv") or shutil.which("uv.exe")
    if uv:
        try:
            result = subprocess.run(
                [uv, "tool", "dir"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        except (subprocess.TimeoutExpired, OSError):
            pass
    # Default UV tool dir for Windows: %APPDATA%\uv\tools
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            default = Path(appdata) / "uv" / "tools"
            if default.is_dir():
                return default
    return None


def _pysysfan_uv_venv_exe() -> str | None:
    """Return pysysfan.exe from inside the UV tool venv, if installed there.

    When installed via ``uv tool install .``, pysysfan lives in a venv that
    uses UV's standalone CPython — not the Windows Store Python stub.  Using
    this exe bypasses the "Unable to create process" failure that occurs when
    the scheduled task tries to launch a Windows Store app alias.
    """
    tool_dir = _uv_tool_dir()
    if tool_dir is None:
        return None
    for candidate in (
        tool_dir / "pysysfan" / "Scripts" / "pysysfan.exe",  # Windows
        tool_dir / "pysysfan" / "bin" / "pysysfan",  # Unix / WSL
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def _pysysfan_exe() -> str:
    """Return the pysysfan executable path.

    Search order:
    1. UV tool venv (standalone CPython — works in scheduled tasks without
       requiring an interactive Windows app-execution context).
    2. PATH entries that are *not* Windows Store app execution aliases.
    """
    # Prefer the UV tool venv exe so the service always gets standalone CPython.
    uv_exe = _pysysfan_uv_venv_exe()
    if uv_exe:
        return uv_exe

    # Fall back to PATH, skipping Windows Store stubs.
    for name in ("pysysfan", "pysysfan.exe"):
        exe = shutil.which(name)
        if exe and not _is_windows_store_stub(exe):
            return exe

    raise FileNotFoundError(
        "pysysfan executable not found in PATH. "
        "Install with 'uv tool install .' then ensure uv tool bin is in PATH."
    )


def _service_launcher_path(user_home: Path | None = None) -> Path:
    """Return the launcher script path used by the scheduled task."""
    home = (user_home or Path.home()).resolve()
    return home / ".pysysfan" / SERVICE_LAUNCHER_NAME


def _build_service_launcher(
    config_path: Path,
    *,
    user_home: Path | None = None,
    executable_path: str | None = None,
) -> str:
    """Build the batch script that restores the user environment and starts the daemon."""
    exe = executable_path or _pysysfan_exe()
    home = (user_home or Path.home()).resolve()
    home_drive = home.drive or ""
    home_tail = home.as_posix().replace("/", "\\")
    if home_drive and home_tail.lower().startswith(home_drive.lower()):
        home_path = home_tail[len(home_drive) :]
    else:
        home_path = home_tail

    lines = [
        "@echo off",
        "setlocal",
        f'set "USERPROFILE={home}"',
        f'set "HOME={home}"',
        f'set "HOMEDRIVE={home_drive}"',
        f'set "HOMEPATH={home_path}"',
        f'cd /d "{home}"',
        f'call "{exe}" run --config "{config_path}"',
    ]
    return "\r\n".join(lines) + "\r\n"


def _get_current_username() -> str:
    """Return the effective username for the scheduled task principal."""
    return os.environ.get("USERNAME") or getpass.getuser()


def _write_service_launcher(
    config_path: Path, *, user_home: Path | None = None
) -> Path:
    """Write the scheduled-task launcher script and return its path."""
    launcher_path = _service_launcher_path(user_home)
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_path.write_text(
        _build_service_launcher(config_path, user_home=user_home),
        encoding="utf-8",
        newline="\r\n",
    )
    return launcher_path


def _build_task_command(launcher_path: Path) -> str:
    """Build the short scheduled-task command line that invokes the launcher."""
    normalized_launcher = str(Path(launcher_path).resolve())
    return f'cmd.exe /d /c "{normalized_launcher}"'


def _delete_service_launcher(user_home: Path | None = None) -> None:
    """Delete the scheduled-task launcher script if it exists."""
    try:
        _service_launcher_path(user_home).unlink()
    except FileNotFoundError:
        return


def install_task(config_path: Path | str | None = None) -> None:
    """Create a Windows Task Scheduler task to run pysysfan at system startup.

    The task runs as SYSTEM with highest privileges so it has access to
    hardware sensors before any user logs in.

    Args:
        config_path: Optional explicit path to config file. If not provided,
                     uses the default path (~/.pysysfan/config.yaml). The path
                     is resolved to an absolute path before creating the task
                     to avoid issues with SYSTEM account's different home directory.
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    config_path = Path(config_path).resolve()

    launcher_path = _write_service_launcher(config_path)
    cmd_args = _build_task_command(launcher_path)

    # Run as the current interactive user so the user-space Python
    # environment (including Windows Store / uv / pip installs) is accessible.
    # SYSTEM cannot use Windows Store Python stubs or user-profile venvs.
    username = _get_current_username()

    result = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            cmd_args,
            "/SC",
            "ONLOGON",
            "/RU",
            username,
            "/IT",  # interactive token — no stored password needed
            "/RL",
            "HIGHEST",
            "/F",
        ],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"schtasks /Create failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    logger.info(f"Task '{TASK_NAME}' installed successfully with config: {config_path}")


def uninstall_task() -> None:
    """Remove the pysysfan Task Scheduler task."""
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )

    if result.returncode != 0:
        if (
            "cannot find" in result.stderr.lower()
            or "does not exist" in result.stderr.lower()
        ):
            raise FileNotFoundError(f"Task '{TASK_NAME}' is not installed.")
        raise RuntimeError(
            f"schtasks /Delete failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    _delete_service_launcher()

    logger.info(f"Task '{TASK_NAME}' removed.")


def enable_task() -> None:
    """Enable the pysysfan scheduled task.

    Raises:
        FileNotFoundError: If the task is not installed
        RuntimeError: If the enable operation fails
    """
    result = subprocess.run(
        ["schtasks", "/Change", "/TN", TASK_NAME, "/ENABLE"],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )

    if result.returncode != 0:
        if (
            "cannot find" in result.stderr.lower()
            or "does not exist" in result.stderr.lower()
        ):
            raise FileNotFoundError(f"Task '{TASK_NAME}' is not installed.")
        raise RuntimeError(
            f"schtasks /Change /ENABLE failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    logger.info(f"Task '{TASK_NAME}' enabled.")


def disable_task() -> None:
    """Disable the pysysfan scheduled task.

    The task remains installed but will not run at startup.

    Raises:
        FileNotFoundError: If the task is not installed
        RuntimeError: If the disable operation fails
    """
    result = subprocess.run(
        ["schtasks", "/Change", "/TN", TASK_NAME, "/DISABLE"],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )

    if result.returncode != 0:
        if (
            "cannot find" in result.stderr.lower()
            or "does not exist" in result.stderr.lower()
        ):
            raise FileNotFoundError(f"Task '{TASK_NAME}' is not installed.")
        raise RuntimeError(
            f"schtasks /Change /DISABLE failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    logger.info(f"Task '{TASK_NAME}' disabled.")


def start_task() -> None:
    """Start the pysysfan scheduled task immediately.

    Raises:
        FileNotFoundError: If the task is not installed
        RuntimeError: If the start operation fails
    """
    result = subprocess.run(
        ["schtasks", "/Run", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )

    if result.returncode != 0:
        if (
            "cannot find" in result.stderr.lower()
            or "does not exist" in result.stderr.lower()
        ):
            raise FileNotFoundError(f"Task '{TASK_NAME}' is not installed.")
        raise RuntimeError(
            f"schtasks /Run failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    logger.info(f"Task '{TASK_NAME}' started.")


def stop_task() -> None:
    """Stop the pysysfan scheduled task if it is currently running.

    Raises:
        FileNotFoundError: If the task is not installed
        RuntimeError: If the stop operation fails
    """
    result = subprocess.run(
        ["schtasks", "/End", "/TN", TASK_NAME],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )

    if result.returncode != 0:
        stderr = result.stderr.lower()
        if "cannot find" in stderr or "does not exist" in stderr:
            raise FileNotFoundError(f"Task '{TASK_NAME}' is not installed.")
        raise RuntimeError(
            f"schtasks /End failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    logger.info(f"Task '{TASK_NAME}' stopped.")


@dataclass
class ServiceStatus:
    """Combined status of scheduled task and daemon process.

    This dataclass distinguishes between:
    - Task Scheduler state (is the task installed/enabled?)
    - Daemon process state (is the daemon actually running?)

    This is important because:
    - Task can be installed but disabled
    - Task can be enabled but daemon not running
    - Daemon can be running but not via task (manual start)
    """

    task_installed: bool
    task_enabled: bool
    task_status: str | None
    task_last_run: datetime | None

    daemon_running: bool
    daemon_pid: int | None
    daemon_healthy: bool


def get_task_status() -> str | None:
    """Query the current state of the pysysfan scheduled task.

    Returns a human-readable status string, or None if not installed.
    """
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if line.strip().lower().startswith("status:"):
            return line.split(":", 1)[1].strip()

    return "Unknown"


def get_service_status() -> ServiceStatus:
    """Get comprehensive status of both task and daemon.

    Returns:
        ServiceStatus with task and daemon information
    """
    task_status_str = get_task_status()

    task_installed = task_status_str is not None
    task_enabled = task_status_str not in ["Disabled", None]
    task_last_run = None

    if task_installed:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"],
            capture_output=True,
            text=True,
            **_hidden_process_kwargs(),
        )

        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Last Run Time:" in line:
                    try:
                        time_str = line.split(":", 1)[1].strip()
                        if time_str and time_str != "N/A":
                            task_last_run = datetime.now()
                    except (ValueError, IndexError):
                        pass
                    break

    daemon_state = read_state()
    daemon_running = daemon_state is not None and daemon_state.running
    daemon_pid = daemon_state.pid if daemon_state is not None else None
    daemon_healthy = (
        daemon_state is not None
        and daemon_state.running
        and daemon_state.config_error is None
    )

    return ServiceStatus(
        task_installed=task_installed,
        task_enabled=task_enabled,
        task_status=task_status_str,
        task_last_run=task_last_run,
        daemon_running=daemon_running,
        daemon_pid=daemon_pid,
        daemon_healthy=daemon_healthy,
    )


def get_task_details() -> dict[str, str] | None:
    """Get detailed task information from Task Scheduler.

    Returns:
        Dictionary of task properties if task exists, None otherwise.
    """
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )

    if result.returncode != 0:
        return None

    # Parse output
    details: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            details[key.strip()] = value.strip()

    return details
