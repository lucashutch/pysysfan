"""Tests for pysysfan.install — Independent install entry points."""

from unittest.mock import patch, MagicMock

from click.testing import CliRunner


class TestInstallLhm:
    """Tests for the install_lhm CLI entry point."""

    @patch("pysysfan.install.download_latest")
    def test_download_success(self, mock_download):
        """Should exit cleanly when download_latest succeeds."""
        from pysysfan.install import install_lhm

        mock_download.return_value = MagicMock()
        runner = CliRunner()
        result = runner.invoke(install_lhm, ["download"])
        assert result.exit_code == 0
        mock_download.assert_called_once()

    @patch("pysysfan.install.download_latest", side_effect=RuntimeError("API error"))
    def test_download_failure_prints_error(self, mock_download):
        """Should exit with code 1 and print error on failure."""
        from pysysfan.install import install_lhm

        runner = CliRunner()
        result = runner.invoke(install_lhm, ["download"])
        assert result.exit_code == 1
        assert "API error" in result.output

    @patch("pysysfan.install.get_lhm_dll_path")
    @patch("pysysfan.install.LHM_DIR", MagicMock())
    def test_info_success(self, mock_get_path):
        """Should display info when LHM is installed."""
        from pysysfan.install import install_lhm

        mock_get_path.return_value = "/fake/path/LibreHardwareMonitorLib.dll"
        runner = CliRunner()
        result = runner.invoke(install_lhm, ["info"])
        assert result.exit_code == 0
        assert "DLL found" in result.output

    @patch(
        "pysysfan.install.get_lhm_dll_path",
        side_effect=FileNotFoundError("DLL not found"),
    )
    @patch("pysysfan.install.LHM_DIR", MagicMock())
    def test_info_not_installed(self, mock_get_path):
        """Should exit with error when LHM is not installed."""
        from pysysfan.install import install_lhm

        runner = CliRunner()
        result = runner.invoke(install_lhm, ["info"])
        assert result.exit_code == 1
        assert "DLL not found" in result.output


class TestInstallPawnio:
    """Tests for the install_pawnio CLI entry point."""

    @patch("pysysfan.install._do_install")
    def test_success(self, mock_install):
        """Should exit cleanly when PawnIO install succeeds."""
        from pysysfan.install import install_pawnio

        runner = CliRunner()
        result = runner.invoke(install_pawnio)
        assert result.exit_code == 0
        mock_install.assert_called_once()

    @patch(
        "pysysfan.install._do_install",
        side_effect=RuntimeError("Download failed"),
    )
    def test_failure_prints_error(self, mock_install):
        """Should exit with code 1 and print error on failure."""
        from pysysfan.install import install_pawnio

        runner = CliRunner()
        result = runner.invoke(install_pawnio)
        assert result.exit_code == 1
        assert "Download failed" in result.output
