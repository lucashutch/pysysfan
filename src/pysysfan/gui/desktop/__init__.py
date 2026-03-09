"""PySide6 desktop GUI launcher.

This module stays lightweight so importing `pysysfan.gui` does not pull in
PySide6 until the GUI is explicitly launched.
"""

from __future__ import annotations

__all__ = ["launch_gui"]


def launch_gui() -> int:
    """Launch the desktop GUI application."""
    from pysysfan.gui.desktop.app import launch_gui as _launch_gui

    return _launch_gui()
