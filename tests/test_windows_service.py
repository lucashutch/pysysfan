"""Tests for pysysfan.platforms.windows_service — Windows Task Scheduler integration."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pysysfan.platforms.windows_service import (
    _build_task_command,
    _build_task_xml,
    _hidden_process_kwargs,
    _is_windows_store_stub,
    _pysysfan_exe,
    _pysysfan_service_exe,
    _pysysfan_uv_venv_exe,
    _uv_tool_dir,
    clean_all,
    get_service_status,
    install_task,
    uninstall_task,
    get_task_status,
)


class TestWindowsStoreStub:
    """Tests for _is_windows_store_stub()."""

    def test_detects_windowsapps_path(self):
        assert _is_windows_store_stub(
            r"C:\Users\lucas\AppData\Local\Microsoft\WindowsApps\python.exe"
        )

    def test_detects_case_insensitive(self):
        assert _is_windows_store_stub(
            r"C:\Users\lucas\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe"
        )

    def test_normal_exe_not_a_stub(self):
        assert not _is_windows_store_stub(r"C:\tools\pysysfan.exe")
        assert not _is_windows_store_stub(
            r"C:\Users\lucas\AppData\Roaming\uv\tools\pysysfan\Scripts\pysysfan.exe"
        )


class TestUvToolDir:
    """Tests for _uv_tool_dir()."""

    @patch(
        "pysysfan.platforms.windows_service.shutil.which",
        return_value=r"C:\tools\uv.exe",
    )
    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_returns_path_from_uv(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=r"C:\Users\lucas\AppData\Roaming\uv\tools" + "\n"
        )
        result = _uv_tool_dir()
        assert result == Path(r"C:\Users\lucas\AppData\Roaming\uv\tools")

    @patch("pysysfan.platforms.windows_service.shutil.which", return_value=None)
    def test_returns_none_when_uv_not_found(self, mock_which):
        with patch.dict("os.environ", {"APPDATA": ""}, clear=False):
            result = _uv_tool_dir()
        assert result is None


class TestPysysfanUvVenvExe:
    """Tests for _pysysfan_uv_venv_exe()."""

    @patch("pysysfan.platforms.windows_service._uv_tool_dir")
    def test_returns_none_when_no_tool_dir(self, mock_dir):
        mock_dir.return_value = None
        assert _pysysfan_uv_venv_exe() is None

    @patch("pysysfan.platforms.windows_service._uv_tool_dir")
    def test_returns_exe_when_found(self, mock_dir, tmp_path):
        scripts = tmp_path / "pysysfan" / "Scripts"
        scripts.mkdir(parents=True)
        exe = scripts / "pysysfan.exe"
        exe.write_bytes(b"fake exe")
        mock_dir.return_value = tmp_path
        assert _pysysfan_uv_venv_exe() == str(exe)

    @patch("pysysfan.platforms.windows_service._uv_tool_dir")
    def test_returns_none_when_venv_missing(self, mock_dir, tmp_path):
        mock_dir.return_value = tmp_path
        assert _pysysfan_uv_venv_exe() is None


class TestPysysfanServiceExe:
    """Tests for _pysysfan_service_exe()."""

    @patch("pysysfan.platforms.windows_service._pysysfan_service_uv_venv_exe")
    def test_prefers_service_uv_venv_exe(self, mock_svc_exe):
        mock_svc_exe.return_value = (
            r"C:\AppData\Roaming\uv\tools\pysysfan\Scripts\pysysfan-service.exe"
        )
        assert _pysysfan_service_exe() == (
            r"C:\AppData\Roaming\uv\tools\pysysfan\Scripts\pysysfan-service.exe"
        )

    @patch(
        "pysysfan.platforms.windows_service._pysysfan_service_uv_venv_exe",
        return_value=None,
    )
    @patch("pysysfan.platforms.windows_service._find_exe_in_path")
    @patch(
        "pysysfan.platforms.windows_service._pysysfan_uv_venv_exe",
        return_value=r"C:\tools\pysysfan.exe",
    )
    def test_falls_back_to_pysysfan(self, mock_uv, mock_path, mock_svc):
        """When pysysfan-service.exe is not found, falls back to pysysfan.exe."""
        mock_path.return_value = None  # no pysysfan-service in PATH either
        result = _pysysfan_service_exe()
        assert result == r"C:\tools\pysysfan.exe"


class TestPysysfanExe:
    """Tests for _pysysfan_exe()."""

    @patch("pysysfan.platforms.windows_service._pysysfan_uv_venv_exe")
    def test_prefers_uv_venv_exe(self, mock_uv_exe):
        """Should prefer the UV tool venv exe over PATH."""
        mock_uv_exe.return_value = (
            r"C:\AppData\Roaming\uv\tools\pysysfan\Scripts\pysysfan.exe"
        )
        assert (
            _pysysfan_exe()
            == r"C:\AppData\Roaming\uv\tools\pysysfan\Scripts\pysysfan.exe"
        )

    @patch(
        "pysysfan.platforms.windows_service._pysysfan_uv_venv_exe", return_value=None
    )
    @patch("pysysfan.platforms.windows_service.shutil.which")
    def test_found_in_path(self, mock_which, mock_uv):
        """Should return the PATH exe when no UV venv exe is found."""
        mock_which.return_value = r"C:\tools\pysysfan.exe"
        assert _pysysfan_exe() == r"C:\tools\pysysfan.exe"

    @patch(
        "pysysfan.platforms.windows_service._pysysfan_uv_venv_exe", return_value=None
    )
    @patch("pysysfan.platforms.windows_service.shutil.which")
    def test_skips_windows_store_stub(self, mock_which, mock_uv):
        """Should skip Windows Store app stubs and raise FileNotFoundError."""
        mock_which.return_value = (
            r"C:\Users\u\AppData\Local\Microsoft\WindowsApps\python.exe"
        )
        with pytest.raises(FileNotFoundError, match="not found in PATH"):
            _pysysfan_exe()

    @patch(
        "pysysfan.platforms.windows_service._pysysfan_uv_venv_exe", return_value=None
    )
    @patch("pysysfan.platforms.windows_service.shutil.which", return_value=None)
    def test_raises_when_not_found(self, mock_which, mock_uv):
        """Should raise FileNotFoundError when not in PATH."""
        with pytest.raises(FileNotFoundError, match="not found in PATH"):
            _pysysfan_exe()


class TestHiddenProcessKwargs:
    """Tests for the hidden subprocess helper."""

    def test_returns_stable_shape(self):
        """The helper should return kwargs on Windows and no-op elsewhere."""
        kwargs = _hidden_process_kwargs()
        assert kwargs == {} or "creationflags" in kwargs


class TestInstallTask:
    """Tests for install_task() — XML-based task creation."""

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    @patch(
        "pysysfan.platforms.windows_service._pysysfan_service_exe",
        return_value=r"C:\tools\pysysfan-service.exe",
    )
    @patch(
        "pysysfan.platforms.windows_service._get_current_username",
        return_value="testuser",
    )
    def test_success(self, mock_user, mock_exe, mock_run):
        """Should call schtasks /Create with /XML flag."""
        mock_run.return_value = MagicMock(returncode=0)
        install_task()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "schtasks" in args
        assert "/Create" in args
        assert "/XML" in args
        assert "/F" in args

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    @patch(
        "pysysfan.platforms.windows_service._pysysfan_service_exe",
        return_value=r"C:\tools\pysysfan-service.exe",
    )
    @patch(
        "pysysfan.platforms.windows_service._get_current_username",
        return_value="testuser",
    )
    def test_with_config_path(self, mock_user, mock_exe, mock_run):
        """Should include custom config path in the XML task definition."""
        mock_run.return_value = MagicMock(returncode=0)
        install_task(config_path=r"C:\cfg\config.yaml")
        # Verify schtasks was called (XML content itself is tested in TestBuildTaskXml)
        mock_run.assert_called_once()

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    @patch(
        "pysysfan.platforms.windows_service._pysysfan_service_exe",
        return_value=r"C:\tools\pysysfan-service.exe",
    )
    @patch(
        "pysysfan.platforms.windows_service._get_current_username",
        return_value="testuser",
    )
    def test_failure_raises(self, mock_user, mock_exe, mock_run):
        """Should raise RuntimeError when schtasks fails."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="error", stderr="access denied"
        )
        with pytest.raises(RuntimeError, match="schtasks /Create failed"):
            install_task()


class TestBuildTaskCommand:
    """Tests for the task command builder."""

    def test_build_task_command_with_exe_and_config(self):
        """Should build a direct exe invocation."""
        exe = r"C:\Users\lucas\AppData\Roaming\uv\tools\pysysfan\Scripts\pysysfan-service.exe"
        config = Path(r"C:\Users\lucas\.pysysfan\config.yaml")

        command = _build_task_command(exe, config)

        assert command.startswith('"')
        assert "pysysfan-service.exe" in command
        assert "--config" in command
        assert ".pysysfan" in command

    def test_build_task_command_stays_under_limit(self):
        """Task command should stay under 260 char Windows limit."""
        exe = r"C:\tools\pysysfan-service.exe"
        config = Path(r"C:\Users\lucas\.pysysfan\config.yaml")

        command = _build_task_command(exe, config)

        assert len(command) < 261


class TestBuildTaskXml:
    """Tests for the XML task definition builder."""

    def test_xml_contains_required_elements(self):
        """XML should contain all required task scheduler elements."""
        xml = _build_task_xml(
            r"C:\tools\pysysfan-service.exe",
            Path(r"C:\Users\lucas\.pysysfan\config.yaml"),
            "testuser",
        )
        assert "LogonTrigger" in xml
        assert "HighestAvailable" in xml
        assert "InteractiveToken" in xml
        assert "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>" in xml
        assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in xml
        assert "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>" in xml
        assert "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>" in xml
        assert "<AllowStartOnDemand>true</AllowStartOnDemand>" in xml
        assert "pysysfan-service.exe" in xml
        assert "testuser" in xml

    def test_xml_escapes_special_characters(self):
        """Should escape XML special characters in paths and username."""
        xml = _build_task_xml(
            r"C:\tools\pysysfan & son.exe",
            Path(r"C:\Users\<bob>\config.yaml"),
            "user&admin",
        )
        assert "&amp;" in xml
        assert "&lt;bob&gt;" in xml
        assert "user&amp;admin" in xml


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


class TestGetServiceStatus:
    """Tests for `get_service_status()`."""

    @patch("pysysfan.platforms.windows_service.read_state")
    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_uses_hidden_process_kwargs(self, mock_run, mock_read_state):
        """Task status queries should use the hidden-window subprocess kwargs."""
        mock_read_state.return_value = None
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Status: Running\n"),
            MagicMock(returncode=0, stdout="Last Run Time: N/A\n"),
        ]

        get_service_status()

        assert mock_run.call_count == 2
        for call in mock_run.call_args_list:
            kwargs = call.kwargs
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            hidden = _hidden_process_kwargs()
            for key, value in hidden.items():
                if key == "startupinfo":
                    assert kwargs[key].dwFlags == value.dwFlags
                    assert kwargs[key].wShowWindow == value.wShowWindow
                else:
                    assert kwargs[key] == value


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


class TestCleanAll:
    """Tests for clean_all()."""

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_clean_all_deletes_task_and_processes(self, mock_run):
        """Should attempt to kill processes and delete the task."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        messages = clean_all()
        assert any("Killed" in m or "Deleted" in m for m in messages)

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_clean_all_when_nothing_installed(self, mock_run):
        """Should report gracefully when nothing is installed."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
        messages = clean_all()
        assert any("not installed" in m.lower() for m in messages)

    @patch("pysysfan.platforms.windows_service.subprocess.run")
    def test_clean_all_removes_state_files(self, mock_run, tmp_path):
        """Should remove state and log files when they exist."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")

        import pysysfan.platforms.windows_service as ws

        state = tmp_path / "daemon_state.json"
        history = tmp_path / "daemon_history.ndjson"
        log = tmp_path / "service.log"
        state.write_text("{}")
        history.write_text("")
        log.write_text("")

        orig_state = ws.STATE_FILE_PATH
        orig_hist = ws.HISTORY_FILE_PATH
        orig_log = ws.SERVICE_LOG_PATH
        try:
            ws.STATE_FILE_PATH = state
            ws.HISTORY_FILE_PATH = history
            ws.SERVICE_LOG_PATH = log
            messages = clean_all()
        finally:
            ws.STATE_FILE_PATH = orig_state
            ws.HISTORY_FILE_PATH = orig_hist
            ws.SERVICE_LOG_PATH = orig_log

        assert not state.exists()
        assert not history.exists()
        assert not log.exists()
        assert any("daemon_state.json" in m for m in messages)
