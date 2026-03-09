"""Safe daemon stop strategies."""

from __future__ import annotations

import logging
import time
from enum import Enum
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8765


class StopMethod(Enum):
    """Methods for stopping the daemon."""

    GRACEFUL_API = "graceful_api"
    SIGTERM = "sigterm"
    TASKKILL = "taskkill"
    FAILED = "failed"


def find_daemon_process() -> psutil.Process | None:
    """Find running pysysfan daemon process.

    Returns:
        psutil.Process if found, None otherwise.
    """
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline", [])
            if not cmdline:
                continue

            cmdline_str = " ".join(cmdline)

            # Check if this is pysysfan daemon
            if "pysysfan" in cmdline_str and "run" in cmdline:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return None


def build_local_api_base_url(
    api_host: str = DEFAULT_API_HOST, api_port: int = DEFAULT_API_PORT
) -> str:
    """Build a loopback-safe base URL for the daemon API."""
    normalized_host = api_host.strip() if api_host else DEFAULT_API_HOST
    if normalized_host in {"0.0.0.0", "::", "[::]"}:
        normalized_host = DEFAULT_API_HOST
    return f"http://{normalized_host}:{api_port}"


def stop_daemon_graceful(
    timeout: float = 10.0,
    api_host: str = DEFAULT_API_HOST,
    api_port: int = DEFAULT_API_PORT,
) -> tuple[bool, StopMethod]:
    """Attempt to stop daemon gracefully with fallback strategies.

    Tries methods in order:
    1. API graceful shutdown (if API is responding)
    2. SIGTERM to the process
    3. Force kill (SIGKILL)

    Args:
        timeout: Timeout in seconds for graceful exit attempts.
        api_host: Host where the daemon API is listening.
        api_port: Port where the daemon API is listening.

    Returns:
        Tuple of (success, method_used)
    """
    # Method 1: Try API graceful shutdown
    try:
        import requests

        from pysysfan.api.auth import load_token

        token = load_token()
        if token:
            base_url = build_local_api_base_url(api_host=api_host, api_port=api_port)
            response = requests.post(
                f"{base_url}/api/service/shutdown",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )

            if response.status_code == 200:
                logger.info("Daemon stop requested via API")

                # Wait for process to exit
                start = time.time()
                while time.time() - start < timeout:
                    if not find_daemon_process():
                        logger.info("Daemon exited gracefully")
                        return True, StopMethod.GRACEFUL_API
                    time.sleep(0.5)

                logger.warning("Daemon did not exit within timeout")
    except Exception as e:
        logger.debug(f"API shutdown failed: {e}")

    # Method 2: Find process and send SIGTERM
    proc = find_daemon_process()
    if proc:
        try:
            logger.info(f"Sending SIGTERM to daemon (PID {proc.pid})")
            proc.terminate()

            # Wait for graceful exit
            try:
                proc.wait(timeout=timeout)
                logger.info("Daemon terminated via SIGTERM")
                return True, StopMethod.SIGTERM
            except psutil.TimeoutExpired:
                logger.warning("Daemon did not respond to SIGTERM")
        except psutil.NoSuchProcess:
            # Process already exited
            return True, StopMethod.SIGTERM
        except Exception as e:
            logger.error(f"SIGTERM failed: {e}")

    # Method 3: Force kill (last resort)
    proc = find_daemon_process()
    if proc:
        try:
            logger.warning(f"Force killing daemon (PID {proc.pid})")
            proc.kill()
            proc.wait(timeout=5.0)
            logger.info("Daemon killed")
            return True, StopMethod.TASKKILL
        except Exception as e:
            logger.error(f"Force kill failed: {e}")
            return False, StopMethod.FAILED

    # No process found - already stopped
    return True, StopMethod.GRACEFUL_API


def get_recent_logs(lines: int = 100) -> list[str]:
    """Get recent daemon logs from log file.

    Args:
        lines: Number of lines to return (from end of file).

    Returns:
        List of log lines.
    """
    log_file = Path.home() / ".pysysfan" / "daemon.log"

    if not log_file.exists():
        return []

    try:
        with open(log_file, encoding="utf-8") as f:
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-lines:]]
    except Exception as e:
        logger.warning(f"Failed to read logs: {e}")
        return []
