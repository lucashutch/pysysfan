"""Independent entry points for installing pysysfan dependencies.

These entry points are designed to be called from a batch installer
script or other automation tools, separate from the main CLI.

Entry points:
    pysysfan-install-lhm    → install_lhm (group: download, info)
    pysysfan-install-pawnio → install_pawnio()
"""

import sys

import click

from pysysfan.lhm import get_lhm_dll_path, LHM_DIR
from pysysfan.lhm.download import download_latest
from pysysfan.pawnio.download import install_pawnio as _do_install


@click.group()
def install_lhm():
    """Manage LibreHardwareMonitor installation."""
    pass


@install_lhm.command("download")
@click.option(
    "--target",
    "-t",
    type=click.Path(),
    default=None,
    help="Directory to install LHM into. Default: ~/.pysysfan/lib/",
)
def lhm_download(target: str | None) -> None:
    """Download and install LibreHardwareMonitor.

    Downloads the latest LHM release from GitHub and extracts the
    required DLLs to the pysysfan lib directory.
    """
    from pathlib import Path

    target_dir = Path(target) if target else None

    try:
        download_latest(target_dir)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@install_lhm.command("info")
def lhm_info() -> None:
    """Show information about the installed LHM library."""
    try:
        dll_path = get_lhm_dll_path()
        click.echo(f"[bold green]✓[/] DLL found: {dll_path}")
    except FileNotFoundError as e:
        click.echo(f"[bold red]✗[/] {e}")
        sys.exit(1)

    version_file = LHM_DIR / ".lhm_version"
    if version_file.is_file():
        lines = version_file.read_text().strip().split("\n")
        if lines:
            click.echo(f"  Release: {lines[0]}")
        if len(lines) > 1:
            click.echo(f"  Asset: {lines[1]}")


@click.command()
def install_pawnio() -> None:
    """Download and install the PawnIO driver.

    Downloads the latest PawnIO setup executable from GitHub and
    launches it.  The PawnIO installer is a GUI application — follow
    the on-screen prompts to complete installation.
    """
    try:
        _do_install()
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
