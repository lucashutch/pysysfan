"""Windows Task Scheduler integration for pysysfan startup service."""

from __future__ import annotations
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)

TASK_NAME = "pysysfan"


def _pysysfan_exe() -> str:
    """Find the pysysfan executable in PATH."""
    exe = shutil.which("pysysfan")
    if exe:
        return exe
    # Fallback: try uv tool path
    exe = shutil.which("pysysfan.exe")
    if exe:
        return exe
    raise FileNotFoundError(
        "pysysfan executable not found in PATH. "
        "Install with 'uv tool install .' then ensure uv tool bin is in PATH."
    )


def install_task(config_path: str | None = None) -> None:
    """Create a Windows Task Scheduler task to run pysysfan at system startup.

    The task runs as SYSTEM with highest privileges so it has access to
    hardware sensors before any user logs in.
    """
    exe = _pysysfan_exe()

    cmd_args = f'"{exe}" run'
    if config_path:
        cmd_args += f' --config "{config_path}"'

    # Build schtasks command
    # /SC ONSTART  — trigger at system startup
    # /RL HIGHEST  — highest privileges (administrator)
    # /RU SYSTEM   — run as SYSTEM account (no user login required)
    # /F           — force overwrite if task already exists
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

    logger.info(f"Task '{TASK_NAME}' installed successfully.")


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
        return None  # Not installed

    # Parse the output for Status line
    for line in result.stdout.splitlines():
        if line.strip().lower().startswith("status:"):
            return line.split(":", 1)[1].strip()

    return "Unknown"
