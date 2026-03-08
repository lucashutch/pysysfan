"""GUI package - lazy loaded to avoid importing Qt/Svelte dependencies."""

# This file is intentionally minimal.
# All imports should be done within functions to avoid
# loading GUI dependencies when using CLI only.

__all__ = ["main"]


def main():
    """Entry point for pysysfan-gui command.

    This function is only called when the GUI is explicitly launched.
    All GUI-specific imports happen inside this function.
    """
    # Import here to avoid loading GUI deps on CLI-only usage
    from pysysfan.gui.web import launch_gui

    launch_gui()
