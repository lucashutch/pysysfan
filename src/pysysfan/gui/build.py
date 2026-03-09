"""Desktop GUI helper commands for the PySide6 migration."""

from __future__ import annotations

import argparse
import importlib.util


def _module_available(name: str) -> bool:
    """Return whether a Python module is importable."""
    return importlib.util.find_spec(name) is not None


def check_prerequisites() -> int:
    """Validate the Python desktop GUI dependencies are installed."""
    missing = [module for module in ("PySide6",) if not _module_available(module)]
    if missing:
        print("Missing GUI dependencies:")
        for module in missing:
            print(f"- {module}")
        print("Install them with: uv sync --extra gui")
        return 1

    print("Desktop GUI dependencies are available.")
    return 0


def launch_gui() -> int:
    """Launch the PySide6 GUI."""
    from pysysfan.gui.desktop import launch_gui as _launch_gui

    return _launch_gui()


def main() -> int:
    parser = argparse.ArgumentParser(description="PySysFan desktop GUI helper")
    parser.add_argument(
        "command",
        choices=["check", "launch"],
        default="check",
        nargs="?",
        help="Validate GUI prerequisites or launch the desktop GUI",
    )
    args = parser.parse_args()

    if args.command == "launch":
        return launch_gui()
    return check_prerequisites()


if __name__ == "__main__":
    raise SystemExit(main())
