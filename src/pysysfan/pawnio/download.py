"""Download and install the PawnIO driver from GitHub."""

import subprocess
import tempfile
from pathlib import Path

import click
import requests

from pysysfan.pawnio import PAWNIO_API_URL, is_pawnio_installed

# Version marker file lives alongside the LHM libs
_PAWNIO_VERSION_DIR = Path.home() / ".pysysfan"
_PAWNIO_VERSION_FILE = _PAWNIO_VERSION_DIR / ".pawnio_version"


def get_latest_release_info() -> dict:
    """Fetch the latest PawnIO.Setup release info from the GitHub API."""
    resp = requests.get(PAWNIO_API_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def find_setup_asset(release: dict) -> dict | None:
    """Find the ``PawnIO_setup.exe`` asset in a GitHub release.

    Args:
        release: JSON dict from the GitHub releases API.

    Returns:
        The matching asset dict, or ``None`` if not found.
    """
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.lower() == "pawnio_setup.exe":
            return asset
    # Fallback: any exe asset
    for asset in release.get("assets", []):
        name = asset.get("name", "").lower()
        if name.endswith(".exe") and "pawnio" in name:
            return asset
    return None


def get_installed_version() -> str | None:
    """Read the locally recorded PawnIO version, or None if not recorded."""
    if _PAWNIO_VERSION_FILE.is_file():
        lines = _PAWNIO_VERSION_FILE.read_text().strip().splitlines()
        if lines:
            return lines[0]
    return None


def download_setup(asset: dict, target_dir: Path | None = None) -> Path:
    """Download the PawnIO setup executable.

    Args:
        asset: GitHub release asset dict (must have
            ``browser_download_url``, ``name``, ``size``).
        target_dir: Directory to save the file to.  Defaults to a
            temporary directory.

    Returns:
        Path to the downloaded setup executable.
    """
    if target_dir is None:
        target_dir = Path(tempfile.mkdtemp(prefix="pysysfan_pawnio_"))
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    size_mb = asset["size"] / 1024 / 1024
    click.echo(f"  Downloading {asset['name']} ({size_mb:.1f} MB)...")

    resp = requests.get(asset["browser_download_url"], timeout=120, stream=True)
    resp.raise_for_status()

    setup_path = target_dir / asset["name"]
    with open(setup_path, "wb") as f:
        f.write(resp.content)

    click.echo(f"  Downloaded to: {setup_path}")
    return setup_path


def _find_uninstall_command() -> str | None:
    """Look up the PawnIO uninstall command from the Windows registry."""
    import winreg

    uninstall_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key_path in uninstall_keys:
            try:
                with winreg.OpenKey(root, key_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if "pawnio" in str(name).lower():
                                    cmd, _ = winreg.QueryValueEx(
                                        subkey, "UninstallString"
                                    )
                                    return str(cmd)
                        except (OSError, FileNotFoundError):
                            continue
            except (OSError, FileNotFoundError):
                continue
    return None


def install_pawnio() -> None:
    """Download and launch the latest PawnIO driver installer.

    Skips the download if PawnIO is already installed and the version
    matches the latest release.  When upgrading, the existing PawnIO
    installation is uninstalled first.  The installer is launched with
    administrator privileges via PowerShell ``Start-Process -Verb RunAs``.
    """
    click.echo("Fetching latest PawnIO release...")
    release = get_latest_release_info()
    version = release.get("tag_name", "unknown")
    click.echo(f"  Latest version: {version}")

    already_installed = is_pawnio_installed()
    installed_version = get_installed_version()

    # If PawnIO service exists but we have no version marker, assume
    # the current release is installed and record the marker.
    if already_installed and installed_version is None:
        click.echo(f"\n  ✓ PawnIO is already installed (recording version {version}).")
        _PAWNIO_VERSION_DIR.mkdir(parents=True, exist_ok=True)
        _PAWNIO_VERSION_FILE.write_text(f"{version}\n")
        return

    # Already up-to-date
    if already_installed and installed_version == version:
        click.echo(f"\n  ✓ PawnIO {version} is already installed and up-to-date.")
        return

    # Upgrading: uninstall old version first
    if already_installed and installed_version != version:
        click.echo(f"\n  Upgrading PawnIO from {installed_version} to {version}...")
        uninstall_cmd = _find_uninstall_command()
        if uninstall_cmd:
            click.echo("  Uninstalling previous PawnIO version...")
            try:
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        f"Start-Process -FilePath '{uninstall_cmd}' -Verb RunAs -Wait",
                    ],
                    timeout=120,
                )
            except Exception as exc:
                click.echo(f"  ⚠ Uninstall failed: {exc}")
                click.echo("  Please uninstall PawnIO manually and try again.")
                return
        else:
            click.echo(
                "  ⚠ Could not find PawnIO uninstaller in registry.\n"
                "  Please uninstall PawnIO manually before upgrading."
            )
            return

    asset = find_setup_asset(release)
    if asset is None:
        raise RuntimeError(
            f"No PawnIO_setup.exe found in release {version}. "
            f"Please download manually from: {release.get('html_url', '')}"
        )

    setup_path = download_setup(asset)

    click.echo("\n  Launching PawnIO installer (requesting admin privileges)...")
    click.echo("  Please follow the installer prompts to complete installation.\n")

    try:
        # Launch the installer elevated via PowerShell Start-Process
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Start-Process -FilePath '{setup_path}' -Verb RunAs -Wait",
            ],
            timeout=300,
        )
        if proc.returncode == 0:
            # Write version marker
            _PAWNIO_VERSION_DIR.mkdir(parents=True, exist_ok=True)
            _PAWNIO_VERSION_FILE.write_text(f"{version}\n")
            click.echo(f"\n  ✓ PawnIO installer ({version}) completed successfully.")
        else:
            click.echo(f"\n  ⚠ PawnIO installer exited with code {proc.returncode}.")
    except subprocess.TimeoutExpired:
        click.echo("\n  ⚠ PawnIO installer timed out (5 min). Please run it manually.")
    except Exception as exc:
        click.echo(f"\n  ✗ Failed to run PawnIO installer: {exc}")
        raise
