"""Windows Task Scheduler integration for pysysfan startup service.

The scheduled task launches the **GUI-subsystem** ``pysysfan-service.exe``
(registered via ``[project.gui-scripts]``) so that no console window is ever
displayed.  An XML task definition gives full control over execution policy,
battery handling, and instance deduplication.
"""

from __future__ import annotations

import getpass
import os
import subprocess
import shutil
import logging
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pysysfan.config import DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_PATH
from pysysfan.platforms._process import hidden_process_kwargs
from pysysfan.state_file import read_state

logger = logging.getLogger(__name__)

TASK_NAME = "pysysfan"

# Paths managed by clean_all()
SERVICE_LOG_PATH = DEFAULT_CONFIG_DIR / "service.log"
STATE_FILE_PATH = DEFAULT_CONFIG_DIR / "daemon_state.json"
HISTORY_FILE_PATH = DEFAULT_CONFIG_DIR / "daemon_history.ndjson"


def _hidden_process_kwargs() -> dict[str, object]:
    """Return subprocess kwargs that suppress console windows on Windows."""
    return hidden_process_kwargs()


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


def _find_uv_venv_exe(name: str) -> str | None:
    """Return an exe from the UV tool venv for pysysfan, or None."""
    tool_dir = _uv_tool_dir()
    if tool_dir is None:
        return None
    for candidate in (
        tool_dir / "pysysfan" / "Scripts" / name,  # Windows
        tool_dir / "pysysfan" / "bin" / name.removesuffix(".exe"),  # Unix
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def _pysysfan_uv_venv_exe() -> str | None:
    """Return pysysfan.exe from inside the UV tool venv, if installed there."""
    return _find_uv_venv_exe("pysysfan.exe")


def _pysysfan_service_uv_venv_exe() -> str | None:
    """Return pysysfan-service.exe from the UV tool venv, if installed there."""
    return _find_uv_venv_exe("pysysfan-service.exe")


def _find_exe_in_path(name: str) -> str | None:
    """Find an executable in PATH, skipping Windows Store stubs."""
    for candidate in (name, f"{name}.exe"):
        exe = shutil.which(candidate)
        if exe and not _is_windows_store_stub(exe):
            return exe
    return None


def _pysysfan_exe() -> str:
    """Return the pysysfan executable path.

    Search order:
    1. UV tool venv (standalone CPython — works in scheduled tasks without
       requiring an interactive Windows app-execution context).
    2. PATH entries that are *not* Windows Store app execution aliases.
    """
    uv_exe = _pysysfan_uv_venv_exe()
    if uv_exe:
        return uv_exe

    path_exe = _find_exe_in_path("pysysfan")
    if path_exe:
        return path_exe

    raise FileNotFoundError(
        "pysysfan executable not found in PATH. "
        "Install with 'uv tool install .' then ensure uv tool bin is in PATH."
    )


def _pysysfan_service_exe() -> str:
    """Return the pysysfan-service executable path (GUI-subsystem / windowless).

    Search order:
    1. UV tool venv ``pysysfan-service.exe`` (preferred — guaranteed windowless).
    2. PATH ``pysysfan-service`` / ``pysysfan-service.exe``.
    3. Fallback to ``pysysfan.exe`` (console — will show a window, but works).
    """
    uv_exe = _pysysfan_service_uv_venv_exe()
    if uv_exe:
        return uv_exe

    path_exe = _find_exe_in_path("pysysfan-service")
    if path_exe:
        return path_exe

    logger.warning(
        "pysysfan-service.exe not found — falling back to pysysfan.exe. "
        "Reinstall with 'uv tool install . --force' to get the windowless service exe."
    )
    return _pysysfan_exe()


def _get_current_username() -> str:
    """Return the effective username for the scheduled task principal."""
    return os.environ.get("USERNAME") or getpass.getuser()


def _build_task_command(exe_path: str, config_path: Path) -> str:
    """Build the scheduled-task command line for the service executable."""
    resolved_exe = str(Path(exe_path).resolve())
    resolved_config = str(Path(config_path).resolve())
    return f'"{resolved_exe}" --config "{resolved_config}"'


def _build_task_xml(
    exe_path: str,
    config_path: Path,
    username: str,
) -> str:
    """Build an XML task definition for Task Scheduler.

    The XML gives us full control over settings that ``schtasks /Create``
    CLI flags cannot express (Hidden, battery policy, execution time limit,
    multiple-instance policy, etc.).
    """
    resolved_exe = str(Path(exe_path).resolve())
    resolved_config = str(Path(config_path).resolve())

    # Escape XML special characters in paths
    def _xml_escape(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    exe_escaped = _xml_escape(resolved_exe)
    args_escaped = _xml_escape(f'--config "{resolved_config}"')
    user_escaped = _xml_escape(username)

    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-16"?>
        <Task version="1.2"
              xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
          <RegistrationInfo>
            <Description>pysysfan fan control daemon — runs invisibly at logon.</Description>
          </RegistrationInfo>
          <Triggers>
            <LogonTrigger>
              <Enabled>true</Enabled>
            </LogonTrigger>
          </Triggers>
          <Principals>
            <Principal id="Author">
              <UserId>{user_escaped}</UserId>
              <LogonType>InteractiveToken</LogonType>
              <RunLevel>HighestAvailable</RunLevel>
            </Principal>
          </Principals>
          <Settings>
            <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
            <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
            <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
            <AllowHardTerminate>true</AllowHardTerminate>
            <StartWhenAvailable>true</StartWhenAvailable>
            <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
            <IdleSettings>
              <StopOnIdleEnd>false</StopOnIdleEnd>
              <RestartOnIdle>false</RestartOnIdle>
            </IdleSettings>
            <AllowStartOnDemand>true</AllowStartOnDemand>
            <Enabled>true</Enabled>
            <Hidden>false</Hidden>
            <RunOnlyIfIdle>false</RunOnlyIfIdle>
            <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
            <Priority>7</Priority>
          </Settings>
          <Actions Context="Author">
            <Exec>
              <Command>{exe_escaped}</Command>
              <Arguments>{args_escaped}</Arguments>
            </Exec>
          </Actions>
        </Task>
    """)


def install_task(config_path: Path | str | None = None) -> None:
    """Create a Windows Task Scheduler task to run pysysfan at user logon.

    Uses an XML task definition so the GUI-subsystem ``pysysfan-service.exe``
    is launched without any console window.

    Args:
        config_path: Optional explicit path to config file. If not provided,
                     uses the default path (~/.pysysfan/config.yaml).
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    config_path = Path(config_path).resolve()
    exe_path = _pysysfan_service_exe()
    username = _get_current_username()
    xml_content = _build_task_xml(exe_path, config_path, username)

    # Write XML to a temp file, import via schtasks, then delete.
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".xml",
        encoding="utf-16",
        delete=False,
    )
    try:
        tmp.write(xml_content)
        tmp.close()

        result = subprocess.run(
            [
                "schtasks",
                "/Create",
                "/TN",
                TASK_NAME,
                "/XML",
                tmp.name,
                "/F",
            ],
            capture_output=True,
            text=True,
            **_hidden_process_kwargs(),
        )
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"schtasks /Create failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    logger.info(
        "Task '%s' installed (exe: %s, config: %s)", TASK_NAME, exe_path, config_path
    )


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


def clean_all() -> list[str]:
    """Remove all pysysfan service artefacts for a clean-slate reinstall.

    1. Kill running pysysfan / pysysfan-service processes.
    2. Delete the scheduled task.
    3. Remove state, history, and service log files.

    Returns:
        List of human-readable messages describing what was cleaned.
    """
    messages: list[str] = []

    # Kill processes
    for exe_name in ("pysysfan.exe", "pysysfan-service.exe"):
        result = subprocess.run(
            ["taskkill", "/F", "/IM", exe_name],
            capture_output=True,
            text=True,
            **_hidden_process_kwargs(),
        )
        if result.returncode == 0:
            messages.append(f"Killed running {exe_name} processes.")
        # returncode != 0 likely means "not found" — that's fine.

    # Delete scheduled task
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )
    if result.returncode == 0:
        messages.append(f"Deleted scheduled task '{TASK_NAME}'.")
    else:
        messages.append(f"Scheduled task '{TASK_NAME}' was not installed.")

    # Remove state files
    for path in (STATE_FILE_PATH, HISTORY_FILE_PATH, SERVICE_LOG_PATH):
        if path.is_file():
            path.unlink()
            messages.append(f"Removed {path.name}.")
    # Remove rotated log backups (service.log.1, service.log.2, etc.)
    for backup in SERVICE_LOG_PATH.parent.glob("service.log.*"):
        backup.unlink(missing_ok=True)
        messages.append(f"Removed {backup.name}.")

    return messages
