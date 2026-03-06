"""Windows Task Scheduler integration for pysysfan startup service."""

from __future__ import annotations

import subprocess
import shutil
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pysysfan.config import DEFAULT_CONFIG_PATH

logger = logging.getLogger(__name__)

TASK_NAME = "pysysfan"


def _pysysfan_exe() -> str:
    """Find the pysysfan executable in PATH."""
    exe = shutil.which("pysysfan")
    if exe:
        return exe
    exe = shutil.which("pysysfan.exe")
    if exe:
        return exe
    raise FileNotFoundError(
        "pysysfan executable not found in PATH. "
        "Install with 'uv tool install .' then ensure uv tool bin is in PATH."
    )


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

    exe = _pysysfan_exe()

    cmd_args = f'"{exe}" run --config "{config_path}"'

    result = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            cmd_args,
            "/SC",
            "ONSTART",
            "/RL",
            "HIGHEST",
            "/RU",
            "SYSTEM",
            "/F",
        ],
        capture_output=True,
        text=True,
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

    daemon_running = False
    daemon_pid = None
    daemon_healthy = False

    return ServiceStatus(
        task_installed=task_installed,
        task_enabled=task_enabled,
        task_status=task_status_str,
        task_last_run=task_last_run,
        daemon_running=daemon_running,
        daemon_pid=daemon_pid,
        daemon_healthy=daemon_healthy,
    )
