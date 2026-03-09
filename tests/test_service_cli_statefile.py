"""Focused tests for the expanded service CLI commands."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from pysysfan.cli import main


class TestServiceCommands:
    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_start_calls_platform_helper(self, mock_service, _mock_admin):
        runner = CliRunner()

        result = runner.invoke(main, ["service", "start"])

        assert result.exit_code == 0
        mock_service.start_task.assert_called_once_with()

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_stop_calls_platform_helper(self, mock_service, _mock_admin):
        runner = CliRunner()

        result = runner.invoke(main, ["service", "stop"])

        assert result.exit_code == 0
        mock_service.stop_task.assert_called_once_with()

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_enable_calls_platform_helper(self, mock_service, _mock_admin):
        runner = CliRunner()

        result = runner.invoke(main, ["service", "enable"])

        assert result.exit_code == 0
        mock_service.enable_task.assert_called_once_with()

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_disable_calls_platform_helper(self, mock_service, _mock_admin):
        runner = CliRunner()

        result = runner.invoke(main, ["service", "disable"])

        assert result.exit_code == 0
        mock_service.disable_task.assert_called_once_with()

    @patch("time.sleep", return_value=None)
    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_restart_stops_then_starts(
        self,
        mock_service,
        _mock_admin,
        _mock_sleep,
    ):
        runner = CliRunner()

        result = runner.invoke(main, ["service", "restart"])

        assert result.exit_code == 0
        mock_service.stop_task.assert_called_once_with()
        mock_service.start_task.assert_called_once_with()

    @patch("pysysfan.cli.check_admin", return_value=False)
    def test_service_start_requires_admin(self, _mock_admin):
        runner = CliRunner()

        result = runner.invoke(main, ["service", "start"])

        assert result.exit_code == 1
        assert "Administrator" in result.output


class TestCliDefaults:
    def test_monitor_help_shows_one_second_default(self):
        runner = CliRunner()

        result = runner.invoke(main, ["monitor", "--help"])

        assert result.exit_code == 0
        assert "[default: 1.0]" in result.output or "[default: 1]" in result.output
