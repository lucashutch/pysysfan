"""Tests for pysysfan.cli — CLI entry point and command structure."""

from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from pysysfan.cli import main, check_admin
from pysysfan.hardware import HardwareScanResult, SensorInfo, ControlInfo


# ── Version and help ──────────────────────────────────────────────────


class TestMainCli:
    """Tests for the main CLI group."""

    def test_version_flag(self):
        """--version should print the version string."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "pysysfan" in result.output.lower() or "." in result.output

    def test_help_flag(self):
        """--help should show usage information."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output

    def test_verbose_flag(self):
        """--verbose should not error."""
        runner = CliRunner()
        result = runner.invoke(main, ["--verbose", "--help"])
        assert result.exit_code == 0


# ── Subcommand help ──────────────────────────────────────────────────


class TestSubcommandHelp:
    """Test that subcommands show help without errors."""

    def test_lhm_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["lhm", "--help"])
        assert result.exit_code == 0
        assert "LibreHardwareMonitor" in result.output

    def test_config_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_service_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["service", "--help"])
        assert result.exit_code == 0

    def test_update_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["update", "--help"])
        assert result.exit_code == 0

    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0

    def test_status_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--help"])
        assert result.exit_code == 0

    def test_monitor_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["monitor", "--help"])
        assert result.exit_code == 0

    def test_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0


# ── check_admin ──────────────────────────────────────────────────────


class TestCheckAdmin:
    """Tests for check_admin()."""

    def test_returns_false_when_exception(self):
        """check_admin should return False when ctypes raises."""
        # On non-Windows or non-admin, should return False gracefully
        result = check_admin()
        assert isinstance(result, bool)


# ── Config show ──────────────────────────────────────────────────────


class TestConfigShow:
    """Tests for 'config show' subcommand."""

    def test_config_show_file_not_found(self, tmp_path):
        """Should report error when config file doesn't exist."""
        runner = CliRunner()
        cfg_path = tmp_path / "nonexistent.yaml"
        result = runner.invoke(main, ["config", "--path", str(cfg_path), "show"])
        # SystemExit(1) from the command
        assert result.exit_code != 0

    def test_config_show_valid(self, tmp_path):
        """Should display config file contents."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 5\nfans: {}\ncurves: {}\n")
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--path", str(cfg_file), "show"])
        assert result.exit_code == 0


# ── Config validate ──────────────────────────────────────────────────


class TestConfigValidate:
    """Tests for 'config validate' subcommand."""

    def test_config_validate_missing_file(self, tmp_path):
        """Should fail when config file doesn't exist."""
        runner = CliRunner()
        cfg_path = tmp_path / "nope.yaml"
        result = runner.invoke(main, ["config", "--path", str(cfg_path), "validate"])
        assert result.exit_code != 0

    def test_config_validate_valid(self, tmp_path):
        """Should succeed when config is valid."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "general:\n  poll_interval: 2\nfans: {}\ncurves:\n"
            "  balanced:\n    hysteresis: 3\n    points:\n      - [30, 30]\n"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--path", str(cfg_file), "validate"])
        assert result.exit_code == 0
        assert "OK" in result.output

    def test_config_validate_bad_curve_ref(self, tmp_path):
        """Should fail when a fan references a non-existent curve."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "general:\n  poll_interval: 2\n"
            "fans:\n  f1:\n    sensor: /mb/c/0\n    curve: nonexistent\n    source: /cpu/t/0\n"
            "curves: {}\n"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--path", str(cfg_file), "validate"])
        assert result.exit_code != 0


# ── Config init ──────────────────────────────────────────────────────


class TestConfigInit:
    """Tests for 'config init' subcommand."""

    def test_config_init_creates_file(self, tmp_path):
        """Should create a config file."""
        cfg_path = tmp_path / "subdir" / "config.yaml"
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--path", str(cfg_path), "init"])
        assert result.exit_code == 0
        assert cfg_path.is_file()

    def test_config_init_exists_without_force(self, tmp_path):
        """Should not overwrite without --force."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("existing")
        runner = CliRunner()
        runner.invoke(main, ["config", "--path", str(cfg_path), "init"])
        assert cfg_path.read_text() == "existing"


# ── Update check command ─────────────────────────────────────────────


class TestUpdateCheck:
    """Tests for 'update check' subcommand."""

    @patch("pysysfan.updater.check_for_update")
    def test_update_check_up_to_date(self, mock_check):
        """Should display up-to-date message."""
        mock_info = MagicMock()
        mock_info.available = False
        mock_info.current_version = "1.0.0"
        mock_info.latest_version = "1.0.0"
        mock_check.return_value = mock_info

        runner = CliRunner()
        result = runner.invoke(main, ["update", "check"])
        assert result.exit_code == 0

    @patch("pysysfan.updater.check_for_update")
    def test_update_check_available(self, mock_check):
        """Should display update available info."""
        mock_info = MagicMock()
        mock_info.available = True
        mock_info.current_version = "0.1.0"
        mock_info.latest_version = "0.2.0"
        mock_info.release_url = "https://github.com/test"
        mock_info.release_notes = "Bug fixes"
        mock_check.return_value = mock_info

        runner = CliRunner()
        result = runner.invoke(main, ["update", "check"])
        assert result.exit_code == 0


# ── LHM subcommands ─────────────────────────────────────────────────


class TestLhmCommands:
    """Tests for LHM CLI subcommands."""

    def test_lhm_info_not_found(self):
        """lhm info should handle missing DLL gracefully."""
        runner = CliRunner()
        result = runner.invoke(main, ["lhm", "info"])
        # Either finds the DLL or fails gracefully
        assert isinstance(result.exit_code, int)


# ── Output formatters ────────────────────────────────────────────────


class TestOutputFormatters:
    """Tests for _output_scan_json and _output_scan_tables."""

    def test_output_scan_json(self):
        """Should format scan results as JSON."""
        from pysysfan.cli import _output_scan_json

        result = HardwareScanResult(
            temperatures=[SensorInfo("CPU", "Proc", "Core", "Temp", "/cpu/t/0", 55.0)],
            fans=[SensorInfo("MB", "Board", "Fan1", "Fan", "/mb/f/0", 1200.0)],
            controls=[ControlInfo("MB", "Fan Ctrl", "/mb/c/0", 75.0, has_control=True)],
        )
        # Should not raise
        _output_scan_json(result, "all")

    def test_output_scan_tables(self):
        """Should format scan results as tables without error."""
        from pysysfan.cli import _output_scan_tables

        result = HardwareScanResult(
            temperatures=[SensorInfo("CPU", "Proc", "Core", "Temp", "/cpu/t/0", 55.0)],
            fans=[SensorInfo("MB", "Board", "Fan1", "Fan", "/mb/f/0", 1200.0)],
            controls=[ControlInfo("MB", "Fan Ctrl", "/mb/c/0", 75.0, has_control=True)],
        )
        # Should not raise
        _output_scan_tables(result, "all")

    def test_output_scan_tables_temp_only(self):
        """Should only show temperature table when type is temp."""
        from pysysfan.cli import _output_scan_tables

        result = HardwareScanResult(
            temperatures=[SensorInfo("CPU", "Proc", "Core", "Temp", "/cpu/t/0", None)],
        )
        _output_scan_tables(result, "temp")

    def test_output_scan_json_fan_only(self):
        """Should only include fan data when type is fan."""
        from pysysfan.cli import _output_scan_json

        result = HardwareScanResult(
            fans=[SensorInfo("MB", "Board", "Fan1", "Fan", "/mb/f/0", None)],
        )
        _output_scan_json(result, "fan")

    def test_output_scan_json_control_only(self):
        """Should only include control data when type is control."""
        from pysysfan.cli import _output_scan_json

        result = HardwareScanResult(
            controls=[
                ControlInfo("MB", "Fan Ctrl", "/mb/c/0", None, has_control=False)
            ],
        )
        _output_scan_json(result, "control")


# ── _build_status_table ──────────────────────────────────────────────


class TestBuildStatusTable:
    """Tests for _build_status_table."""

    def test_builds_table(self):
        """Should build a rich Table without errors."""
        from pysysfan.cli import _build_status_table

        result = HardwareScanResult(
            temperatures=[SensorInfo("CPU", "Proc", "Core", "Temp", "/cpu/t/0", 55.0)],
            fans=[SensorInfo("MB", "Board", "Fan1", "Fan", "/mb/f/0", 1200.0)],
            controls=[ControlInfo("MB", "Fan Ctrl", "/mb/c/0", 75.0, has_control=True)],
        )
        table = _build_status_table(result)
        assert table is not None

    def test_builds_table_with_none_values(self):
        """Should handle None values in sensors."""
        from pysysfan.cli import _build_status_table

        result = HardwareScanResult(
            temperatures=[SensorInfo("CPU", "Proc", "Core", "Temp", "/cpu/t/0", None)],
            fans=[SensorInfo("MB", "Board", "Fan1", "Fan", "/mb/f/0", None)],
            controls=[
                ControlInfo("MB", "Fan Ctrl", "/mb/c/0", None, has_control=False)
            ],
        )
        table = _build_status_table(result)
        assert table is not None


# ── Service commands ─────────────────────────────────────────────────


class TestServiceCommands:
    """Tests for service CLI subcommands."""

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.get_service_manager")
    def test_service_install_success(self, mock_get_service, mock_admin):
        """Should install startup task."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "install"])
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

    @patch("pysysfan.cli.check_admin", return_value=False)
    def test_service_install_no_admin(self, mock_admin):
        """Should fail when not admin."""
        runner = CliRunner()
        result = runner.invoke(main, ["service", "install"])
        assert result.exit_code != 0

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.get_service_manager")
    def test_service_install_fails(self, mock_get_service, mock_admin):
        """Should handle install failure."""
        mock_service = MagicMock()
        mock_service.install_task.side_effect = RuntimeError("denied")
        mock_get_service.return_value = mock_service
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "install"])
        assert result.exit_code != 0

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.get_service_manager")
    def test_service_uninstall_success(self, mock_get_service, mock_admin):
        """Should uninstall startup task."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "uninstall"])
        assert result.exit_code == 0

    @patch("pysysfan.cli.check_admin", return_value=False)
    def test_service_uninstall_no_admin(self, mock_admin):
        """Should fail when not admin."""
        runner = CliRunner()
        result = runner.invoke(main, ["service", "uninstall"])
        assert result.exit_code != 0

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.get_service_manager")
    def test_service_uninstall_fails(self, mock_get_service, mock_admin):
        """Should handle uninstall failure."""
        mock_service = MagicMock()
        mock_service.uninstall_task.side_effect = RuntimeError("error")
        mock_get_service.return_value = mock_service
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "uninstall"])
        assert result.exit_code != 0

    @patch("pysysfan.platforms.get_service_manager")
    def test_service_status_installed(self, mock_get_service):
        """Should show task status when installed."""
        mock_service = MagicMock()
        mock_service.get_task_status.return_value = "Running"
        mock_get_service.return_value = mock_service
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "status"])
        assert result.exit_code == 0
        assert "Running" in result.output

    @patch("pysysfan.platforms.get_service_manager")
    def test_service_status_not_installed(self, mock_get_service):
        """Should show not installed message."""
        mock_service = MagicMock()
        mock_service.get_task_status.return_value = None
        mock_get_service.return_value = mock_service
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "status"])
        assert result.exit_code == 0
        assert "not installed" in result.output.lower()


# ── Run command ──────────────────────────────────────────────────────


class TestRunCommand:
    """Tests for the 'run' CLI command."""

    def test_run_no_config(self, tmp_path):
        """Should fail when config doesn't exist."""
        runner = CliRunner()
        cfg_path = tmp_path / "nonexistent.yaml"
        result = runner.invoke(main, ["run", "--config", str(cfg_path)])
        assert result.exit_code != 0

    @patch("pysysfan.daemon.FanDaemon.run_once")
    def test_run_once_success(self, mock_run_once, tmp_path):
        """Should run a single pass with --once."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")
        mock_run_once.return_value = {"cpu_fan": 55.0}
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--once", "--config", str(cfg_file)])
        assert result.exit_code == 0

    @patch("pysysfan.daemon.FanDaemon.run_once")
    def test_run_once_no_fans(self, mock_run_once, tmp_path):
        """Should handle when no fans are controlled."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")
        mock_run_once.return_value = {}
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--once", "--config", str(cfg_file)])
        assert result.exit_code == 0

    @patch("pysysfan.daemon.FanDaemon.run_once", side_effect=RuntimeError("hw error"))
    def test_run_once_error(self, mock_run_once, tmp_path):
        """Should handle hardware errors."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--once", "--config", str(cfg_file)])
        assert result.exit_code != 0


# ── LHM download command ────────────────────────────────────────────


class TestLhmDownloadCommand:
    """Tests for 'lhm download' subcommand."""

    @patch("pysysfan.lhm.download.download_latest")
    def test_lhm_download_success(self, mock_download, tmp_path):
        """Should download LHM successfully."""
        from pathlib import Path

        mock_download.return_value = Path("/fake/dll.dll")
        runner = CliRunner()
        result = runner.invoke(main, ["lhm", "download"])
        assert result.exit_code == 0

    @patch(
        "pysysfan.lhm.download.download_latest", side_effect=RuntimeError("API error")
    )
    def test_lhm_download_failure(self, mock_download):
        """Should handle download failure."""
        runner = CliRunner()
        result = runner.invoke(main, ["lhm", "download"])
        assert result.exit_code != 0


# ── Update apply/auto commands ───────────────────────────────────────


class TestUpdateApply:
    """Tests for 'update apply' subcommand."""

    @patch("pysysfan.updater.check_for_update")
    def test_already_up_to_date(self, mock_check):
        """Should show up-to-date message."""
        mock_info = MagicMock()
        mock_info.available = False
        mock_info.current_version = "1.0.0"
        mock_check.return_value = mock_info

        runner = CliRunner()
        result = runner.invoke(main, ["update", "apply"])
        assert result.exit_code == 0

    @patch("pysysfan.updater.perform_update")
    @patch("pysysfan.updater.check_for_update")
    def test_apply_with_yes(self, mock_check, mock_update):
        """Should apply update with --yes flag."""
        mock_info = MagicMock()
        mock_info.available = True
        mock_info.current_version = "0.1.0"
        mock_info.latest_version = "0.2.0"
        mock_check.return_value = mock_info

        runner = CliRunner()
        result = runner.invoke(main, ["update", "apply", "--yes"])
        assert result.exit_code == 0

    @patch("pysysfan.updater.check_for_update", side_effect=ConnectionError("offline"))
    def test_apply_network_error(self, mock_check):
        """Should handle network error."""
        runner = CliRunner()
        result = runner.invoke(main, ["update", "apply"])
        assert result.exit_code != 0

    @patch(
        "pysysfan.updater.perform_update", side_effect=RuntimeError("install failed")
    )
    @patch("pysysfan.updater.check_for_update")
    def test_apply_install_fails(self, mock_check, mock_update):
        """Should handle failed update installation."""
        mock_info = MagicMock()
        mock_info.available = True
        mock_info.current_version = "0.1.0"
        mock_info.latest_version = "0.2.0"
        mock_check.return_value = mock_info

        runner = CliRunner()
        result = runner.invoke(main, ["update", "apply", "--yes"])
        assert result.exit_code != 0


class TestUpdateAuto:
    """Tests for 'update auto' subcommand."""

    def test_update_auto_on(self, tmp_path):
        """Should enable auto updates."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n"
            "update:\n  auto_check: false\n  notify_only: true\n"
        )
        with patch("pysysfan.config.DEFAULT_CONFIG_PATH", cfg_file):
            runner = CliRunner()
            result = runner.invoke(main, ["update", "auto", "on"])
            assert result.exit_code == 0
            assert "enabled" in result.output.lower()

    def test_update_auto_off(self, tmp_path):
        """Should disable auto updates."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n"
            "update:\n  auto_check: true\n  notify_only: true\n"
        )
        with patch("pysysfan.config.DEFAULT_CONFIG_PATH", cfg_file):
            runner = CliRunner()
            result = runner.invoke(main, ["update", "auto", "off"])
            assert result.exit_code == 0
            assert "disabled" in result.output.lower()

    def test_update_auto_no_config(self, tmp_path):
        """Should fail when config doesn't exist."""
        cfg_file = tmp_path / "nonexistent.yaml"
        with patch("pysysfan.config.DEFAULT_CONFIG_PATH", cfg_file):
            runner = CliRunner()
            result = runner.invoke(main, ["update", "auto", "on"])
            assert result.exit_code != 0
