"""Independent entry points for installing pysysfan dependencies.

These entry points are designed to be called from a batch installer
script or other automation tools, separate from the main CLI.

Entry points:
    pysysfan-install-lhm    → install_lhm()
    pysysfan-install-pawnio → install_pawnio()
"""

import sys

import click

from pysysfan.lhm.download import download_latest
from pysysfan.pawnio.download import install_pawnio as _do_install


@click.command()
@click.option(
    "--target",
    "-t",
    type=click.Path(),
    default=None,
    help="Directory to install LHM into. Default: ~/.pysysfan/lib/",
)
def install_lhm(target: str | None) -> None:
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
