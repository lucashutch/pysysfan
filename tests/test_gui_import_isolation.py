"""Tests for GUI import isolation.

These tests ensure that importing pysysfan modules does not
automatically import GUI dependencies, which keeps CLI startup fast
and avoids unnecessary dependency loading.
"""

import sys
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def preserve_sys_modules():
    """Save and restore sys.modules to prevent test pollution."""
    original_modules = sys.modules.copy()
    yield
    # Restore modules, but also keep any new modules that were added
    # We need to restore the original pysysfan modules to prevent pollution
    for key in list(sys.modules.keys()):
        if key.startswith("pysysfan") and key not in original_modules:
            del sys.modules[key]
    # Restore original pysysfan modules
    for key, value in original_modules.items():
        if key.startswith("pysysfan"):
            sys.modules[key] = value


class TestGUIImportIsolation:
    """Test that GUI imports are isolated and lazy-loaded."""

    def test_cli_import_does_not_import_gui(self):
        """Verify that importing cli module does not load GUI components."""
        # Clear any existing imports
        modules_to_clear = [
            key for key in sys.modules.keys() if key.startswith("pysysfan")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]

        # Import CLI - side effect test
        from pysysfan import cli  # noqa: F401

        # Verify GUI modules are not loaded
        gui_modules = [key for key in sys.modules.keys() if "pysysfan.gui" in key]
        assert len(gui_modules) == 0, f"GUI modules loaded unexpectedly: {gui_modules}"

    def test_config_import_does_not_import_gui(self):
        """Verify that importing config module does not load GUI components."""
        # Clear modules
        modules_to_clear = [
            key for key in sys.modules.keys() if key.startswith("pysysfan")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]

        # Import config - side effect test
        from pysysfan import config  # noqa: F401

        # Verify GUI modules are not loaded
        gui_modules = [key for key in sys.modules.keys() if "pysysfan.gui" in key]
        assert len(gui_modules) == 0, f"GUI modules loaded unexpectedly: {gui_modules}"

    def test_daemon_import_does_not_import_gui(self):
        """Verify that importing daemon module does not load GUI components."""
        # Clear modules
        modules_to_clear = [
            key for key in sys.modules.keys() if key.startswith("pysysfan")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]

        # Import daemon - side effect test
        from pysysfan import daemon  # noqa: F401

        # Verify GUI modules are not loaded
        gui_modules = [key for key in sys.modules.keys() if "pysysfan.gui" in key]
        assert len(gui_modules) == 0, f"GUI modules loaded unexpectedly: {gui_modules}"

    def test_gui_module_is_empty_on_init(self):
        """Verify that pysysfan.gui __init__ is minimal and lazy."""
        from pysysfan import gui

        # The __init__ should only expose 'main'
        assert hasattr(gui, "main")

        # The docstring should mention lazy loading
        assert "lazy" in gui.__doc__.lower()

    def test_gui_desktop_module_exports_launch_function(self):
        """Verify the desktop module exports a launch function."""
        from pysysfan.gui import desktop

        assert hasattr(desktop, "launch_gui")
        assert callable(desktop.launch_gui)

    def test_gui_main_imports_desktop_launcher_on_call(self):
        """Verify GUI main delegates to the desktop launcher lazily."""
        from pysysfan import gui

        with mock.patch("pysysfan.gui.desktop.launch_gui") as mock_launch:
            gui.main()

        mock_launch.assert_called_once_with()


class TestGUIEntryPoints:
    """Test the GUI entry points work correctly."""

    def test_gui_main_function_exists(self):
        """Verify the main GUI entry point exists."""
        from pysysfan.gui import main

        assert callable(main)

    def test_gui_main_module_entry_point(self):
        """Verify __main__ module entry point exists."""
        from pysysfan.gui import __main__

        assert hasattr(__main__, "main")
        assert callable(__main__.main)


class TestGUIFileStructure:
    """Test that GUI files are in expected locations."""

    def test_gui_init_file_exists(self):
        """Verify __init__.py exists."""
        from pysysfan import gui

        assert gui.__file__ is not None
        assert gui.__file__.endswith("__init__.py")

    def test_gui_desktop_directory_exists(self):
        """Verify desktop directory structure exists."""
        from pathlib import Path
        from pysysfan import gui

        gui_dir = Path(gui.__file__).parent
        desktop_dir = gui_dir / "desktop"

        assert desktop_dir.exists()
        assert (desktop_dir / "__init__.py").exists()
        assert (desktop_dir / "app.py").exists()
        assert (desktop_dir / "main_window.py").exists()

    def test_desktop_source_files_exist(self):
        """Verify desktop source files exist."""
        from pathlib import Path
        from pysysfan import gui

        gui_dir = Path(gui.__file__).parent
        desktop_dir = gui_dir / "desktop"

        required_files = [
            "__init__.py",
            "app.py",
            "curves_page.py",
            "dashboard_page.py",
            "main_window.py",
            "service_page.py",
        ]

        for file in required_files:
            assert (desktop_dir / file).exists(), f"Missing file: {file}"

    def test_build_script_exists(self):
        """Verify the desktop helper script exists."""
        from pathlib import Path
        from pysysfan import gui

        gui_dir = Path(gui.__file__).parent
        assert (gui_dir / "build.py").exists()


class TestGUIPackageStructure:
    """Test the overall package structure."""

    def test_desktop_package_has_launch_function(self):
        """Verify desktop package exports launch_gui."""
        from pysysfan.gui import desktop

        assert hasattr(desktop, "launch_gui")
        assert callable(desktop.launch_gui)

    def test_gui_all_exports(self):
        """Verify __all__ exports in gui module."""
        from pysysfan import gui

        assert hasattr(gui, "__all__")
        assert "main" in gui.__all__
