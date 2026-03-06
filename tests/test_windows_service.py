"""Tests for pysysfan.platforms.windows_service — Windows Task Scheduler integration."""

from unittest.mock import patch, MagicMock

import pytest

from pysysfan.platforms.windows_service import (
    _pysysfan_exe,
    install_task,
    uninstall_task,
    get_task_status,
)


class TestPysysfanExe:
    """Tests for _pysysfan_exe()."""

    @patch("pysysfan.platforms.windows_service.shutil.which")
    def test_found_in_path(self, mock_which):
        """Should return the exe when found via shutil.which."""
        mock_which.return_value = r"C:\tools\pysysfan.exe"
        assert _pysysfan_exe() == r"C:\tools\pysysfan.exe"

    @patch("pysysfan.platforms.windows_service.shutil.which")
    def test_fallback_pysysfan_exe(self, mock_which):
        """Should try pysysfan.exe as a fallback."""
        mock_which.side_effect = [None, r"C:\tools\pysysfan.exe"]
        assert _pysysfan_exe() == r"C:\tools\pysysfan.exe"

    @patch("pysysfan.platforms.windows_service.shutil.which", return_value=None)
    def test_raises_when_not_found(self, mock_which):
        """Should raise FileNotFoundError when not in PATH."""
        with pytest.raises(FileNotFoundError, match="not found in PATH"):
            _pysysfan_exe()


class TestInstallTask:
    """Tests for install_task()."""

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    @patch(
        "pysysfan.platforms.windows_service._pysysfan_exe",
        return_value=r"C:\tools\pysysfan.exe",
    )
    def test_success(self, mock_exe, mock_run):
        """Should call schtasks /Create without errors."""
        mock_run.return_value = MagicMock(returncode=0)
        install_task()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "schtasks" in args
        assert "/Create" in args

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    @patch(
        "pysysfan.platforms.windows_service._pysysfan_exe",
        return_value=r"C:\tools\pysysfan.exe",
    )
    def test_with_config_path(self, mock_exe, mock_run):
        """Should include --config in the task command when provided."""
        mock_run.return_value = MagicMock(returncode=0)
        install_task(config_path=r"C:\cfg\config.yaml")
        args = mock_run.call_args[0][0]
        tr_idx = args.index("/TR")
        cmd_str = args[tr_idx + 1]
        assert "--config" in cmd_str

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    @patch(
        "pysysfan.platforms.windows_service._pysysfan_exe",
        return_value=r"C:\tools\pysysfan.exe",
    )
    def test_failure_raises(self, mock_exe, mock_run):
        """Should raise RuntimeError when schtasks fails."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="error", stderr="access denied"
        )
        with pytest.raises(RuntimeError, match="schtasks /Create failed"):
            install_task()


class TestUninstallTask:
    """Tests for uninstall_task()."""

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_success(self, mock_run):
        """Should complete without error when schtasks /Delete succeeds."""
        mock_run.return_value = MagicMock(returncode=0)
        uninstall_task()
        mock_run.assert_called_once()

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_raises_not_found(self, mock_run):
        """Should raise FileNotFoundError when task doesn't exist."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="The system cannot find the file specified."
        )
        with pytest.raises(FileNotFoundError):
            uninstall_task()

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_raises_generic_error(self, mock_run):
        """Should raise RuntimeError for other schtasks errors."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Access is denied."
        )
        with pytest.raises(RuntimeError, match="schtasks /Delete failed"):
            uninstall_task()


class TestGetTaskStatus:
    """Tests for get_task_status()."""

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_returns_status(self, mock_run):
        """Should return the parsed status string."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Folder: \\\n"
                "HostName:      DESKTOP\n"
                "TaskName:      \\pysysfan\n"
                "Status:        Running\n"
            ),
        )
        assert get_task_status() == "Running"

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_returns_none_when_not_installed(self, mock_run):
        """Should return None when task doesn't exist."""
        mock_run.return_value = MagicMock(returncode=1)
        assert get_task_status() is None

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_returns_unknown_when_no_status_line(self, mock_run):
        """Should return 'Unknown' when output has no Status line."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="TaskName: \\pysysfan\n",
        )
        assert get_task_status() == "Unknown"


class TestEnableTask:
    """Tests for enable_task()."""

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_enable_success(self, mock_run):
        """Should enable task successfully."""
        mock_run.return_value = MagicMock(returncode=0)
        from pysysfan.platforms.windows_service import enable_task

        enable_task()  # Should not raise
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "schtasks" in args
        assert "/ENABLE" in args

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_enable_raises_not_found(self, mock_run):
        """Should raise FileNotFoundError when task doesn't exist."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="The system cannot find the file specified.",
        )
        from pysysfan.platforms.windows_service import enable_task

        import pytest

        with pytest.raises(FileNotFoundError, match="not installed"):
            enable_task()

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_enable_raises_generic_error(self, mock_run):
        """Should raise RuntimeError for other schtasks errors."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Access is denied.",
        )
        from pysysfan.platforms.windows_service import enable_task

        import pytest

        with pytest.raises(RuntimeError, match="failed"):
            enable_task()


class TestDisableTask:
    """Tests for disable_task()."""

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_disable_success(self, mock_run):
        """Should disable task successfully."""
        mock_run.return_value = MagicMock(returncode=0)
        from pysysfan.platforms.windows_service import disable_task

        disable_task()  # Should not raise
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "schtasks" in args
        assert "/DISABLE" in args

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_disable_raises_not_found(self, mock_run):
        """Should raise FileNotFoundError when task doesn't exist."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="The system cannot find the file specified.",
        )
        from pysysfan.platforms.windows_service import disable_task
        import pytest

        with pytest.raises(FileNotFoundError, match="not installed"):
            disable_task()

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_disable_raises_generic_error(self, mock_run):
        """Should raise RuntimeError for other schtasks errors."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Access is denied.",
        )
        from pysysfan.platforms.windows_service import disable_task
        import pytest

        with pytest.raises(RuntimeError, match="failed"):
            disable_task()
