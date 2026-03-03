"""Tests for pysysfan.pawnio — PawnIO driver detection and download."""

from unittest.mock import patch, MagicMock

from pysysfan.pawnio import is_pawnio_installed, get_pawnio_status
from pysysfan.pawnio.download import find_setup_asset, get_latest_release_info


# ── Driver detection ──────────────────────────────────────────────────


class TestIsPawnioInstalled:
    """Tests for is_pawnio_installed()."""

    @patch("pysysfan.pawnio.subprocess.run")
    def test_returns_true_when_service_exists(self, mock_run):
        """Should return True when sc query succeeds (returncode 0)."""
        mock_run.return_value = MagicMock(returncode=0)
        assert is_pawnio_installed() is True

    @patch("pysysfan.pawnio.subprocess.run")
    def test_returns_false_when_service_missing(self, mock_run):
        """Should return False when sc query fails (returncode != 0)."""
        mock_run.return_value = MagicMock(returncode=1)
        assert is_pawnio_installed() is False

    @patch("pysysfan.pawnio.subprocess.run", side_effect=FileNotFoundError)
    def test_returns_false_on_exception(self, mock_run):
        """Should return False if subprocess raises an exception."""
        assert is_pawnio_installed() is False


class TestGetPawnioStatus:
    """Tests for get_pawnio_status()."""

    @patch("pysysfan.pawnio.subprocess.run")
    def test_returns_installed_with_state(self, mock_run):
        """Should parse the service state from sc query output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "SERVICE_NAME: PawnIO\n"
                "        TYPE               : 1  KERNEL_DRIVER\n"
                "        STATE              : 4  RUNNING\n"
                "        WIN32_EXIT_CODE    : 0  (0x0)\n"
            ),
        )
        status = get_pawnio_status()
        assert status["installed"] is True
        assert status["state"] == "RUNNING"

    @patch("pysysfan.pawnio.subprocess.run")
    def test_returns_not_installed(self, mock_run):
        """Should return installed=False when service is absent."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        status = get_pawnio_status()
        assert status["installed"] is False
        assert status["state"] is None

    @patch("pysysfan.pawnio.subprocess.run", side_effect=OSError)
    def test_returns_not_installed_on_error(self, mock_run):
        """Should return installed=False on subprocess errors."""
        status = get_pawnio_status()
        assert status["installed"] is False
        assert status["state"] is None


# ── GitHub release parsing ────────────────────────────────────────────


MOCK_RELEASE = {
    "tag_name": "v1.2.3",
    "html_url": "https://github.com/namazso/PawnIO.Setup/releases/tag/v1.2.3",
    "assets": [
        {
            "name": "PawnIO_setup.exe",
            "size": 5242880,
            "browser_download_url": "https://github.com/namazso/PawnIO.Setup/releases/download/v1.2.3/PawnIO_setup.exe",
        },
    ],
}

MOCK_RELEASE_NO_ASSET = {
    "tag_name": "v0.0.1",
    "html_url": "https://github.com/namazso/PawnIO.Setup/releases/tag/v0.0.1",
    "assets": [],
}


class TestFindSetupAsset:
    """Tests for find_setup_asset()."""

    def test_finds_exact_match(self):
        """Should find PawnIO_setup.exe by exact name match."""
        asset = find_setup_asset(MOCK_RELEASE)
        assert asset is not None
        assert asset["name"] == "PawnIO_setup.exe"

    def test_returns_none_for_empty_assets(self):
        """Should return None when no assets are present."""
        assert find_setup_asset(MOCK_RELEASE_NO_ASSET) is None

    def test_fallback_to_any_pawnio_exe(self):
        """Should fall back to any exe with 'pawnio' in the name."""
        release = {
            "assets": [
                {"name": "PawnIO-driver-v2.exe", "size": 1024},
            ],
        }
        asset = find_setup_asset(release)
        assert asset is not None
        assert asset["name"] == "PawnIO-driver-v2.exe"


class TestGetLatestReleaseInfo:
    """Tests for get_latest_release_info()."""

    @patch("pysysfan.pawnio.download.requests.get")
    def test_returns_release_json(self, mock_get):
        """Should return the parsed JSON from the GitHub API."""
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RELEASE
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_latest_release_info()
        assert result["tag_name"] == "v1.2.3"
        mock_get.assert_called_once()
