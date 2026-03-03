"""Linux installer for pysysfan.

This module provides automated installation of pysysfan on Linux systems,
including dependency installation, sensor setup, and service configuration.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Distribution families
DEBIAN_BASED = {"ubuntu", "debian", "linuxmint", "pop", "elementary", "zorin"}
RHEL_BASED = {"fedora", "rhel", "centos", "rocky", "almalinux", "oracle"}
ARCH_BASED = {"arch", "manjaro", "endeavouros", "garuda"}
SUSE_BASED = {"opensuse", "opensuse-tumbleweed", "opensuse-leap", "suse"}


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


def print_error(msg: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}ERROR: {msg}{Colors.NC}", file=sys.stderr)


def print_success(msg: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.NC}")


def print_warning(msg: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.NC}")


def print_info(msg: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {msg}{Colors.NC}")


def print_header(title: str) -> None:
    """Print section header."""
    print("")
    print(f"{Colors.BLUE}{'=' * 40}{Colors.NC}")
    print(f"{Colors.BLUE}  {title}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 40}{Colors.NC}")
    print("")


def detect_distro() -> tuple[str, str]:
    """Detect Linux distribution and family.

    Returns:
        Tuple of (distro_id, distro_family)
    """
    # Try /etc/os-release first
    os_release = Path("/etc/os-release")
    if os_release.exists():
        content = os_release.read_text()
        distro_id = ""
        for line in content.splitlines():
            if line.startswith("ID="):
                distro_id = line.split("=", 1)[1].strip('"').lower()
                break

        # Determine family
        if distro_id in DEBIAN_BASED:
            return distro_id, "debian"
        elif distro_id in RHEL_BASED:
            return distro_id, "rhel"
        elif distro_id in ARCH_BASED:
            return distro_id, "arch"
        elif distro_id in SUSE_BASED:
            return distro_id, "suse"
        else:
            return distro_id, "unknown"

    # Fallback detection
    if Path("/etc/arch-release").exists():
        return "arch", "arch"
    elif Path("/etc/redhat-release").exists():
        return "rhel", "rhel"
    elif Path("/etc/debian_version").exists():
        return "debian", "debian"

    return "unknown", "unknown"


def run_command(
    cmd: list[str],
    sudo: bool = False,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    """Run a shell command.

    Args:
        cmd: Command and arguments as list
        sudo: Whether to run with sudo
        check: Whether to raise on non-zero exit
        capture: Whether to capture output

    Returns:
        CompletedProcess instance
    """
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd

    logger.debug(f"Running: {' '.join(cmd)}")

    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    else:
        result = subprocess.run(cmd, check=False)

    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )

    return result


def install_system_deps(distro_family: str, dry_run: bool = False) -> bool:
    """Install system dependencies based on distribution.

    Args:
        distro_family: Distribution family (debian, rhel, arch, suse)
        dry_run: If True, only print what would be done

    Returns:
        True on success, False on failure
    """
    print_info(f"Installing dependencies for {distro_family}...")

    packages = {
        "debian": ["lm-sensors", "libsensors-dev", "python3", "python3-pip"],
        "rhel": ["lm_sensors", "lm_sensors-devel", "python3", "python3-pip"],
        "arch": ["lm_sensors", "python", "python-pip"],
        "suse": ["sensors", "libsensors4-devel", "python3", "python3-pip"],
    }

    if distro_family not in packages:
        print_warning(f"Unknown distribution family: {distro_family}")
        print_info("Please manually install: lm-sensors, python3, python3-pip")
        return False

    pkgs = packages[distro_family]

    if dry_run:
        print(f"Would install: {' '.join(pkgs)}")
        return True

    try:
        if distro_family == "debian":
            run_command(["apt-get", "update"], sudo=True, check=False)
            run_command(["apt-get", "install", "-y"] + pkgs, sudo=True)
        elif distro_family == "rhel":
            if shutil.which("dnf"):
                run_command(["dnf", "install", "-y"] + pkgs, sudo=True)
            else:
                run_command(["yum", "install", "-y"] + pkgs, sudo=True)
        elif distro_family == "arch":
            run_command(["pacman", "-S", "--noconfirm"] + pkgs, sudo=True)
        elif distro_family == "suse":
            run_command(["zypper", "install", "-y"] + pkgs, sudo=True)

        print_success("Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install packages: {e}")
        return False


def setup_sensors(dry_run: bool = False) -> bool:
    """Run sensors-detect to discover hardware sensors.

    Args:
        dry_run: If True, only print what would be done

    Returns:
        True on success, False on failure
    """
    print_header("Setting up hardware sensors")

    if dry_run:
        print("Would run: sensors-detect --auto")
        return True

    print_info("Running sensors-detect to discover hardware sensors...")

    try:
        run_command(["sensors-detect", "--auto"], sudo=True, check=False)
        print_success("Sensor setup complete")
        return True
    except Exception as e:
        print_warning(f"sensors-detect encountered issues: {e}")
        return False


def is_thinkpad() -> bool:
    """Detect if system is a ThinkPad.

    Returns:
        True if ThinkPad detected, False otherwise
    """
    dmi_path = Path("/sys/class/dmi/id")
    if not dmi_path.exists():
        return False

    try:
        product_name = (dmi_path / "product_name").read_text().strip()
        sys_vendor = (dmi_path / "sys_vendor").read_text().strip()

        return "thinkpad" in product_name.lower() or "lenovo" in sys_vendor.lower()
    except Exception:
        return False


def setup_thinkpad_fan_control(dry_run: bool = False) -> bool:
    """Setup ThinkPad-specific fan control.

    Args:
        dry_run: If True, only print what would be done

    Returns:
        True on success, False on failure
    """
    if not is_thinkpad():
        return False

    print_header("ThinkPad detected - Setting up fan control")

    modprobe_file = Path("/etc/modprobe.d/thinkpad-pysysfan.conf")
    modprobe_content = (
        "# Auto-generated by pysysfan\noptions thinkpad_acpi fan_control=1\n"
    )

    if dry_run:
        print(f"Would create: {modprobe_file}")
        print("Would reload thinkpad_acpi module")
        return True

    # Create modprobe config
    if not modprobe_file.exists():
        print_info("Creating modprobe configuration...")
        try:
            if os.geteuid() == 0:
                modprobe_file.write_text(modprobe_content)
            else:
                run_command(
                    ["tee", str(modprobe_file)],
                    sudo=True,
                    input=modprobe_content,
                )
            print_success("Modprobe configuration created")
        except Exception as e:
            print_warning(f"Could not create modprobe config: {e}")

    # Load module with fan_control
    try:
        run_command(
            ["modprobe", "thinkpad_acpi", "fan_control=1"],
            sudo=True,
            check=False,
        )

        if Path("/proc/acpi/ibm/fan").exists():
            print_success("ThinkPad fan control available at /proc/acpi/ibm/fan")
            return True
        else:
            print_warning("ThinkPad fan control not available (may require reboot)")
            return False
    except Exception as e:
        print_warning(f"Could not setup ThinkPad fan control: {e}")
        return False


def find_python_tool() -> Literal["uv", "pip3", "pip", ""]:
    """Find available Python package manager.

    Returns:
        Tool name or empty string if none found
    """
    for tool in ["uv", "pip3", "pip"]:
        if shutil.which(tool):
            return tool
    return ""


def install_pysysfan_package(dry_run: bool = False) -> bool:
    """Install pysysfan Python package.

    Args:
        dry_run: If True, only print what would be done

    Returns:
        True on success, False on failure
    """
    print_header("Installing pysysfan")

    tool = find_python_tool()
    if not tool:
        print_error("No Python package manager found (tried: uv, pip3, pip)")
        print_info(
            "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
        )
        return False

    print_info(f"Using {tool}...")

    if dry_run:
        if tool == "uv":
            print("Would run: uv tool install pysysfan[linux]")
        else:
            print(f"Would run: {tool} install --user pysysfan[linux]")
        return True

    try:
        if tool == "uv":
            run_command(["uv", "tool", "install", "pysysfan[linux]"])
        else:
            run_command([tool, "install", "--user", "pysysfan[linux]"])

        print_success("pysysfan installed")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install pysysfan: {e}")
        return False


def generate_config(dry_run: bool = False) -> bool:
    """Generate initial pysysfan configuration.

    Args:
        dry_run: If True, only print what would be done

    Returns:
        True on success, False on failure
    """
    print_header("Generating configuration")

    if dry_run:
        print("Would run: pysysfan config init --force")
        return True

    if not shutil.which("pysysfan"):
        print_warning("pysysfan not in PATH - skipping config generation")
        print_info("Run 'pysysfan config init' after reloading your shell")
        return False

    try:
        run_command(["pysysfan", "config", "init", "--force"])
        print_success("Configuration created at ~/.pysysfan/config.yaml")
        return True
    except subprocess.CalledProcessError as e:
        print_warning(f"Could not generate config: {e}")
        return False


def install_systemd_service(user_service: bool = False, dry_run: bool = False) -> bool:
    """Install systemd service for pysysfan.

    Args:
        user_service: If True, install user service instead of system-wide
        dry_run: If True, only print what would be done

    Returns:
        True on success, False on failure
    """
    print_header("Installing systemd service")

    if dry_run:
        if user_service:
            print("Would run: pysysfan service install --user")
        else:
            print("Would run: sudo pysysfan service install")
        return True

    if not shutil.which("pysysfan"):
        print_warning("pysysfan not in PATH - cannot install service")
        return False

    try:
        if user_service:
            run_command(["pysysfan", "service", "install", "--user"])
            print_success("User service installed")
            print_info("Start: systemctl --user start pysysfan")
        else:
            run_command(["pysysfan", "service", "install"], sudo=True)
            print_success("System service installed")
            print_info("Start: sudo systemctl start pysysfan")
        return True
    except subprocess.CalledProcessError as e:
        print_warning(f"Could not install service: {e}")
        return False


def main() -> int:
    """Main installer entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Install pysysfan on Linux systems",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Interactive installation
  %(prog)s --user                   # Install user service only
  %(prog)s --no-service             # Install without service
  %(prog)s --dry-run                # Preview installation steps
        """,
    )

    parser.add_argument(
        "--user",
        action="store_true",
        help="Install user service instead of system-wide",
    )
    parser.add_argument(
        "--no-service",
        action="store_true",
        help="Skip service installation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Print welcome
    print_header("pysysfan Linux Installer")

    if args.dry_run:
        print_info("DRY RUN MODE - No changes will be made")
        print("")

    # Detect distribution
    distro, family = detect_distro()
    print_info(f"Detected: {distro} ({family})")
    print("")

    # Confirm installation
    if not args.dry_run:
        print("This will:")
        print("  1. Install system dependencies (lm-sensors)")
        print("  2. Detect and configure hardware sensors")
        print("  3. Install pysysfan Python package")
        print("  4. Generate initial configuration")
        if not args.no_service:
            if args.user:
                print("  5. Install user systemd service")
            else:
                print("  5. Install system-wide systemd service")
        print("")

        response = input("Continue? [Y/n] ")
        if response.lower() not in ("", "y", "yes"):
            print_info("Installation cancelled")
            return 0

    success = True

    # Install dependencies
    if not install_system_deps(family, args.dry_run):
        success = False

    # Setup sensors
    setup_sensors(args.dry_run)

    # Setup ThinkPad if applicable
    if is_thinkpad():
        setup_thinkpad_fan_control(args.dry_run)

    # Install pysysfan
    if not install_pysysfan_package(args.dry_run):
        success = False

    # Generate config
    generate_config(args.dry_run)

    # Install service
    if not args.no_service:
        install_systemd_service(args.user, args.dry_run)

    # Print completion
    print_header("Installation Complete!")

    print("Next steps:")
    print("  pysysfan config show          # View configuration")
    print("  sudo pysysfan scan            # Scan for sensors")
    print("  sudo pysysfan run --once      # Test daemon")
    print("  sudo pysysfan monitor         # Start monitoring")
    print("")

    if not args.no_service:
        if args.user:
            print("Service commands:")
            print("  systemctl --user start pysysfan")
            print("  systemctl --user enable pysysfan")
        else:
            print("Service commands:")
            print("  sudo systemctl start pysysfan")
            print("  pysysfan service status")
        print("")

    print("Documentation: https://github.com/anomalyco/pysysfan")
    print("")
    print_success("Thank you for installing pysysfan!")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
