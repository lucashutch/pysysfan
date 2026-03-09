"""Tests for the PySide6 desktop GUI helper entry point."""

from __future__ import annotations

from importlib.machinery import ModuleSpec
from unittest.mock import patch

from pysysfan.gui import build


class TestModuleAvailable:
    """Tests for module availability checks."""

    @patch("importlib.util.find_spec")
    def test_module_available_true(self, mock_find_spec):
        """A found module should be reported as available."""
        mock_find_spec.return_value = ModuleSpec("PySide6", loader=None)

        assert build._module_available("PySide6") is True

    @patch("importlib.util.find_spec")
    def test_module_available_false(self, mock_find_spec):
        """A missing module should be reported as unavailable."""
        mock_find_spec.return_value = None

        assert build._module_available("PySide6") is False


class TestCheckPrerequisites:
    """Tests for dependency validation."""

    @patch("pysysfan.gui.build._module_available")
    @patch("builtins.print")
    def test_check_prerequisites_success(self, mock_print, mock_module_available):
        """The helper should succeed when GUI dependencies are present."""
        mock_module_available.return_value = True

        assert build.check_prerequisites() == 0
        mock_print.assert_called_once_with("Desktop GUI dependencies are available.")

    @patch("pysysfan.gui.build._module_available")
    @patch("builtins.print")
    def test_check_prerequisites_reports_missing_modules(
        self, mock_print, mock_module_available
    ):
        """The helper should report each missing GUI dependency."""
        mock_module_available.side_effect = [False, False]

        assert build.check_prerequisites() == 1
        assert mock_print.call_args_list[0].args == ("Missing GUI dependencies:",)
        assert mock_print.call_args_list[1].args == ("- PySide6",)
        assert mock_print.call_args_list[2].args == ("- pyqtgraph",)
        assert mock_print.call_args_list[3].args == (
            "Install them with: uv sync --extra gui",
        )


class TestLaunchGUI:
    """Tests for GUI launching."""

    @patch("pysysfan.gui.desktop.launch_gui")
    def test_launch_gui_delegates_to_desktop_entrypoint(self, mock_launch):
        """The helper should delegate launch to the desktop package."""
        mock_launch.return_value = 0

        assert build.launch_gui() == 0
        mock_launch.assert_called_once_with()


class TestMain:
    """Tests for the command-line entry point."""

    @patch("pysysfan.gui.build.check_prerequisites")
    def test_main_defaults_to_check_command(self, mock_check):
        """Running without arguments should validate prerequisites."""
        mock_check.return_value = 0

        with patch("sys.argv", ["pysysfan.gui.build"]):
            assert build.main() == 0

        mock_check.assert_called_once_with()

    @patch("pysysfan.gui.build.launch_gui")
    def test_main_launch_command_runs_gui(self, mock_launch):
        """The launch subcommand should call the GUI launcher."""
        mock_launch.return_value = 0

        with patch("sys.argv", ["pysysfan.gui.build", "launch"]):
            assert build.main() == 0

        mock_launch.assert_called_once_with()
