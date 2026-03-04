"""Tests for pysysfan.pawnio.download — PawnIO download and install logic."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from pysysfan.pawnio.download import (
    get_installed_version,
    download_setup,
    install_pawnio,
)


# ── Test data ─────────────────────────────────────────────────────────

MOCK_RELEASE = {
    "tag_name": "v1.2.3",
    "html_url": "https://github.com/namazso/PawnIO.Setup/releases/tag/v1.2.3",
    "assets": [
        {
            "name": "PawnIO_setup.exe",
            "size": 5242880,
            "browser_download_url": "https://example.com/PawnIO_setup.exe",
        },
    ],
}


# ── get_installed_version ─────────────────────────────────────────────


class TestGetInstalledVersion:
    """Tests for get_installed_version()."""

    def test_reads_version_file(self, tmp_path):
        """Should read version from the .pawnio_version file."""
        version_file = tmp_path / ".pawnio_version"
        version_file.write_text("v1.2.3\n")

        with patch("pysysfan.pawnio.download._PAWNIO_VERSION_FILE", version_file):
            assert get_installed_version() == "v1.2.3"

    def test_returns_none_when_missing(self, tmp_path):
        """Should return None when no version file exists."""
        missing_file = tmp_path / ".pawnio_version"
        with patch("pysysfan.pawnio.download._PAWNIO_VERSION_FILE", missing_file):
            assert get_installed_version() is None

    def test_returns_none_for_empty_file(self, tmp_path):
        """Should return None when version file is empty."""
        version_file = tmp_path / ".pawnio_version"
        version_file.write_text("")
        with patch("pysysfan.pawnio.download._PAWNIO_VERSION_FILE", version_file):
            assert get_installed_version() is None


# ── download_setup ────────────────────────────────────────────────────


class TestDownloadSetup:
    """Tests for download_setup()."""

    @patch("pysysfan.pawnio.download.requests.get")
    def test_downloads_to_target_dir(self, mock_get, tmp_path):
        """Should download the setup exe to the specified directory."""
        mock_response = MagicMock()
        mock_response.content = b"fake exe content"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        asset = MOCK_RELEASE["assets"][0]
        result = download_setup(asset, tmp_path)
        assert result.name == "PawnIO_setup.exe"
        assert result.is_file()
        assert result.read_bytes() == b"fake exe content"

    @patch("pysysfan.pawnio.download.requests.get")
    def test_downloads_to_temp_dir(self, mock_get):
        """Should download to a temp directory when none specified."""
        mock_response = MagicMock()
        mock_response.content = b"fake"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        asset = MOCK_RELEASE["assets"][0]
        result = download_setup(asset, None)
        assert result.name == "PawnIO_setup.exe"
        assert result.is_file()

    @patch("pysysfan.pawnio.download.requests.get")
    def test_creates_target_dir(self, mock_get, tmp_path):
        """Should create target_dir if it doesn't exist."""
        mock_response = MagicMock()
        mock_response.content = b"fake"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        target = tmp_path / "nested" / "dir"
        asset = MOCK_RELEASE["assets"][0]
        result = download_setup(asset, target)
        assert result.is_file()


# ── install_pawnio ────────────────────────────────────────────────────


class TestInstallPawnio:
    """Tests for install_pawnio()."""

    @patch("pysysfan.pawnio.download._PAWNIO_VERSION_DIR")
    @patch("pysysfan.pawnio.download._PAWNIO_VERSION_FILE")
    @patch("pysysfan.pawnio.download.get_installed_version", return_value=None)
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=True)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_already_installed_no_marker(
        self, mock_api, mock_installed, mock_version, mock_vfile, mock_vdir, tmp_path
    ):
        """Should record version when PawnIO is installed but no marker exists."""
        mock_api.return_value = MOCK_RELEASE
        mock_vdir_path = tmp_path
        mock_vfile_path = tmp_path / ".pawnio_version"
        mock_vdir.__truediv__ = lambda s, x: mock_vdir_path / x
        mock_vdir.mkdir = MagicMock()
        mock_vfile.write_text = mock_vfile_path.write_text

        install_pawnio()
        assert mock_vfile_path.read_text().startswith("v1.2.3")

    @patch("pysysfan.pawnio.download.get_installed_version", return_value="v1.2.3")
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=True)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_already_up_to_date_skips(self, mock_api, mock_installed, mock_version):
        """Should skip when already installed and version matches."""
        mock_api.return_value = MOCK_RELEASE
        install_pawnio()

    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_raises_when_no_asset(self, mock_api):
        """Should raise RuntimeError when no setup exe is found in release."""
        mock_api.return_value = {
            "tag_name": "v0.0.1",
            "html_url": "",
            "assets": [],
        }
        with (
            patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=False),
            patch("pysysfan.pawnio.download.get_installed_version", return_value=None),
            pytest.raises(RuntimeError, match="No PawnIO_setup.exe"),
        ):
            install_pawnio()

    @patch("pysysfan.pawnio.download._PAWNIO_VERSION_DIR")
    @patch("pysysfan.pawnio.download._PAWNIO_VERSION_FILE")
    @patch("pysysfan.pawnio.download.subprocess.run")
    @patch("pysysfan.pawnio.download.download_setup")
    @patch("pysysfan.pawnio.download.get_installed_version", return_value=None)
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=False)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_fresh_install_success(
        self,
        mock_api,
        mock_installed,
        mock_version,
        mock_download,
        mock_run,
        mock_vfile,
        mock_vdir,
        tmp_path,
    ):
        """Should download and run installer for fresh install."""
        mock_api.return_value = MOCK_RELEASE
        mock_download.return_value = tmp_path / "PawnIO_setup.exe"
        mock_run.return_value = MagicMock(returncode=0)

        mock_vfile_path = tmp_path / ".pawnio_version"
        mock_vdir.mkdir = MagicMock()
        mock_vfile.write_text = mock_vfile_path.write_text

        install_pawnio()
        mock_download.assert_called_once()
        mock_run.assert_called_once()

    @patch("pysysfan.pawnio.download.subprocess.run")
    @patch("pysysfan.pawnio.download.download_setup")
    @patch("pysysfan.pawnio.download.get_installed_version", return_value=None)
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=False)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_installer_nonzero_exit(
        self, mock_api, mock_installed, mock_version, mock_download, mock_run, tmp_path
    ):
        """Should handle a non-zero exit from the installer."""
        mock_api.return_value = MOCK_RELEASE
        mock_download.return_value = tmp_path / "PawnIO_setup.exe"
        mock_run.return_value = MagicMock(returncode=1)

        install_pawnio()  # Should not raise

    @patch("pysysfan.pawnio.download.subprocess.run")
    @patch("pysysfan.pawnio.download.download_setup")
    @patch("pysysfan.pawnio.download._find_uninstall_command", return_value=None)
    @patch("pysysfan.pawnio.download.get_installed_version", return_value="v1.0.0")
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=True)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_upgrade_no_uninstaller(
        self,
        mock_api,
        mock_installed,
        mock_version,
        mock_find_uninstall,
        mock_download,
        mock_run,
    ):
        """Should abort upgrade when uninstaller not found in registry."""
        mock_api.return_value = MOCK_RELEASE
        install_pawnio()
        mock_download.assert_not_called()  # Should not proceed to download

    @patch("pysysfan.pawnio.download.subprocess.run")
    @patch("pysysfan.pawnio.download.download_setup")
    @patch(
        "pysysfan.pawnio.download._find_uninstall_command",
        return_value="C:\\uninstall.exe",
    )
    @patch("pysysfan.pawnio.download.get_installed_version", return_value="v1.0.0")
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=True)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_upgrade_with_uninstaller(
        self,
        mock_api,
        mock_installed,
        mock_version,
        mock_find_uninstall,
        mock_download,
        mock_run,
        tmp_path,
    ):
        """Should uninstall then install when upgrading."""
        mock_api.return_value = MOCK_RELEASE
        mock_download.return_value = tmp_path / "PawnIO_setup.exe"
        mock_run.return_value = MagicMock(returncode=0)

        install_pawnio()
        # Should have called subprocess.run twice: uninstall + install
        assert mock_run.call_count >= 2

    @patch("pysysfan.pawnio.download.subprocess.run")
    @patch("pysysfan.pawnio.download.download_setup")
    @patch(
        "pysysfan.pawnio.download._find_uninstall_command",
        return_value="C:\\uninstall.exe",
    )
    @patch("pysysfan.pawnio.download.get_installed_version", return_value="v1.0.0")
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=True)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_upgrade_uninstall_fails(
        self,
        mock_api,
        mock_installed,
        mock_version,
        mock_find_uninstall,
        mock_download,
        mock_run,
    ):
        """Should abort upgrade when uninstall subprocess fails."""
        mock_api.return_value = MOCK_RELEASE
        mock_run.side_effect = OSError("Failed")

        install_pawnio()  # Should not raise, just print warning
        mock_download.assert_not_called()

    @patch("pysysfan.pawnio.download.subprocess.run")
    @patch("pysysfan.pawnio.download.download_setup")
    @patch("pysysfan.pawnio.download.get_installed_version", return_value=None)
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=False)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_installer_timeout(
        self, mock_api, mock_installed, mock_version, mock_download, mock_run, tmp_path
    ):
        """Should handle installer timeout gracefully."""
        mock_api.return_value = MOCK_RELEASE
        mock_download.return_value = tmp_path / "PawnIO_setup.exe"
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 300)

        install_pawnio()  # Should not raise

    @patch("pysysfan.pawnio.download.subprocess.run")
    @patch("pysysfan.pawnio.download.download_setup")
    @patch("pysysfan.pawnio.download.get_installed_version", return_value=None)
    @patch("pysysfan.pawnio.download.is_pawnio_installed", return_value=False)
    @patch("pysysfan.pawnio.download.get_latest_release_info")
    def test_installer_other_exception(
        self, mock_api, mock_installed, mock_version, mock_download, mock_run, tmp_path
    ):
        """Should raise exception for unexpected errors during install."""
        mock_api.return_value = MOCK_RELEASE
        mock_download.return_value = tmp_path / "PawnIO_setup.exe"
        mock_run.side_effect = RuntimeError("Unknown error")

        with pytest.raises(RuntimeError, match="Unknown error"):
            install_pawnio()
