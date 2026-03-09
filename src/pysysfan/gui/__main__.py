"""Entry point for pysysfan-gui command.

Usage:
    python -m pysysfan.gui
    pysysfan-gui (after pip install)
"""

import sys


def main():
    """Launch the GUI application."""
    # Import here to ensure GUI deps are only loaded when explicitly requested
    from pysysfan.gui import main as gui_main

    try:
        gui_main()
    except ImportError as e:
        print(f"Error: GUI dependencies not installed. {e}", file=sys.stderr)
        print("Install with: pip install pysysfan[gui]", file=sys.stderr)
        print("The desktop GUI now uses PySide6.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error launching GUI: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
