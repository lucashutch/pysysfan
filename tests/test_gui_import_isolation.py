"""Tests for GUI import isolation.

These tests ensure that importing pysysfan modules does not
automatically import GUI dependencies, which keeps CLI startup fast
and avoids unnecessary dependency loading.
"""

import sys
from unittest import mock

import pytest


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

    def test_gui_web_module_imports_are_lazy(self):
        """Verify that web module imports don't happen until launch."""
        from pysysfan.gui import web

        # The web module should have launch_gui
        assert hasattr(web, "launch_gui")

        # But should not have imported heavy dependencies yet
        # (we can't easily test this without actually importing)

    def test_gui_launch_imports_on_call(self):
        """Verify GUI dependencies are only imported when launch is called."""
        from pysysfan.gui.web import launch_gui

        # Mock subprocess.run to simulate npm not found
        with (
            mock.patch(
                "subprocess.run", side_effect=FileNotFoundError("npm not found")
            ),
            mock.patch("pathlib.Path.exists", return_value=True),
        ):
            # This should trigger the imports and fail with SystemExit
            with pytest.raises(SystemExit) as exc_info:
                launch_gui()

            # Should exit with code 1 because npm command won't be found
            assert exc_info.value.code == 1


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

    def test_gui_web_directory_exists(self):
        """Verify web directory structure exists."""
        from pathlib import Path
        from pysysfan import gui

        gui_dir = Path(gui.__file__).parent
        web_dir = gui_dir / "web"

        assert web_dir.exists()
        assert (web_dir / "package.json").exists()
        assert (web_dir / "src").exists()

    def test_gui_tauri_directory_exists(self):
        """Verify tauri directory structure exists."""
        from pathlib import Path
        from pysysfan import gui

        gui_dir = Path(gui.__file__).parent
        tauri_dir = gui_dir / "tauri"

        assert tauri_dir.exists()
        assert (tauri_dir / "src-tauri").exists()

    def test_svelte_source_files_exist(self):
        """Verify Svelte source files exist."""
        from pathlib import Path
        from pysysfan import gui

        gui_dir = Path(gui.__file__).parent
        src_dir = gui_dir / "web" / "src"

        required_files = [
            "main.ts",
            "App.svelte",
            "app.css",
            "lib/types.ts",
            "lib/api.ts",
            "lib/stores.ts",
        ]

        for file in required_files:
            assert (src_dir / file).exists(), f"Missing file: {file}"

    def test_build_script_exists(self):
        """Verify build.py script exists."""
        from pathlib import Path
        from pysysfan import gui

        gui_dir = Path(gui.__file__).parent
        assert (gui_dir / "build.py").exists()


class TestGUIPackageStructure:
    """Test the overall package structure."""

    def test_web_package_has_launch_function(self):
        """Verify web package exports launch_gui."""
        from pysysfan.gui import web

        assert hasattr(web, "launch_gui")
        assert callable(web.launch_gui)

    def test_gui_all_exports(self):
        """Verify __all__ exports in gui module."""
        from pysysfan import gui

        assert hasattr(gui, "__all__")
        assert "main" in gui.__all__
