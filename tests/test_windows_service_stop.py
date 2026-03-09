"""Focused tests for Windows service stop support."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pysysfan.platforms.windows_service import stop_task


class TestStopTask:
    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_stop_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        stop_task()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "schtasks" in args
        assert "/End" in args

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_stop_raises_not_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="The system cannot find the file specified.",
        )

        with pytest.raises(FileNotFoundError, match="not installed"):
            stop_task()

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_stop_raises_generic_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Access is denied.",
        )

        with pytest.raises(RuntimeError, match="schtasks /End failed"):
            stop_task()
