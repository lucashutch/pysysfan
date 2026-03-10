"""Tests for desktop local backend command launching helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pysysfan.gui.desktop.local_backend import run_service_command


@patch("pysysfan.gui.desktop.local_backend.check_admin", return_value=False)
@patch("pysysfan.gui.desktop.local_backend.shutil.which")
@patch("pysysfan.gui.desktop.local_backend.ctypes.windll", new_callable=MagicMock)
@patch("pysysfan.gui.desktop.local_backend.sys.platform", "win32")
def test_run_service_command_requests_elevation_via_cli_executable(
    mock_windll,
    mock_which,
    _mock_admin,
) -> None:
    """The GUI should elevate the installed CLI executable, not the GUI launcher."""
    mock_which.side_effect = [r"C:\tools\pysysfan.exe"]
    mock_windll.shell32.IsUserAnAdmin.return_value = 0
    mock_windll.shell32.ShellExecuteW.return_value = 33

    success, message = run_service_command("install")

    assert success is True
    assert "Administrator permission" in message
    mock_windll.shell32.ShellExecuteW.assert_called_once_with(
        None,
        "runas",
        r"C:\tools\pysysfan.exe",
        "service install",
        None,
        1,
    )


@patch("pysysfan.gui.desktop.local_backend.shutil.which", return_value=None)
@patch("pysysfan.gui.desktop.local_backend.Path.is_file", return_value=False)
@patch("pysysfan.gui.desktop.local_backend.run_python_module")
def test_run_service_command_falls_back_to_python_module(
    mock_run_python_module,
    _mock_is_file,
    _mock_which,
) -> None:
    """Missing CLI launchers should fall back to the module invocation path."""
    mock_run_python_module.return_value = (True, "ok")

    result = run_service_command("start")

    assert result == (True, "ok")
    mock_run_python_module.assert_called_once_with(
        "pysysfan.cli",
        ["service", "start"],
        elevate=True,
    )
