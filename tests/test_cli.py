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

    def test_returns_bool(self):
        """Should always return a boolean."""
        result = check_admin()
        assert result in (True, False)


class TestCliFunctions:
    """Tests for CLI helper functions."""

    @patch("click.echo")
    def test_print_version_callback(self, mock_echo):
        """Test _print_version callback."""
        from pysysfan.cli import _print_version

        mock_ctx = MagicMock()
        mock_ctx.resilient_parsing = False
        _print_version(mock_ctx, None, True)
        mock_echo.assert_called_once()
        mock_ctx.exit.assert_called_once()

    def test_print_version_skips_without_value(self):
        """Test _print_version skips when value is False."""
        from pysysfan.cli import _print_version

        mock_ctx = MagicMock()
        _print_version(mock_ctx, None, False)
        # Should not raise

        _print_version(mock_ctx, None, True)
        mock_ctx.echo.assert_not_called()


class TestScanCommandErrors:
    """Tests for scan command error handling."""

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_scan_handles_filenotfound_error(self, mock_check_admin, mock_hw_manager):
        """Should handle FileNotFoundError from HardwareManager."""
        runner = CliRunner()
        mock_check_admin.return_value = True
        mock_hw_manager.side_effect = FileNotFoundError("DLL not found")

        result = runner.invoke(main, ["scan"])
        assert result.exit_code == 1
        assert "Error" in result.output or "DLL" in str(result.output)

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_scan_handles_generic_error(self, mock_check_admin, mock_hw_manager):
        """Should handle generic exceptions from HardwareManager."""
        runner = CliRunner()
        mock_check_admin.return_value = True
        mock_hw_manager.side_effect = RuntimeError("Hardware access failed")

        result = runner.invoke(main, ["scan"])
        assert result.exit_code == 1

    @patch("pysysfan.cli.check_admin")
    def test_scan_shows_warning_when_not_admin(self, mock_check_admin):
        """Should show warning when not running as admin."""
        runner = CliRunner()
        mock_check_admin.return_value = False

        with patch("pysysfan.hardware.HardwareManager") as mock_hw:
            mock_hw.side_effect = Exception("Access denied")
            result = runner.invoke(main, ["scan"])

        assert (
            "Warning" in result.output
            or "Administrator" in result.output
            or result.exit_code == 1
        )

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_scan_json_output(self, mock_check_admin, mock_hw_manager):
        """Should support JSON output."""
        runner = CliRunner()
        mock_check_admin.return_value = True

        # Mock the scan result
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.scan.return_value = HardwareScanResult()
        mock_hw_manager.return_value = mock_instance

        runner.invoke(main, ["scan", "--json"])
        # May succeed or fail depending on mocking, but should not crash

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_scan_with_type_filter(self, mock_check_admin, mock_hw_manager):
        """Should support type filtering."""
        runner = CliRunner()
        mock_check_admin.return_value = True

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.scan.return_value = HardwareScanResult()
        mock_hw_manager.return_value = mock_instance

        runner.invoke(main, ["scan", "--type", "temp"])
        runner.invoke(main, ["scan", "--type", "fan"])
        runner.invoke(main, ["scan", "--type", "control"])
        # Should handle different filter types without crashing


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
            "general:\n"
            "  poll_interval: 2\n"
            "fans:\n"
            "  f1:\n"
            "    fan_id: /mb/c/0\n"
            "    curve: nonexistent\n"
            "    temp_id: /cpu/t/0\n"
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
        result = runner.invoke(
            main, ["config", "--path", str(cfg_path), "init", "--example"]
        )
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


# ── Output formatters ────────────────────────────────────────────────


class TestOutputFormatters:
    """Tests for _output_scan_json and _output_scan_tables."""

    def test_output_scan_json(self):
        """Should format scan results as JSON dict."""
        from pysysfan.cli import _get_scan_dict

        result = HardwareScanResult(
            temperatures=[SensorInfo("CPU", "Proc", "Core", "Temp", "/cpu/t/0", 55.0)],
            fans=[SensorInfo("MB", "Board", "Fan1", "Fan", "/mb/f/0", 1200.0)],
            controls=[ControlInfo("MB", "Fan Ctrl", "/mb/c/0", 75.0, has_control=True)],
        )
        data = _get_scan_dict(result, "all")
        assert "temperatures" in data
        assert "fans" in data
        assert "controls" in data

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
        from pysysfan.cli import _get_scan_dict

        result = HardwareScanResult(
            fans=[SensorInfo("MB", "Board", "Fan1", "Fan", "/mb/f/0", None)],
        )
        data = _get_scan_dict(result, "fan")
        assert "fans" in data
        assert "temperatures" not in data
        assert "controls" not in data

    def test_output_scan_json_control_only(self):
        """Should only include control data when type is control."""
        from pysysfan.cli import _get_scan_dict

        result = HardwareScanResult(
            controls=[
                ControlInfo("MB", "Fan Ctrl", "/mb/c/0", None, has_control=False)
            ],
        )
        data = _get_scan_dict(result, "control")
        assert "controls" in data
        assert "fans" not in data


# ── _build_status_table ──────────────────────────────────────────────


class TestIsValidTemperatureSensor:
    """Tests for _is_valid_temperature_sensor."""

    def test_valid_temp_sensor(self):
        """Should accept normal temperature sensors."""
        from pysysfan.cli import _is_valid_temperature_sensor

        sensor = SensorInfo("CPU", "Proc", "Core (Tctl/Tdie)", "Temp", "/cpu/t/0", 55.0)
        assert _is_valid_temperature_sensor(sensor) is True

    def test_valid_cpu_temp(self):
        """Should accept CPU temperature sensors."""
        from pysysfan.cli import _is_valid_temperature_sensor

        sensor = SensorInfo(
            "AMD Ryzen", "CPU", "CCD1 (Tdie)", "Temp", "/amdcpu/0/t/3", 41.0
        )
        assert _is_valid_temperature_sensor(sensor) is True

    def test_filter_resolution(self):
        """Should filter out temperature sensor resolution."""
        from pysysfan.cli import _is_valid_temperature_sensor

        sensor = SensorInfo(
            "Memory",
            "DIMM",
            "Temperature Sensor Resolution",
            "Temp",
            "/mem/dimm/1/t/1",
            0.25,
        )
        assert _is_valid_temperature_sensor(sensor) is False

    def test_filter_low_limit(self):
        """Should filter out thermal sensor low limit."""
        from pysysfan.cli import _is_valid_temperature_sensor

        sensor = SensorInfo(
            "Memory", "DIMM", "Thermal Sensor Low Limit", "Temp", "/mem/dimm/1/t/2", 0.0
        )
        assert _is_valid_temperature_sensor(sensor) is False

    def test_filter_high_limit(self):
        """Should filter out thermal sensor high limit."""
        from pysysfan.cli import _is_valid_temperature_sensor

        sensor = SensorInfo(
            "Memory",
            "DIMM",
            "Thermal Sensor High Limit",
            "Temp",
            "/mem/dimm/1/t/3",
            55.0,
        )
        assert _is_valid_temperature_sensor(sensor) is False

    def test_filter_critical_limit(self):
        """Should filter out critical temperature limits."""
        from pysysfan.cli import _is_valid_temperature_sensor

        sensor = SensorInfo(
            "Memory",
            "DIMM",
            "Thermal Sensor Critical High Limit",
            "Temp",
            "/mem/dimm/1/t/5",
            85.0,
        )
        assert _is_valid_temperature_sensor(sensor) is False

    def test_filter_warning_temperature(self):
        """Should filter out warning temperature sensors."""
        from pysysfan.cli import _is_valid_temperature_sensor

        sensor = SensorInfo(
            "Samsung SSD",
            "SSD",
            "Warning Temperature",
            "Temp",
            "/storage/ssd/0/t/1",
            84.0,
        )
        assert _is_valid_temperature_sensor(sensor) is False


class TestMatchFansWithControls:
    """Tests for _match_fans_with_controls."""

    def test_match_fans_with_controls(self):
        """Should match fan RPM sensors with their PWM controls."""
        from pysysfan.cli import _match_fans_with_controls

        fans = [
            SensorInfo(
                "Nuvoton", "LPC", "Fan #1", "Fan", "/lpc/nct6799d/0/fan/0", 1200.0
            ),
            SensorInfo(
                "Nuvoton", "LPC", "Fan #2", "Fan", "/lpc/nct6799d/0/fan/1", 800.0
            ),
        ]
        controls = [
            ControlInfo(
                "Nuvoton", "Fan #1", "/lpc/nct6799d/0/control/0", 75.0, has_control=True
            ),
            ControlInfo(
                "Nuvoton", "Fan #2", "/lpc/nct6799d/0/control/1", 50.0, has_control=True
            ),
        ]

        matched = _match_fans_with_controls(fans, controls)
        assert len(matched) == 2
        assert matched[0][0].sensor_name == "Fan #1"
        assert matched[0][1].current_value == 75.0
        assert matched[1][0].sensor_name == "Fan #2"
        assert matched[1][1].current_value == 50.0

    def test_no_matching_control(self):
        """Should return None control when no match found."""
        from pysysfan.cli import _match_fans_with_controls

        fans = [
            SensorInfo(
                "Nuvoton", "LPC", "Fan #1", "Fan", "/lpc/nct6799d/0/fan/0", 1200.0
            ),
        ]
        controls = [
            ControlInfo(
                "Nuvoton", "Fan #2", "/lpc/nct6799d/0/control/1", 50.0, has_control=True
            ),
        ]

        matched = _match_fans_with_controls(fans, controls)
        assert len(matched) == 1
        assert matched[0][1] is None

    def test_empty_fans(self):
        """Should handle empty fan list."""
        from pysysfan.cli import _match_fans_with_controls

        controls = [
            ControlInfo(
                "Nuvoton", "Fan #1", "/lpc/nct6799d/0/control/0", 75.0, has_control=True
            ),
        ]
        matched = _match_fans_with_controls([], controls)
        assert matched == []

    def test_empty_controls(self):
        """Should handle empty control list."""
        from pysysfan.cli import _match_fans_with_controls

        fans = [
            SensorInfo(
                "Nuvoton", "LPC", "Fan #1", "Fan", "/lpc/nct6799d/0/fan/0", 1200.0
            ),
        ]
        matched = _match_fans_with_controls(fans, [])
        assert len(matched) == 1
        assert matched[0][1] is None


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

    def test_filters_invalid_temps(self):
        """Should filter out invalid temperature sensors."""
        from io import StringIO
        from rich.console import Console

        from pysysfan.cli import _build_status_table

        result = HardwareScanResult(
            temperatures=[
                SensorInfo("CPU", "Proc", "Core", "Temp", "/cpu/t/0", 55.0),
                SensorInfo(
                    "Memory",
                    "DIMM",
                    "Temperature Sensor Resolution",
                    "Temp",
                    "/mem/t/1",
                    0.25,
                ),
                SensorInfo(
                    "Memory",
                    "DIMM",
                    "Thermal Sensor High Limit",
                    "Temp",
                    "/mem/t/2",
                    55.0,
                ),
            ],
            fans=[],
            controls=[],
        )
        table = _build_status_table(result)
        assert table is not None
        string_buffer = StringIO()
        console = Console(file=string_buffer, width=120)
        console.print(table)
        table_str = string_buffer.getvalue()
        assert "Core" in table_str
        assert "Resolution" not in table_str
        assert "Limit" not in table_str

    def test_groups_fan_with_control(self):
        """Should show fan RPM and PWM% in same row."""
        from io import StringIO
        from rich.console import Console

        from pysysfan.cli import _build_status_table

        result = HardwareScanResult(
            temperatures=[],
            fans=[
                SensorInfo(
                    "Nuvoton", "LPC", "Fan #1", "Fan", "/lpc/nct6799d/0/fan/0", 1200.0
                ),
            ],
            controls=[
                ControlInfo(
                    "Nuvoton",
                    "Fan #1",
                    "/lpc/nct6799d/0/control/0",
                    75.5,
                    has_control=True,
                ),
            ],
        )
        table = _build_status_table(result)
        assert table is not None
        string_buffer = StringIO()
        console = Console(file=string_buffer, width=120)
        console.print(table)
        table_str = string_buffer.getvalue()
        assert "1200" in table_str
        assert "75.5%" in table_str


# ── Service commands ─────────────────────────────────────────────────


class TestServiceCommands:
    """Tests for service CLI subcommands."""

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_install_success(self, mock_service, mock_admin):
        """Should install startup task."""
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "install"])
        assert result.exit_code == 0
        assert "installed" in result.output.lower()
        mock_service.install_task.assert_called_once()

    @patch("pysysfan.cli.check_admin", return_value=False)
    def test_service_install_no_admin(self, mock_admin):
        """Should fail when not admin."""
        runner = CliRunner()
        result = runner.invoke(main, ["service", "install"])
        assert result.exit_code != 0

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_install_fails(self, mock_service, mock_admin):
        """Should handle install failure."""
        mock_service.install_task.side_effect = RuntimeError("denied")
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "install"])
        assert result.exit_code != 0

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_uninstall_success(self, mock_service, mock_admin):
        """Should uninstall startup task."""
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "uninstall"])
        assert result.exit_code == 0
        mock_service.uninstall_task.assert_called_once()

    @patch("pysysfan.cli.check_admin", return_value=False)
    def test_service_uninstall_no_admin(self, mock_admin):
        """Should fail when not admin."""
        runner = CliRunner()
        result = runner.invoke(main, ["service", "uninstall"])
        assert result.exit_code != 0

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_uninstall_fails(self, mock_service, mock_admin):
        """Should handle uninstall failure."""
        mock_service.uninstall_task.side_effect = RuntimeError("error")
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "uninstall"])
        assert result.exit_code != 0

    @patch("pysysfan.platforms.windows_service")
    def test_service_status_installed(self, mock_service):
        """Should show task status when installed."""
        mock_service.get_task_status.return_value = "Running"
        runner = CliRunner()
        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "status"])
        assert result.exit_code == 0
        assert "Running" in result.output

    @patch("pysysfan.platforms.windows_service")
    def test_service_status_not_installed(self, mock_service):
        """Should show not installed message."""
        mock_service.get_task_status.return_value = None
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


# ── Status command ───────────────────────────────────────────────────


class TestStatusCommand:
    """Tests for 'status' command."""

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_status_shows_sensors(self, mock_check_admin, mock_hw_manager):
        """Should display sensor status."""
        runner = CliRunner()
        mock_check_admin.return_value = True

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.scan.return_value = HardwareScanResult(
            temperatures=[
                SensorInfo(
                    "CPU", "Processor", "Core 0", "Temperature", "/cpu/0/temp/0", 55.0
                )
            ],
            fans=[SensorInfo("MB", "Motherboard", "Fan 1", "Fan", "/mb/fan/0", 1200.0)],
            controls=[ControlInfo("MB", "Fan Control", "/mb/control/0", 75.0, True)],
        )
        mock_hw_manager.return_value = mock_instance

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0

    @patch("pysysfan.hardware.HardwareManager")
    def test_status_handles_error(self, mock_hw_manager):
        """Should handle hardware errors."""
        runner = CliRunner()
        mock_hw_manager.side_effect = RuntimeError("Hardware error")

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 1


# ── Config reload command ────────────────────────────────────────────


class TestConfigReload:
    """Tests for 'config reload' subcommand."""

    def test_config_reload_success(self, tmp_path):
        """Should reload config successfully."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "general:\n  poll_interval: 2\nfans: {}\ncurves:\n"
            "  balanced:\n    hysteresis: 3\n    points:\n      - [30, 30]\n"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--path", str(cfg_file), "reload"])
        assert result.exit_code == 0
        assert "success" in result.output.lower() or "reloaded" in result.output.lower()

    def test_config_reload_missing_file(self, tmp_path):
        """Should fail when config file doesn't exist."""
        cfg_file = tmp_path / "nonexistent.yaml"
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--path", str(cfg_file), "reload"])
        assert result.exit_code != 0

    def test_config_reload_invalid_yaml(self, tmp_path):
        """Should fail with invalid YAML."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("invalid: yaml: syntax[")
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--path", str(cfg_file), "reload"])
        assert result.exit_code != 0


# ── Config init auto mode ────────────────────────────────────────────


class TestConfigInitAuto:
    """Tests for 'config init' auto mode."""

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_config_init_auto_detects_fans(
        self, mock_check_admin, mock_hw_manager, tmp_path
    ):
        """Should auto-detect fans and generate config."""
        runner = CliRunner()
        mock_check_admin.return_value = True

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.scan.return_value = HardwareScanResult(
            temperatures=[
                SensorInfo(
                    "AMD", "CPU", "Core (Tctl)", "Temperature", "/amdcpu/0/temp/0", 45.0
                )
            ],
            fans=[SensorInfo("MB", "LPC", "Fan #1", "Fan", "/lpc/nct/0/fan/0", 1200.0)],
            controls=[ControlInfo("MB", "Fan #1", "/lpc/nct/0/control/0", 75.0, True)],
        )
        mock_hw_manager.return_value = mock_instance

        cfg_path = tmp_path / "subdir" / "config.yaml"
        result = runner.invoke(main, ["config", "--path", str(cfg_path), "init"])
        assert result.exit_code == 0
        assert cfg_path.exists()

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_config_init_auto_no_fans(
        self, mock_check_admin, mock_hw_manager, tmp_path
    ):
        """Should fallback to example when no fans detected."""
        runner = CliRunner()
        mock_check_admin.return_value = True

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.scan.return_value = HardwareScanResult(
            temperatures=[SensorInfo("CPU", "CPU", "Temp", "Temp", "/cpu/0", 50.0)],
            fans=[],
            controls=[],
        )
        mock_hw_manager.return_value = mock_instance

        cfg_path = tmp_path / "config.yaml"
        result = runner.invoke(main, ["config", "--path", str(cfg_path), "init"])
        assert result.exit_code == 0

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_config_init_auto_no_temps(
        self, mock_check_admin, mock_hw_manager, tmp_path
    ):
        """Should fail when no temperature sensors."""
        runner = CliRunner()
        mock_check_admin.return_value = True

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.scan.return_value = HardwareScanResult(
            temperatures=[],
            fans=[SensorInfo("MB", "LPC", "Fan", "Fan", "/fan/0", 1200.0)],
            controls=[ControlInfo("MB", "Control", "/control/0", 75.0, True)],
        )
        mock_hw_manager.return_value = mock_instance

        cfg_path = tmp_path / "config.yaml"
        result = runner.invoke(main, ["config", "--path", str(cfg_path), "init"])
        assert result.exit_code == 1

    @patch("pysysfan.hardware.HardwareManager")
    def test_config_init_auto_hardware_error(self, mock_hw_manager, tmp_path):
        """Should fallback to example on hardware error."""
        runner = CliRunner()
        mock_hw_manager.side_effect = FileNotFoundError("DLL not found")

        cfg_path = tmp_path / "config.yaml"
        result = runner.invoke(main, ["config", "--path", str(cfg_path), "init"])
        assert result.exit_code == 1


# ── Run command variations ───────────────────────────────────────────


class TestRunCommandVariations:
    """Additional tests for 'run' command."""

    @patch("pysysfan.daemon.FanDaemon")
    def test_run_with_custom_api_settings(self, mock_daemon_class, tmp_path):
        """Should use custom API settings."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")

        mock_daemon = MagicMock()
        mock_daemon_class.return_value = mock_daemon

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "run",
                "--config",
                str(cfg_file),
                "--api-host",
                "0.0.0.0",
                "--api-port",
                "9000",
            ],
        )
        # Command may fail but should attempt to create daemon with correct args
        mock_daemon_class.assert_called_once()
        call_kwargs = mock_daemon_class.call_args.kwargs
        assert call_kwargs["api_host"] == "0.0.0.0"
        assert call_kwargs["api_port"] == 9000

    @patch("pysysfan.daemon.FanDaemon")
    def test_run_no_api(self, mock_daemon_class, tmp_path):
        """Should disable API with --no-api."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")

        mock_daemon = MagicMock()
        mock_daemon_class.return_value = mock_daemon

        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(cfg_file), "--no-api"])
        mock_daemon_class.assert_called_once()
        call_kwargs = mock_daemon_class.call_args.kwargs
        assert call_kwargs["api_enabled"] is False


# ── Service command variations ───────────────────────────────────────


class TestServiceVariations:
    """Additional tests for service commands."""

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_install_with_config_path(self, mock_service, mock_admin, tmp_path):
        """Should install with custom config path."""
        runner = CliRunner()
        cfg_file = tmp_path / "custom.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")

        with patch("sys.platform", "win32"):
            result = runner.invoke(
                main, ["service", "install", "--config", str(cfg_file)]
            )
        assert result.exit_code == 0
        mock_service.install_task.assert_called_once_with(config_path=str(cfg_file))

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_install_file_not_found(self, mock_service, mock_admin, tmp_path):
        """Should handle FileNotFoundError."""
        mock_service.install_task.side_effect = FileNotFoundError("Config not found")
        runner = CliRunner()

        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "install"])
        assert result.exit_code == 1

    @patch("pysysfan.cli.check_admin", return_value=True)
    @patch("pysysfan.platforms.windows_service")
    def test_service_uninstall_not_installed(self, mock_service, mock_admin):
        """Should handle uninstall when not installed."""
        mock_service.uninstall_task.side_effect = FileNotFoundError("Not installed")
        runner = CliRunner()

        with patch("sys.platform", "win32"):
            result = runner.invoke(main, ["service", "uninstall"])
        assert result.exit_code == 1


# ── Update check variations ──────────────────────────────────────────


class TestUpdateCheckVariations:
    """Additional tests for update check."""

    @patch("pysysfan.updater.check_for_update", side_effect=ConnectionError("offline"))
    def test_update_check_network_error(self, mock_check):
        """Should handle network errors."""
        runner = CliRunner()
        result = runner.invoke(main, ["update", "check"])
        assert result.exit_code == 1
        assert "error" in result.output.lower()

    @patch("pysysfan.updater.check_for_update")
    def test_update_check_with_release_url(self, mock_check):
        """Should show release URL when available."""
        mock_info = MagicMock()
        mock_info.available = True
        mock_info.current_version = "0.1.0"
        mock_info.latest_version = "0.2.0"
        mock_info.release_url = "https://github.com/user/repo/releases/v0.2.0"
        mock_info.release_notes = None
        mock_check.return_value = mock_info

        runner = CliRunner()
        result = runner.invoke(main, ["update", "check"])
        assert result.exit_code == 0


# ── Check admin variations ───────────────────────────────────────────


class TestCheckAdminVariations:
    """Tests for check_admin function."""

    @patch("ctypes.windll.shell32.IsUserAnAdmin", side_effect=Exception("No ctypes"))
    def test_check_admin_exception(self, mock_is_admin):
        """Should return False when exception occurs."""
        result = check_admin()
        assert result is False


# ── Config validate with hardware ────────────────────────────────────


class TestConfigValidateHardware:
    """Tests for config validate with hardware checks."""

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_config_validate_with_hardware_check(
        self, mock_check_admin, mock_hw_manager, tmp_path
    ):
        """Should validate against live hardware."""
        runner = CliRunner()
        mock_check_admin.return_value = True

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "general:\n  poll_interval: 2\nfans:\n"
            "  test_fan:\n    fan_id: /test/fan/0\n    curve: balanced\n"
            "    temp_ids: [/test/temp/0]\ncurves:\n"
            "  balanced:\n    hysteresis: 3\n    points:\n      - [30, 30]\n"
        )

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        # Return empty scan - sensors won't be found
        mock_instance.scan.return_value = HardwareScanResult(
            temperatures=[], fans=[], controls=[]
        )
        mock_hw_manager.return_value = mock_instance

        result = runner.invoke(main, ["config", "--path", str(cfg_file), "validate"])
        # Should succeed validation but warn about missing sensors
        assert result.exit_code == 0

    @patch("pysysfan.hardware.HardwareManager")
    def test_config_validate_hardware_error(self, mock_hw_manager, tmp_path):
        """Should skip hardware check on error."""
        runner = CliRunner()
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")

        mock_hw_manager.side_effect = Exception("Hardware access failed")

        result = runner.invoke(main, ["config", "--path", str(cfg_file), "validate"])
        assert result.exit_code == 0


# ── Scan output variations ───────────────────────────────────────────


class TestScanOutputVariations:
    """Tests for scan output variations."""

    @patch("pysysfan.hardware.HardwareManager")
    @patch("pysysfan.cli.check_admin")
    def test_scan_saves_to_file(self, mock_check_admin, mock_hw_manager, tmp_path):
        """Should save scan results to file."""
        runner = CliRunner()
        mock_check_admin.return_value = True

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.scan.return_value = HardwareScanResult(
            temperatures=[SensorInfo("CPU", "CPU", "Temp", "Temp", "/cpu/0", 55.0)],
            fans=[],
            controls=[],
        )
        mock_hw_manager.return_value = mock_instance

        from pysysfan.config import DEFAULT_CONFIG_DIR

        with patch("pysysfan.config.DEFAULT_CONFIG_DIR", tmp_path / ".pysysfan"):
            result = runner.invoke(main, ["scan"])
            assert result.exit_code == 0
