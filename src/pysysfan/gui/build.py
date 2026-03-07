"""Build script for the PySysFan GUI.

This script handles building both the web frontend (Svelte/Vite)
and the Tauri desktop application.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: Path, description: str) -> None:
    """Run a shell command and handle errors."""
    print(f"\n{'=' * 60}")
    print(f"{description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"Working directory: {cwd}")
    print("=" * 60)

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=False,
        )
        print(f"✓ {description} completed successfully")
        return result
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed with exit code {e.returncode}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"✗ Command not found: {cmd[0]}")
        print(f"  Make sure {cmd[0]} is installed and in your PATH")
        sys.exit(1)


def build_web(web_dir: Path, dev_mode: bool = False) -> None:
    """Build the web frontend."""
    print("\n🔨 Building Web Frontend (Svelte/Vite)")

    # Check for node_modules
    if not (web_dir / "node_modules").exists():
        print("Installing npm dependencies...")
        run_command(["npm", "install"], web_dir, "Installing npm packages")

    if dev_mode:
        # Start dev server
        print("\n🚀 Starting development server...")
        run_command(["npm", "run", "dev"], web_dir, "Running Vite dev server")
    else:
        # Build for production
        run_command(["npm", "run", "build"], web_dir, "Building web assets")


def build_tauri(tauri_dir: Path, dev_mode: bool = False) -> None:
    """Build the Tauri desktop application."""
    print("\n🖥️  Building Tauri Desktop App")

    if dev_mode:
        # Run Tauri in dev mode
        print("\n🚀 Starting Tauri in development mode...")
        run_command(["cargo", "tauri", "dev"], tauri_dir, "Running Tauri dev")
    else:
        # Build Tauri for production
        run_command(["cargo", "tauri", "build"], tauri_dir, "Building Tauri app")


def check_prerequisites() -> bool:
    """Check that required tools are installed."""
    print("\n📋 Checking Prerequisites")

    checks = [
        ("node", "Node.js"),
        ("npm", "npm"),
    ]

    all_ok = True
    for cmd, name in checks:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True)
            print(f"  ✓ {name} found")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"  ✗ {name} not found")
            all_ok = False

    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Build the PySysFan GUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s web              Build only the web frontend
  %(prog)s tauri            Build only the Tauri app
  %(prog)s all              Build both web and Tauri
  %(prog)s --dev            Run web frontend in dev mode
  %(prog)s tauri --dev      Run Tauri in dev mode
        """,
    )

    parser.add_argument(
        "target",
        choices=["web", "tauri", "all"],
        default="all",
        nargs="?",
        help="What to build (default: all)",
    )

    parser.add_argument(
        "--dev", action="store_true", help="Run in development mode instead of building"
    )

    parser.add_argument(
        "--skip-checks", action="store_true", help="Skip prerequisite checks"
    )

    args = parser.parse_args()

    # Find GUI directories
    gui_dir = Path(__file__).parent
    web_dir = gui_dir / "web"
    tauri_dir = gui_dir / "tauri"

    if not web_dir.exists():
        print(f"Error: Web directory not found: {web_dir}")
        sys.exit(1)

    # Check prerequisites
    if not args.skip_checks and not args.dev:
        if not check_prerequisites():
            print("\nPlease install missing prerequisites and try again.")
            sys.exit(1)

    # Build based on target
    if args.target in ("web", "all"):
        build_web(web_dir, dev_mode=args.dev)

    if args.target in ("tauri", "all"):
        if not tauri_dir.exists():
            print(f"Warning: Tauri directory not found: {tauri_dir}")
            print("Skipping Tauri build.")
        else:
            build_tauri(tauri_dir, dev_mode=args.dev)

    if not args.dev:
        print("\n" + "=" * 60)
        print("✓ Build completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    main()
