"""Linux systemd service integration for pysysfan.

This module provides systemd service management for Linux systems,
allowing pysysfan to run as a system or user service.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

SERVICE_NAME = "pysysfan"
SYSTEMD_SYSTEM_DIR = Path("/etc/systemd/system")
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"

# Systemd service unit template
SYSTEMD_SERVICE_TEMPLATE = """[Unit]
Description=pysysfan - Python fan control daemon
Documentation=https://github.com/anomalyco/pysysfan
After=multi-user.target

[Service]
Type=simple
ExecStart={executable} run --config {config_path}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

# User service template (slightly different)
USER_SERVICE_TEMPLATE = """[Unit]
Description=pysysfan - Python fan control daemon (user)
Documentation=https://github.com/anomalyco/pysysfan
After=graphical-session.target

[Service]
Type=simple
ExecStart={executable} run --config {config_path}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""


def _find_executable() -> str:
    """Find the pysysfan executable in PATH."""
    exe = shutil.which("pysysfan")
    if exe:
        return exe
    # Check common locations
    common_paths = [
        Path.home() / ".local" / "bin" / "pysysfan",
        Path("/usr/local/bin/pysysfan"),
        Path("/usr/bin/pysysfan"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)
    raise FileNotFoundError(
        "pysysfan executable not found in PATH. "
        "Install with 'pip install pysysfan[linux]' or 'uv tool install pysysfan[linux]'."
    )


def _get_config_path(config_path: Path | None) -> Path:
    """Get the config path, using default if not specified."""
    if config_path:
        return config_path
    return Path.home() / ".pysysfan" / "config.yaml"


def _run_systemctl(
    args: list[str], system_wide: bool = True, check: bool = True
) -> subprocess.CompletedProcess:
    """Run systemctl command."""
    cmd = ["systemctl"]
    if not system_wide:
        cmd.append("--user")
    cmd.extend(args)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"systemctl command failed (exit {result.returncode}): {result.stderr}"
        )
    return result


def install_systemd_service(
    config_path: Path | None = None,
    system_wide: bool = True,
) -> None:
    """Install pysysfan as a systemd service.

    Args:
        config_path: Path to config file. Defaults to ~/.pysysfan/config.yaml
        system_wide: If True, install system-wide service requiring root.
                     If False, install user service.

    Raises:
        FileNotFoundError: If pysysfan executable not found
        RuntimeError: If systemctl commands fail
        PermissionError: If insufficient permissions for system-wide install
    """
    exe = _find_executable()
    cfg = _get_config_path(config_path)

    # Ensure config file exists
    if not cfg.exists():
        raise FileNotFoundError(
            f"Config file not found: {cfg}. Run 'pysysfan config init' first."
        )

    # Determine service file path
    if system_wide:
        service_dir = SYSTEMD_SYSTEM_DIR
        template = SYSTEMD_SERVICE_TEMPLATE
    else:
        service_dir = SYSTEMD_USER_DIR
        template = USER_SERVICE_TEMPLATE

    service_file = service_dir / f"{SERVICE_NAME}.service"

    # Create directory if needed
    service_dir.mkdir(parents=True, exist_ok=True)

    # Check permissions for system-wide install
    if system_wide and not service_dir.exists():
        raise PermissionError(
            f"Cannot create {service_dir}. Run with sudo for system-wide installation."
        )

    # Generate service file content
    service_content = template.format(
        executable=exe,
        config_path=cfg,
    )

    # Write service file
    try:
        service_file.write_text(service_content)
        logger.info(f"Created systemd service: {service_file}")
    except PermissionError as e:
        raise PermissionError(
            f"Cannot write service file {service_file}. "
            f"{'Run with sudo.' if system_wide else 'Check permissions.'}"
        ) from e

    # Reload systemd
    try:
        if system_wide:
            _run_systemctl(["daemon-reload"])
        else:
            _run_systemctl(["daemon-reload"], system_wide=False)
        logger.debug("Reloaded systemd daemon")
    except Exception as e:
        logger.warning(f"Could not reload systemd: {e}")

    # Enable service (start on boot)
    try:
        _run_systemctl(["enable", SERVICE_NAME], system_wide=system_wide)
        logger.info(f"Enabled {SERVICE_NAME} service")
    except Exception as e:
        logger.warning(f"Could not enable service: {e}")

    logger.info(
        f"Service installed successfully. Start with: "
        f"sudo systemctl start {SERVICE_NAME}"
        if system_wide
        else f"systemctl --user start {SERVICE_NAME}"
    )


def uninstall_systemd_service(system_wide: bool = True) -> None:
    """Remove the pysysfan systemd service.

    Args:
        system_wide: If True, uninstall system-wide service.
                     If False, uninstall user service.

    Raises:
        FileNotFoundError: If service not installed
        RuntimeError: If systemctl commands fail
    """
    # Determine service file path
    if system_wide:
        service_dir = SYSTEMD_SYSTEM_DIR
    else:
        service_dir = SYSTEMD_USER_DIR

    service_file = service_dir / f"{SERVICE_NAME}.service"

    if not service_file.exists():
        raise FileNotFoundError(f"Service not installed at {service_file}")

    # Stop service if running
    try:
        _run_systemctl(["stop", SERVICE_NAME], system_wide=system_wide, check=False)
        logger.debug(f"Stopped {SERVICE_NAME} service")
    except Exception as e:
        logger.debug(f"Could not stop service (may not be running): {e}")

    # Disable service
    try:
        _run_systemctl(["disable", SERVICE_NAME], system_wide=system_wide)
        logger.debug(f"Disabled {SERVICE_NAME} service")
    except Exception as e:
        logger.debug(f"Could not disable service: {e}")

    # Remove service file
    try:
        service_file.unlink()
        logger.info(f"Removed service file: {service_file}")
    except PermissionError as e:
        raise PermissionError(
            f"Cannot remove service file {service_file}. "
            f"{'Run with sudo.' if system_wide else 'Check permissions.'}"
        ) from e

    # Reload systemd
    try:
        _run_systemctl(["daemon-reload"], system_wide=system_wide)
        logger.debug("Reloaded systemd daemon")
    except Exception as e:
        logger.warning(f"Could not reload systemd: {e}")

    logger.info("Service uninstalled successfully")


def get_systemd_service_status(system_wide: bool = True) -> dict:
    """Get the status of the pysysfan systemd service.

    Args:
        system_wide: If True, check system-wide service.
                     If False, check user service.

    Returns:
        Dict with keys:
            - installed (bool): Whether service file exists
            - enabled (bool): Whether service is enabled
            - state (str | None): Current state (e.g., "active", "inactive")
            - service_file (str | None): Path to service file
    """
    result = {
        "installed": False,
        "enabled": False,
        "state": None,
        "service_file": None,
    }

    # Determine service file path
    if system_wide:
        service_dir = SYSTEMD_SYSTEM_DIR
    else:
        service_dir = SYSTEMD_USER_DIR

    service_file = service_dir / f"{SERVICE_NAME}.service"

    # Check if service file exists
    if service_file.exists():
        result["installed"] = True
        result["service_file"] = str(service_file)

    # Query systemd status
    try:
        proc = _run_systemctl(
            ["is-enabled", SERVICE_NAME],
            system_wide=system_wide,
            check=False,
        )
        result["enabled"] = proc.returncode == 0
    except Exception:
        result["enabled"] = False

    # Get current state
    try:
        proc = _run_systemctl(
            ["is-active", SERVICE_NAME],
            system_wide=system_wide,
            check=False,
        )
        if proc.returncode == 0:
            result["state"] = "active"
        else:
            # Try to get more detailed status
            proc = _run_systemctl(
                ["show", SERVICE_NAME, "--property=ActiveState"],
                system_wide=system_wide,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout:
                # Parse "ActiveState=xxx"
                for line in proc.stdout.strip().split("\n"):
                    if line.startswith("ActiveState="):
                        result["state"] = line.split("=", 1)[1]
                        break
            else:
                result["state"] = "inactive"
    except Exception:
        result["state"] = "unknown"

    return result
