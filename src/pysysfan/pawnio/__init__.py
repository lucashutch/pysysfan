"""PawnIO driver management.

PawnIO is a scriptable universal kernel driver for hardware access,
used by pysysfan to communicate with SuperIO chips for fan control.
See https://pawnio.eu/ for details.
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# GitHub repository for PawnIO setup installer
PAWNIO_REPO = "namazso/PawnIO.Setup"
PAWNIO_API_URL = f"https://api.github.com/repos/{PAWNIO_REPO}/releases/latest"

# Windows service name registered by the PawnIO driver
PAWNIO_SERVICE_NAME = "PawnIO"


_PAWNIO_VERSION_MARKER_FILE = Path.home() / ".pysysfan" / ".pawnio_version"


def _read_pawnio_version_marker(marker_file: Path | None = None) -> str | None:
    """Read PawnIO version from the local marker file (if present)."""
    if marker_file is None:
        marker_file = _PAWNIO_VERSION_MARKER_FILE
    try:
        if marker_file.is_file():
            lines = marker_file.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                return lines[0]
    except OSError:
        return None
    return None


def get_installed_pawnio_version() -> str | None:
    """Return the installed PawnIO version.

    Windows "Installed apps" reads the version from the uninstaller registry
    entry (DisplayVersion). We do the same for a UI-accurate result.

    Falls back to the local marker file used by the installer.
    """

    if sys.platform != "win32":
        return _read_pawnio_version_marker()

    try:
        import winreg
    except Exception:
        return _read_pawnio_version_marker()

    uninstall_keys = [
        r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
        r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
    ]

    def _normalize_version(raw: object) -> str | None:
        if raw is None:
            return None
        version = str(raw).strip()
        if not version:
            return None
        if not version.lower().startswith("v"):
            version = f"v{version}"
        return version

    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key_path in uninstall_keys:
            try:
                with winreg.OpenKey(root, key_path) as key:
                    subkey_count = winreg.QueryInfoKey(key)[0]
                    for i in range(subkey_count):
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(
                            root, f"{key_path}\\{subkey_name}"
                        ) as subkey:
                            try:
                                display_name, _ = winreg.QueryValueEx(
                                    subkey, "DisplayName"
                                )
                            except FileNotFoundError:
                                continue

                            if "pawnio" not in str(display_name).lower():
                                continue

                            # Windows “Installed apps” typically uses
                            # DisplayVersion but some installers only set
                            # Version.
                            display_version = None
                            try:
                                display_version, _ = winreg.QueryValueEx(
                                    subkey, "DisplayVersion"
                                )
                            except FileNotFoundError:
                                pass
                            if display_version is None:
                                try:
                                    display_version, _ = winreg.QueryValueEx(
                                        subkey, "Version"
                                    )
                                except FileNotFoundError:
                                    pass

                            normalized = _normalize_version(display_version)
                            if normalized:
                                return normalized
            except Exception:
                # Ignore missing keys or access failures.
                continue

    return _read_pawnio_version_marker()


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
