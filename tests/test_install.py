"""Tests for pysysfan.install — Independent install entry points."""

from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from pysysfan.install import install_lhm, install_pawnio


class TestInstallLhm:
    """Tests for the install_lhm CLI entry point."""

    @patch("pysysfan.install.download_latest")
    def test_success(self, mock_download):
        """Should exit cleanly when download_latest succeeds."""
        mock_download.return_value = MagicMock()
        runner = CliRunner()
        result = runner.invoke(install_lhm)
        assert result.exit_code == 0
        mock_download.assert_called_once()

    @patch("pysysfan.install.download_latest", side_effect=RuntimeError("API error"))
    def test_failure_prints_error(self, mock_download):
        """Should exit with code 1 and print error on failure."""
        runner = CliRunner()
        result = runner.invoke(install_lhm)
        assert result.exit_code == 1
        assert "API error" in result.output


class TestInstallPawnio:
    """Tests for the install_pawnio CLI entry point."""

    @patch("pysysfan.install._do_install")
    def test_success(self, mock_install):
        """Should exit cleanly when PawnIO install succeeds."""
        runner = CliRunner()
        result = runner.invoke(install_pawnio)
        assert result.exit_code == 0

    @patch("pysysfan.install._do_install", side_effect=RuntimeError("Download failed"))
    def test_failure_prints_error(self, mock_install):
        """Should exit with code 1 and print error on failure."""
        runner = CliRunner()
        result = runner.invoke(install_pawnio)
        assert result.exit_code == 1
        assert "Download failed" in result.output
