"""Tests for Linux systemd service integration.

These tests mock systemctl and filesystem operations to test
Linux service management without requiring actual systemd.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pysysfan.platforms.linux_service import (
    get_systemd_service_status,
    install_systemd_service,
    uninstall_systemd_service,
    _find_executable,
    _get_config_path,
    SERVICE_NAME,
)


class TestFindExecutable:
    """Tests for finding pysysfan executable."""

    def test_finds_in_path(self):
        """Should find executable in PATH."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/pysysfan"
            result = _find_executable()
            assert result == "/usr/bin/pysysfan"

    def test_checks_common_paths(self):
        """Should check common installation paths."""
        with (
            patch("shutil.which") as mock_which,
            patch("pathlib.Path.exists") as mock_exists,
        ):
            mock_which.return_value = None
            mock_exists.return_value = True

            result = _find_executable()
            assert result is not None

    def test_raises_when_not_found(self):
        """Should raise FileNotFoundError when executable not found."""
        with (
            patch("shutil.which") as mock_which,
            patch("pathlib.Path.exists") as mock_exists,
        ):
            mock_which.return_value = None
            mock_exists.return_value = False

            with pytest.raises(FileNotFoundError) as exc_info:
                _find_executable()
            assert "pysysfan" in str(exc_info.value)


class TestGetConfigPath:
    """Tests for config path resolution."""

    def test_uses_default_path(self):
        """Should use default config path when not specified."""
        result = _get_config_path(None)
        assert result == Path.home() / ".pysysfan" / "config.yaml"

    def test_uses_provided_path(self):
        """Should use provided config path."""
        custom_path = Path("/custom/config.yaml")
        result = _get_config_path(custom_path)
        assert result == custom_path


class TestInstallSystemdService:
    """Tests for service installation."""

    def test_creates_system_service_file(self, tmp_path):
        """Should create system-wide service file."""
        service_dir = tmp_path / "system"
        config_file = tmp_path / "config.yaml"
        config_file.write_text("test config")

        with (
            patch("pysysfan.platforms.linux_service.SYSTEMD_SYSTEM_DIR", service_dir),
            patch("pysysfan.platforms.linux_service._find_executable") as mock_exe,
            patch("pysysfan.platforms.linux_service._run_systemctl"),
        ):
            mock_exe.return_value = "/usr/bin/pysysfan"

            install_systemd_service(config_file, system_wide=True)

            service_file = service_dir / f"{SERVICE_NAME}.service"
            assert service_file.exists()
            content = service_file.read_text()
            assert "pysysfan" in content
            assert "run" in content

    def test_creates_user_service_file(self, tmp_path):
        """Should create user service file."""
        service_dir = tmp_path / "user"
        config_file = tmp_path / "config.yaml"
        config_file.write_text("test config")

        with (
            patch("pysysfan.platforms.linux_service.SYSTEMD_USER_DIR", service_dir),
            patch("pysysfan.platforms.linux_service._find_executable") as mock_exe,
            patch("pysysfan.platforms.linux_service._run_systemctl"),
        ):
            mock_exe.return_value = "/usr/bin/pysysfan"

            install_systemd_service(config_file, system_wide=False)

            service_file = service_dir / f"{SERVICE_NAME}.service"
            assert service_file.exists()

    def test_raises_when_config_missing(self):
        """Should raise FileNotFoundError when config doesn't exist."""
        with patch("pysysfan.platforms.linux_service._find_executable") as mock_exe:
            mock_exe.return_value = "/usr/bin/pysysfan"

            with pytest.raises(FileNotFoundError) as exc_info:
                install_systemd_service(Path("/nonexistent/config.yaml"))
            assert "config" in str(exc_info.value).lower()


class TestUninstallSystemdService:
    """Tests for service uninstallation."""

    def test_removes_system_service_file(self, tmp_path):
        """Should remove system service file."""
        service_dir = tmp_path / "system"
        service_dir.mkdir()
        service_file = service_dir / f"{SERVICE_NAME}.service"
        service_file.write_text("[Service]\nExecStart=/usr/bin/pysysfan\n")

        with (
            patch("pysysfan.platforms.linux_service.SYSTEMD_SYSTEM_DIR", service_dir),
            patch("pysysfan.platforms.linux_service._run_systemctl"),
        ):
            uninstall_systemd_service(system_wide=True)

            assert not service_file.exists()

    def test_raises_when_service_not_installed(self):
        """Should raise FileNotFoundError when service not installed."""
        with patch(
            "pysysfan.platforms.linux_service.SYSTEMD_SYSTEM_DIR", Path("/nonexistent")
        ):
            with pytest.raises(FileNotFoundError) as exc_info:
                uninstall_systemd_service(system_wide=True)
            assert "not installed" in str(exc_info.value).lower()


class TestGetSystemdServiceStatus:
    """Tests for service status queries."""

    def test_returns_not_installed_when_missing(self):
        """Should return not installed when service file missing."""
        with patch(
            "pysysfan.platforms.linux_service.SYSTEMD_SYSTEM_DIR", Path("/nonexistent")
        ):
            status = get_systemd_service_status(system_wide=True)
            assert status["installed"] is False

    def test_returns_installed_when_file_exists(self, tmp_path):
        """Should return installed when service file exists."""
        service_dir = tmp_path / "system"
        service_dir.mkdir()
        service_file = service_dir / f"{SERVICE_NAME}.service"
        service_file.write_text("[Service]\n")

        with (
            patch("pysysfan.platforms.linux_service.SYSTEMD_SYSTEM_DIR", service_dir),
            patch("pysysfan.platforms.linux_service._run_systemctl") as mock_systemctl,
        ):
            mock_systemctl.return_value = Mock(returncode=1, stdout="")

            status = get_systemd_service_status(system_wide=True)
            assert status["installed"] is True
            assert status["service_file"] == str(service_file)

    def test_detects_enabled_status(self, tmp_path):
        """Should detect enabled status."""
        service_dir = tmp_path / "system"
        service_dir.mkdir()
        service_file = service_dir / f"{SERVICE_NAME}.service"
        service_file.write_text("[Service]\n")

        with (
            patch("pysysfan.platforms.linux_service.SYSTEMD_SYSTEM_DIR", service_dir),
            patch("pysysfan.platforms.linux_service._run_systemctl") as mock_systemctl,
        ):
            # First call (is-enabled) returns 0, second (is-active) returns error
            mock_systemctl.side_effect = [
                Mock(returncode=0, stdout=""),
                Mock(returncode=1, stdout=""),
            ]

            status = get_systemd_service_status(system_wide=True)
            assert status["enabled"] is True

    def test_detects_active_state(self, tmp_path):
        """Should detect active state."""
        service_dir = tmp_path / "system"
        service_dir.mkdir()
        service_file = service_dir / f"{SERVICE_NAME}.service"
        service_file.write_text("[Service]\n")

        with (
            patch("pysysfan.platforms.linux_service.SYSTEMD_SYSTEM_DIR", service_dir),
            patch("pysysfan.platforms.linux_service._run_systemctl") as mock_systemctl,
        ):
            mock_systemctl.side_effect = [
                Mock(returncode=1, stdout=""),  # is-enabled fails
                Mock(returncode=0, stdout="ActiveState=active\n"),  # show succeeds
            ]

            status = get_systemd_service_status(system_wide=True)
            assert status["state"] == "active"
