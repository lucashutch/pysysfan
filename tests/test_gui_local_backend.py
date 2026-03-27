"""Tests for desktop local backend command launching helpers."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from pysysfan.gui.desktop import local_backend
from pysysfan.gui.desktop.local_backend import (
    read_daemon_history,
    read_daemon_state,
    run_service_command,
)
from pysysfan.history_file import HistorySample, append_history_sample
from pysysfan.state_file import DaemonStateFile, write_state


def _sample_state(timestamp: float | None = None) -> DaemonStateFile:
    stamp = time.time() if timestamp is None else timestamp
    return DaemonStateFile(
        timestamp=stamp,
        pid=123,
        running=True,
        uptime_seconds=5.0,
        active_profile="default",
        poll_interval=1.0,
        config_path="C:/tmp/config.yaml",
    )


@patch("pysysfan.gui.desktop.local_backend.check_admin", return_value=False)
@patch("pysysfan.gui.desktop.local_backend.shutil.which")
@patch("pysysfan.gui.desktop.local_backend.subprocess.run")
@patch("pysysfan.gui.desktop.local_backend.sys.platform", "win32")
def test_run_service_command_requests_elevation_via_cli_executable(
    mock_run,
    mock_which,
    _mock_admin,
) -> None:
    """The GUI should elevate the installed CLI executable and wait."""
    mock_which.side_effect = [r"C:\tools\pysysfan.exe"]

    mock_completed = MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = "0\n"
    mock_completed.stderr = ""
    mock_run.return_value = mock_completed

    success, message = run_service_command("install")

    assert success is True
    assert "Elevated process exit code" in message
    assert "Administrator permission" not in message

    called_args = mock_run.call_args[0][0]
    assert called_args[0] == "powershell"


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


def test_read_daemon_state_uses_mtime_cache(tmp_path) -> None:
    """State reads should skip deserialization when file mtime is unchanged."""
    state_path = tmp_path / "daemon_state.json"
    write_state(_sample_state(), state_path)
    local_backend._STATE_CACHE_PATH = None
    local_backend._STATE_CACHE_MTIME_NS = None
    local_backend._STATE_CACHE_VALUE = None

    with patch("pysysfan.gui.desktop.local_backend.read_state") as mock_read_state:
        mock_read_state.return_value = _sample_state()
        first = read_daemon_state(state_path)
        second = read_daemon_state(state_path)

    assert first is not None
    assert second is not None
    assert mock_read_state.call_count == 1


def test_read_daemon_history_uses_mtime_cache(tmp_path) -> None:
    """History reads should skip re-parsing when the NDJSON mtime is unchanged."""
    history_path = tmp_path / "daemon_history.ndjson"
    append_history_sample(
        HistorySample(
            timestamp=time.time(),
            temperatures={"/cpu/temp/0": 60.0},
            fan_rpm={"/mb/control/0": 1200.0},
            fan_targets={"/mb/control/0": 55.0},
        ),
        history_path,
    )
    local_backend._HISTORY_CACHE_PATH = None
    local_backend._HISTORY_CACHE_MTIME_NS = None
    local_backend._HISTORY_CACHE_VALUE = None

    with patch("pysysfan.gui.desktop.local_backend.read_history") as mock_history:
        mock_history.return_value = [
            HistorySample(
                timestamp=time.time(),
                temperatures={"/cpu/temp/0": 60.0},
                fan_rpm={"/mb/control/0": 1200.0},
                fan_targets={"/mb/control/0": 55.0},
            )
        ]
        first = read_daemon_history(history_path)
        second = read_daemon_history(history_path)

    assert len(first) == 1
    assert len(second) == 1
    assert mock_history.call_count == 1
