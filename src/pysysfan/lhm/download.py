"""Download LibreHardwareMonitor releases from GitHub."""

import io
import zipfile
from pathlib import Path

import click
import requests

from pysysfan.lhm import LHM_DIR, LHM_DLL_NAME

# GitHub API for LHM releases
LHM_REPO = "LibreHardwareMonitor/LibreHardwareMonitor"
LHM_API_URL = f"https://api.github.com/repos/{LHM_REPO}/releases/latest"


def get_latest_release_info() -> dict:
    """Fetch the latest LHM release info from GitHub API."""
    resp = requests.get(LHM_API_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def find_zip_asset(release: dict) -> dict | None:
    """Find the net472 (.NET Framework) release ZIP asset.

    We prefer the net472 build because:
    - .NET Framework 4.7.2 is pre-installed on all Windows 10/11 machines
    - .NET Core/.NET 5+ builds require the specific runtime version installed
    - pythonnet's netfx runtime works reliably with net472 assemblies

    The net472 build is typically named 'LibreHardwareMonitor.zip' while
    the .NET Core build is named 'LibreHardwareMonitor.NET.XX.zip'.
    """
    # First pass: prefer the plain zip (net472 build, no .NET version in name)
    for asset in release.get("assets", []):
        name = asset["name"]
        if name.lower().endswith(".zip") and "librehardwaremonitor" in name.lower():
            # Skip .NET Core builds (e.g., LibreHardwareMonitor.NET.10.zip)
            if ".net." not in name.lower():
                return asset

    # Fallback: any zip with the right name
    for asset in release.get("assets", []):
        name = asset["name"].lower()
        if name.endswith(".zip") and "librehardwaremonitor" in name:
            return asset
    return None


def download_and_extract_dll(asset: dict, target_dir: Path) -> Path:
    """Download a release ZIP and extract LibreHardwareMonitorLib.dll."""
    click.echo(
        f"  Downloading {asset['name']} ({asset['size'] / 1024 / 1024:.1f} MB)..."
    )

    resp = requests.get(asset["browser_download_url"], timeout=120, stream=True)
    resp.raise_for_status()

    content = io.BytesIO(resp.content)

    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(content) as zf:
        # Verify the main DLL is in the archive
        dll_entries = [
            name
            for name in zf.namelist()
            if name.lower().endswith(LHM_DLL_NAME.lower())
        ]

        if not dll_entries:
            raise FileNotFoundError(
                f"{LHM_DLL_NAME} not found in {asset['name']}. "
                f"Archive contents: {zf.namelist()}"
            )

        # Extract ALL DLLs and related files (the net472 build has many
        # runtime dependencies like System.Memory.dll, HidSharp.dll, etc.)
        for entry in zf.namelist():
            basename = Path(entry).name
            if not basename:  # skip directory entries
                continue
            # Extract DLLs, PDBs, XML docs, and config files
            ext = Path(basename).suffix.lower()
            if ext in (".dll", ".pdb", ".xml", ".config", ".exe"):
                target_path = target_dir / basename
                with zf.open(entry) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())
                click.echo(f"  Extracted: {basename}")

    dll_path = target_dir / LHM_DLL_NAME
    if not dll_path.is_file():
        raise FileNotFoundError(
            f"Expected {dll_path} after extraction but it's missing."
        )

    return dll_path


def get_installed_version(target_dir: Path | None = None) -> str | None:
    """Read the locally recorded LHM version, or None if not recorded."""
    lib_dir = target_dir if target_dir else LHM_DIR
    version_file = lib_dir / ".lhm_version"
    if version_file.is_file():
        lines = version_file.read_text().strip().splitlines()
        if lines:
            return lines[0]
    return None


def download_latest(target_dir: Path | None = None) -> Path:
    """Download the latest LHM release and extract the DLL.

    Skips the download if the installed version already matches the
    latest release on GitHub.

    Args:
        target_dir: Directory to extract to. Defaults to ~/.pysysfan/lib/

    Returns:
        Path to the extracted DLL.
    """
    if target_dir is None:
        target_dir = LHM_DIR

    click.echo("Fetching latest LibreHardwareMonitor release...")
    release = get_latest_release_info()
    version = release.get("tag_name", "unknown")
    click.echo(f"  Latest version: {version}")

    # Check if already up-to-date
    installed_version = get_installed_version(target_dir)
    dll_path = target_dir / LHM_DLL_NAME
    if installed_version == version and dll_path.is_file():
        click.echo(f"\n  ✓ LHM {version} is already installed and up-to-date.")
        return dll_path

    asset = find_zip_asset(release)
    if asset is None:
        raise RuntimeError(
            f"No suitable ZIP asset found in LHM release {version}. "
            f"Please download manually from: {release.get('html_url', LHM_REPO)}"
        )

    dll_path = download_and_extract_dll(asset, target_dir)

    # Write a version marker file
    version_file = target_dir / ".lhm_version"
    version_file.write_text(f"{version}\n{asset['name']}\n")

    click.echo(
        f"\n  ✓ LibreHardwareMonitorLib.dll ({version}) installed to {target_dir}"
    )
    return dll_path
