"""Self-update functionality for pysysfan.

Checks the GitHub Releases API for new versions and upgrades via
``uv tool install --force``.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

import requests
from packaging.version import Version, InvalidVersion

from pysysfan import __version__

logger = logging.getLogger(__name__)

# GitHub repository for pysysfan releases
REPO = "lucashutch/pysysfan"
RELEASES_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
REPO_GIT_URL = f"https://github.com/{REPO}.git"


@dataclass
class UpdateInfo:
    """Result of an update check."""

    available: bool
    current_version: str
    latest_version: str
    release_url: str = ""
    release_notes: str = ""


def get_current_version() -> str:
    """Return the currently installed pysysfan version string."""
    return __version__


def get_latest_release_info() -> dict:
    """Fetch the latest pysysfan release info from the GitHub API."""
    resp = requests.get(RELEASES_API_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _normalise_tag(tag: str) -> str:
    """Strip a leading ``v`` prefix from a tag name (e.g. ``v0.3.0`` → ``0.3.0``)."""
    return tag.lstrip("v")


def _is_newer(current_raw: str, latest_raw: str) -> bool:
    """Return True if *latest_raw* is strictly newer than *current_raw*.

    Falls back to a simple string comparison when either value is not a
    valid PEP 440 version (e.g. ``0.0.0-dev``).
    """
    try:
        return Version(_normalise_tag(latest_raw)) > Version(
            _normalise_tag(current_raw)
        )
    except InvalidVersion:
        return _normalise_tag(latest_raw) != _normalise_tag(current_raw)


def check_for_update() -> UpdateInfo:
    """Compare the installed version against the latest GitHub release.

    Returns:
        An :class:`UpdateInfo` describing whether an update is available.

    Raises:
        requests.RequestException: On network / API errors.
    """
    release = get_latest_release_info()
    latest_tag = release.get("tag_name", "")
    current = get_current_version()

    return UpdateInfo(
        available=_is_newer(current, latest_tag),
        current_version=current,
        latest_version=latest_tag,
        release_url=release.get("html_url", ""),
        release_notes=release.get("body", "") or "",
    )


def perform_update(version_tag: str) -> subprocess.CompletedProcess:
    """Upgrade pysysfan to *version_tag* using ``uv tool install``.

    Args:
        version_tag: The Git tag to install (e.g. ``v0.3.0``).

    Returns:
        The :class:`subprocess.CompletedProcess` from the install command.

    Raises:
        subprocess.CalledProcessError: If ``uv`` exits with a non-zero code.
    """
    install_url = f"git+{REPO_GIT_URL}@{version_tag}"
    logger.info(
        "Upgrading pysysfan to %s via: uv tool install %s --force",
        version_tag,
        install_url,
    )

    result = subprocess.run(
        ["uv", "tool", "install", install_url, "--force"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    result.check_returncode()
    return result
