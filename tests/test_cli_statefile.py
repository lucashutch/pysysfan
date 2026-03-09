"""Focused CLI tests for the post-API daemon entrypoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pysysfan.cli import main


class TestRunCommandWithoutApi:
    @patch("pysysfan.daemon.FanDaemon")
    def test_run_constructs_daemon_without_api_kwargs(
        self, mock_daemon_class, tmp_path
    ):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 1\nfans: {}\ncurves: {}\n")

        mock_daemon = MagicMock()
        mock_daemon_class.return_value = mock_daemon

        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(cfg_file)])

        assert result.exit_code == 0
        mock_daemon_class.assert_called_once_with(config_path=cfg_file)
        mock_daemon.run.assert_called_once_with()

    def test_run_help_no_longer_mentions_api_options(self):
        runner = CliRunner()

        result = runner.invoke(main, ["run", "--help"])

        assert result.exit_code == 0
        assert "--api" not in result.output
        assert "--api-host" not in result.output
        assert "--api-port" not in result.output
