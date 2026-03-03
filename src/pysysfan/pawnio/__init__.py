"""PawnIO driver management.

PawnIO is a scriptable universal kernel driver for hardware access,
used by pysysfan to communicate with SuperIO chips for fan control.
See https://pawnio.eu/ for details.
"""

import logging
import subprocess

logger = logging.getLogger(__name__)

# GitHub repository for PawnIO setup installer
PAWNIO_REPO = "namazso/PawnIO.Setup"
PAWNIO_API_URL = f"https://api.github.com/repos/{PAWNIO_REPO}/releases/latest"

# Windows service name registered by the PawnIO driver
PAWNIO_SERVICE_NAME = "PawnIO"


def is_pawnio_installed() -> bool:
    """Check whether the PawnIO driver service is registered on this system.

    Uses ``sc query`` to probe the Windows service manager for the
    PawnIO driver service.

    Returns:
        True if the service exists (any state), False otherwise.
    """
    try:
        result = subprocess.run(
            ["sc", "query", PAWNIO_SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # sc query returns 0 when the service exists
        return result.returncode == 0
    except Exception as exc:
        logger.debug("Failed to query PawnIO service: %s", exc)
        return False


def get_pawnio_status() -> dict:
    """Return a status dict describing the PawnIO driver.

    Keys:
        installed (bool): Whether the service is registered.
        state (str | None): Service state string if installed
            (e.g. "RUNNING", "STOPPED").
    """
    status: dict = {"installed": False, "state": None}

    try:
        result = subprocess.run(
            ["sc", "query", PAWNIO_SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return status

        status["installed"] = True
        # Parse the STATE line, e.g. "        STATE              : 4  RUNNING"
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("STATE"):
                # Extract the human-readable state after the last whitespace
                parts = stripped.split()
                if parts:
                    status["state"] = parts[-1]
                break
    except Exception as exc:
        logger.debug("Failed to query PawnIO service: %s", exc)

    return status
