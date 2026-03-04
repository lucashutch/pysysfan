"""Tests for pysysfan.updater — Self-update functionality."""

from unittest.mock import patch, MagicMock

import pytest

from pysysfan.updater import (
    check_for_update,
    get_current_version,
    perform_update,
    _is_newer,
    _normalise_tag,
)


# ── Helper data ──────────────────────────────────────────────────────


def _fake_release(tag: str = "v1.0.0") -> dict:
    """Return a minimal GitHub release API response."""
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/lucashutch/pysysfan/releases/tag/{tag}",
        "body": f"Release {tag} notes.",
    }


# ── Unit tests ───────────────────────────────────────────────────────


class TestNormaliseTag:
    """Tests for _normalise_tag helper."""

    def test_strips_v_prefix(self):
        assert _normalise_tag("v1.2.3") == "1.2.3"

    def test_no_prefix(self):
        assert _normalise_tag("1.2.3") == "1.2.3"


class TestIsNewer:
    """Tests for _is_newer version comparison."""

    def test_newer_version(self):
        assert _is_newer("0.1.0", "v0.2.0") is True

    def test_same_version(self):
        assert _is_newer("0.2.0", "v0.2.0") is False

    def test_older_version(self):
        assert _is_newer("0.3.0", "v0.2.0") is False

    def test_dev_version_treated_as_outdated(self):
        # 0.0.0-dev is not valid PEP 440, falls back to string comparison
        assert _is_newer("0.0.0-dev", "v0.1.0") is True

    def test_same_dev_version(self):
        assert _is_newer("0.0.0-dev", "v0.0.0-dev") is False


class TestGetCurrentVersion:
    """Tests for get_current_version."""

    @patch("pysysfan.updater.__version__", "1.2.3")
    def test_returns_package_version(self):
        assert get_current_version() == "1.2.3"


class TestCheckForUpdate:
    """Tests for the check_for_update function."""

    @patch("pysysfan.updater.__version__", "0.1.0")
    @patch("pysysfan.updater.get_latest_release_info")
    def test_update_available(self, mock_api):
        mock_api.return_value = _fake_release("v0.2.0")
        info = check_for_update()

        assert info.available is True
        assert info.current_version == "0.1.0"
        assert info.latest_version == "v0.2.0"
        assert "v0.2.0" in info.release_url

    @patch("pysysfan.updater.__version__", "0.2.0")
    @patch("pysysfan.updater.get_latest_release_info")
    def test_already_up_to_date(self, mock_api):
        mock_api.return_value = _fake_release("v0.2.0")
        info = check_for_update()

        assert info.available is False
        assert info.current_version == "0.2.0"

    @patch("pysysfan.updater.get_latest_release_info")
    def test_network_error_propagates(self, mock_api):
        mock_api.side_effect = ConnectionError("No internet")

        with pytest.raises(ConnectionError, match="No internet"):
            check_for_update()

    @patch("pysysfan.updater.get_latest_release_info")
    def test_release_notes_included(self, mock_api):
        mock_api.return_value = _fake_release("v0.2.0")
        info = check_for_update()
        assert info.release_notes == "Release v0.2.0 notes."


class TestPerformUpdate:
    """Tests for the perform_update function."""

    @patch("pysysfan.updater.subprocess.run")
    def test_runs_uv_tool_install(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        mock_run.return_value.check_returncode = MagicMock()

        perform_update("v0.3.0")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "uv"
        assert "tool" in args
        assert "install" in args
        assert "--force" in args
        assert any("v0.3.0" in a for a in args)

    @patch("pysysfan.updater.subprocess.run")
    def test_raises_on_failure(self, mock_run):
        import subprocess

        mock_run.return_value = MagicMock(returncode=1)
        mock_run.return_value.check_returncode.side_effect = (
            subprocess.CalledProcessError(1, "uv")
        )

        with pytest.raises(subprocess.CalledProcessError):
            perform_update("v0.3.0")
