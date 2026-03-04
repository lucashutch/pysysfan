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

    def test_detects_suse(self, tmp_path):
        """Should detect SUSE from os-release."""
        os_release = tmp_path / "os-release"
        os_release.write_text('ID=opensuse\nNAME="openSUSE"\n')

        with patch("pysysfan.install_linux.Path") as mock_path:
            mock_path.return_value = Mock(
                exists=lambda: True, read_text=os_release.read_text
            )
            distro, family = detect_distro()
            assert distro == "opensuse"
            assert family == "suse"

    def test_unknown_distro(self, tmp_path):
        """Should return unknown when distro not recognized."""
        os_release = tmp_path / "os-release"
        os_release.write_text('ID=unknown\nNAME="Unknown"\n')

        with patch("pysysfan.install_linux.Path") as mock_path:
            mock_path.return_value = Mock(
                exists=lambda: True, read_text=os_release.read_text
            )
            distro, family = detect_distro()
            assert distro == "unknown"
            assert family == "unknown"


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
        """Should skip when pysysfan not available (in non-dry-run mode)."""
        with patch("pysysfan.install_linux.shutil.which") as mock_which:
            mock_which.return_value = None
            result = install_systemd_service(user_service=True, dry_run=False)
            assert result is False


class TestRunCommand:
    """Tests for run_command function."""

    def test_runs_command(self):
        """Should execute command successfully."""
        with patch("pysysfan.install_linux.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            from pysysfan.install_linux import run_command

            result = run_command(["echo", "test"], check=False)
            assert result.returncode == 0

    def test_raises_on_nonzero_with_check(self):
        """Should raise CalledProcessError when check=True and exit is non-zero."""
        with patch("pysysfan.install_linux.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
            from pysysfan.install_linux import run_command
            import subprocess

            try:
                run_command(["false"], check=True)
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError("Expected CalledProcessError")

    def test_captures_output_when_requested(self):
        """Should capture output when capture=True."""
        with patch("pysysfan.install_linux.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="output", stderr="")
            from pysysfan.install_linux import run_command

            result = run_command(["echo", "test"], capture=True, check=False)
            assert result.stdout == "output"


class TestSetupSensors:
    """Tests for setup_sensors function."""

    def test_dry_run_does_not_execute(self):
        """Should not execute commands in dry run mode."""
        with patch("pysysfan.install_linux.run_command") as mock_run:
            from pysysfan.install_linux import setup_sensors

            setup_sensors(dry_run=True)
            mock_run.assert_not_called()


class TestSetupThinkPadFanControl:
    """Tests for setup_thinkpad_fan_control function."""

    def test_dry_run(self):
        """Should not execute commands in dry run mode."""
        with patch("pysysfan.install_linux.run_command") as mock_run:
            from pysysfan.install_linux import setup_thinkpad_fan_control

            setup_thinkpad_fan_control(dry_run=True)
            mock_run.assert_not_called()


class TestInstallPysensors:
    """Tests for install_pysensors function."""

    def test_installs_with_uv(self):
        """Should install pysensors with uv."""
        with patch("pysysfan.install_linux.find_python_tool") as mock_tool:
            mock_tool.return_value = "uv"
            with patch("pysysfan.install_linux.run_command"):
                from pysysfan.install_linux import install_pysensors

                result = install_pysensors(dry_run=True)
                assert result is True


class TestGenerateConfig:
    """Tests for generate_config function."""

    def test_dry_run(self):
        """Should not write files in dry run mode."""
        from pysysfan.install_linux import generate_config

        result = generate_config(dry_run=True)
        assert result is True
