"""Tests for pysysfan.lhm.download — LHM release download and extraction."""

import io
import zipfile
from unittest.mock import patch, MagicMock

import pytest

from pysysfan.lhm.download import (
    find_zip_asset,
    get_installed_version,
    download_and_extract_dll,
    download_latest,
)


# ── Test data ─────────────────────────────────────────────────────────

MOCK_RELEASE = {
    "tag_name": "v0.9.2",
    "html_url": "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.2",
    "assets": [
        {
            "name": "LibreHardwareMonitor.zip",
            "size": 5242880,
            "browser_download_url": "https://example.com/LibreHardwareMonitor.zip",
        },
        {
            "name": "LibreHardwareMonitor.NET.10.zip",
            "size": 6291456,
            "browser_download_url": "https://example.com/LibreHardwareMonitor.NET.10.zip",
        },
    ],
}

MOCK_RELEASE_NO_ZIP = {
    "tag_name": "v0.9.0",
    "assets": [
        {"name": "Source.tar.gz", "size": 1024},
    ],
}


# ── find_zip_asset ────────────────────────────────────────────────────


class TestFindZipAsset:
    """Tests for find_zip_asset()."""

    def test_prefers_net472_build(self):
        """Should prefer the plain zip (net472) over the .NET Core build."""
        asset = find_zip_asset(MOCK_RELEASE)
        assert asset is not None
        assert asset["name"] == "LibreHardwareMonitor.zip"

    def test_falls_back_to_any_lhm_zip(self):
        """Should fall back to any zip with 'librehardwaremonitor' in name."""
        release = {
            "assets": [
                {
                    "name": "LibreHardwareMonitor.NET.10.zip",
                    "size": 1024,
                    "browser_download_url": "https://example.com/lhm.zip",
                },
            ]
        }
        asset = find_zip_asset(release)
        assert asset is not None
        assert "NET.10" in asset["name"]

    def test_returns_none_when_no_zip(self):
        """Should return None when no suitable ZIP is found."""
        assert find_zip_asset(MOCK_RELEASE_NO_ZIP) is None

    def test_returns_none_for_empty_assets(self):
        """Should return None when assets list is empty."""
        assert find_zip_asset({"assets": []}) is None


# ── get_installed_version ─────────────────────────────────────────────


class TestGetInstalledVersion:
    """Tests for get_installed_version()."""

    def test_reads_version_file(self, tmp_path):
        """Should read the version from the .lhm_version file."""
        version_file = tmp_path / ".lhm_version"
        version_file.write_text("v0.9.2\nLibreHardwareMonitor.zip\n")
        assert get_installed_version(tmp_path) == "v0.9.2"

    def test_returns_none_when_missing(self, tmp_path):
        """Should return None when no version file exists."""
        assert get_installed_version(tmp_path) is None

    def test_returns_none_for_empty_file(self, tmp_path):
        """Should return None when version file is empty."""
        version_file = tmp_path / ".lhm_version"
        version_file.write_text("")
        assert get_installed_version(tmp_path) is None


# ── download_and_extract_dll ──────────────────────────────────────────


class TestDownloadAndExtractDll:
    """Tests for download_and_extract_dll()."""

    def _make_zip_bytes(self, filenames: list[str]) -> bytes:
        """Create a ZIP in memory with fake files."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name in filenames:
                zf.writestr(name, b"fake content")
        return buf.getvalue()

    @patch("pysysfan.lhm.download.requests.get")
    def test_extracts_dll(self, mock_get, tmp_path):
        """Should extract the DLL and related files."""
        zip_bytes = self._make_zip_bytes(
            ["LibreHardwareMonitorLib.dll", "HidSharp.dll", "readme.txt"]
        )
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [zip_bytes]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        asset = {
            "name": "LibreHardwareMonitor.zip",
            "size": len(zip_bytes),
            "browser_download_url": "https://example.com/lhm.zip",
        }
        result = download_and_extract_dll(asset, tmp_path)
        assert result.name == "LibreHardwareMonitorLib.dll"
        assert result.is_file()
        # Should also extract HidSharp.dll
        assert (tmp_path / "HidSharp.dll").is_file()

    @patch("pysysfan.lhm.download.requests.get")
    def test_raises_when_dll_not_in_archive(self, mock_get, tmp_path):
        """Should raise FileNotFoundError when DLL is missing from the ZIP."""
        zip_bytes = self._make_zip_bytes(["readme.txt", "changelog.txt"])
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [zip_bytes]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        asset = {
            "name": "wrong.zip",
            "size": len(zip_bytes),
            "browser_download_url": "https://example.com/wrong.zip",
        }
        with pytest.raises(FileNotFoundError, match="not found"):
            download_and_extract_dll(asset, tmp_path)


# ── download_latest ───────────────────────────────────────────────────


class TestDownloadLatest:
    """Tests for download_latest()."""

    @patch("pysysfan.lhm.download.get_latest_release_info")
    def test_skips_when_up_to_date(self, mock_api, tmp_path):
        """Should skip download when installed version matches latest."""
        # Set up version marker and DLL
        (tmp_path / ".lhm_version").write_text("v0.9.2\n")
        (tmp_path / "LibreHardwareMonitorLib.dll").write_bytes(b"fake")

        mock_api.return_value = MOCK_RELEASE
        result = download_latest(tmp_path)
        assert result == tmp_path / "LibreHardwareMonitorLib.dll"

    @patch("pysysfan.lhm.download.download_and_extract_dll")
    @patch("pysysfan.lhm.download.get_latest_release_info")
    def test_downloads_when_outdated(self, mock_api, mock_extract, tmp_path):
        """Should download when installed version is different."""
        (tmp_path / ".lhm_version").write_text("v0.9.0\n")
        mock_api.return_value = MOCK_RELEASE
        mock_extract.return_value = tmp_path / "LibreHardwareMonitorLib.dll"

        download_latest(tmp_path)
        mock_extract.assert_called_once()
        # Version marker should be updated
        assert (tmp_path / ".lhm_version").read_text().startswith("v0.9.2")

    @patch("pysysfan.lhm.download.get_latest_release_info")
    def test_raises_when_no_asset(self, mock_api, tmp_path):
        """Should raise RuntimeError when no suitable ZIP is found."""
        mock_api.return_value = MOCK_RELEASE_NO_ZIP
        with pytest.raises(RuntimeError, match="No suitable ZIP"):
            download_latest(tmp_path)
