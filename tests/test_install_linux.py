"""Tests for Linux installer module."""

from unittest.mock import Mock, patch


from pysysfan.install_linux import (
    Colors,
    detect_distro,
    find_python_tool,
    install_pysysfan_package,
    install_system_deps,
    install_systemd_service,
    is_thinkpad,
    print_error,
    print_success,
)


class TestColorFunctions:
    """Tests for color output functions."""

    def test_print_error(self, capsys):
        """Should print error in red."""
        print_error("test message")
        captured = capsys.readouterr()
        assert "ERROR: test message" in captured.err
        assert Colors.RED in captured.err

    def test_print_success(self, capsys):
        """Should print success in green."""
        print_success("test message")
        captured = capsys.readouterr()
        assert "✓ test message" in captured.out
        assert Colors.GREEN in captured.out


class TestDetectDistro:
    """Tests for distribution detection."""

    def test_detects_ubuntu(self, tmp_path):
        """Should detect Ubuntu from os-release."""
        os_release = tmp_path / "os-release"
        os_release.write_text('ID=ubuntu\nNAME="Ubuntu"\n')

        with patch("pysysfan.install_linux.Path") as mock_path:
            mock_path.return_value = Mock(
                exists=lambda: True, read_text=os_release.read_text
            )
            distro, family = detect_distro()
            assert distro == "ubuntu"
            assert family == "debian"

    def test_detects_fedora(self, tmp_path):
        """Should detect Fedora from os-release."""
        os_release = tmp_path / "os-release"
        os_release.write_text('ID=fedora\nNAME="Fedora"\n')

        with patch("pysysfan.install_linux.Path") as mock_path:
            mock_path.return_value = Mock(
                exists=lambda: True, read_text=os_release.read_text
            )
            distro, family = detect_distro()
            assert distro == "fedora"
            assert family == "rhel"

    def test_detects_arch(self, tmp_path):
        """Should detect Arch Linux."""
        os_release = tmp_path / "os-release"
        os_release.write_text('ID=arch\nNAME="Arch Linux"\n')

        with patch("pysysfan.install_linux.Path") as mock_path:
            mock_path.return_value = Mock(
                exists=lambda: True, read_text=os_release.read_text
            )
            distro, family = detect_distro()
            assert distro == "arch"
            assert family == "arch"


class TestFindPythonTool:
    """Tests for Python tool detection."""

    def test_prefers_uv(self):
        """Should prefer uv if available."""
        with patch("pysysfan.install_linux.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: x == "uv"
            result = find_python_tool()
            assert result == "uv"

    def test_falls_back_to_pip3(self):
        """Should fall back to pip3 if uv not available."""
        with patch("pysysfan.install_linux.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: x in ["pip3", "pip"]
            result = find_python_tool()
            assert result == "pip3"

    def test_returns_empty_if_none_found(self):
        """Should return empty string if no tool found."""
        with patch("pysysfan.install_linux.shutil.which") as mock_which:
            mock_which.return_value = None
            result = find_python_tool()
            assert result == ""


class TestInstallSystemDeps:
    """Tests for system dependency installation."""

    def test_debian_install(self):
        """Should install Debian packages."""
        result = install_system_deps("debian", dry_run=True)
        assert result is True

    def test_unknown_distro(self):
        """Should handle unknown distribution."""
        result = install_system_deps("unknown", dry_run=True)
        assert result is False

    def test_dry_run_does_not_execute(self):
        """Should not execute commands in dry run mode."""
        with patch("pysysfan.install_linux.run_command") as mock_run:
            install_system_deps("debian", dry_run=True)
            mock_run.assert_not_called()


class TestIsThinkPad:
    """Tests for ThinkPad detection."""

    def test_detects_thinkpad_from_product_name(self):
        """Should detect ThinkPad from product name."""
        dmi_path = Mock()
        dmi_path.exists.return_value = True
        dmi_path.__truediv__ = Mock(
            side_effect=lambda x: Mock(
                exists=lambda: True,
                read_text=lambda: (
                    "ThinkPad P14s Gen 3" if x == "product_name" else "LENOVO"
                ),
            )
        )

        with patch("pysysfan.install_linux.Path", return_value=dmi_path):
            result = is_thinkpad()
            assert result is True

    def test_detects_non_thinkpad(self):
        """Should return False for non-ThinkPad."""
        dmi_path = Mock()
        dmi_path.exists.return_value = True
        dmi_path.__truediv__ = Mock(
            side_effect=lambda x: Mock(
                exists=lambda: True,
                read_text=lambda: "Dell XPS 13" if x == "product_name" else "Dell Inc.",
            )
        )

        with patch("pysysfan.install_linux.Path", return_value=dmi_path):
            result = is_thinkpad()
            assert result is False


class TestInstallPysysfanPackage:
    """Tests for pysysfan package installation."""

    def test_installs_with_uv(self):
        """Should install with uv when available."""
        with patch("pysysfan.install_linux.find_python_tool") as mock_tool:
            mock_tool.return_value = "uv"
            result = install_pysysfan_package(dry_run=True)
            assert result is True

    def test_installs_with_pip(self):
        """Should install with pip when uv not available."""
        with patch("pysysfan.install_linux.find_python_tool") as mock_tool:
            mock_tool.return_value = "pip3"
            result = install_pysysfan_package(dry_run=True)
            assert result is True

    def test_fails_when_no_tool_available(self):
        """Should fail when no Python tool available."""
        with patch("pysysfan.install_linux.find_python_tool") as mock_tool:
            mock_tool.return_value = ""
            result = install_pysysfan_package(dry_run=True)
            assert result is False


class TestInstallSystemdService:
    """Tests for systemd service installation."""

    def test_installs_user_service(self):
        """Should install user service."""
        with patch("pysysfan.install_linux.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/pysysfan"
            result = install_systemd_service(user_service=True, dry_run=True)
            assert result is True

    def test_installs_system_service(self):
        """Should install system service."""
        with patch("pysysfan.install_linux.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/pysysfan"
            result = install_systemd_service(user_service=False, dry_run=True)
            assert result is True

    def test_skips_when_pysysfan_not_in_path(self):
        """Should skip when pysysfan not available."""
        with patch("pysysfan.install_linux.shutil.which") as mock_which:
            mock_which.return_value = None
            result = install_systemd_service(dry_run=False)
            assert result is False
