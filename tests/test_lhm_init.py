"""Tests for pysysfan.lhm — DLL path resolution and lazy loading behavior."""

import importlib
from unittest.mock import patch
import os

import pytest

from pysysfan.lhm import get_lhm_dll_path, get_lhm_version, LHM_DLL_NAME


# ── get_lhm_dll_path ─────────────────────────────────────────────────


class TestGetLhmDllPath:
    """Tests for get_lhm_dll_path()."""

    def test_env_var_file(self, tmp_path):
        """Should return the path from PYSYSFAN_LHM_PATH when it points to a file."""
        dll = tmp_path / "LibreHardwareMonitorLib.dll"
        dll.write_bytes(b"fake")

        with patch.dict(os.environ, {"PYSYSFAN_LHM_PATH": str(dll)}):
            result = get_lhm_dll_path()
        assert result == dll

    def test_env_var_directory(self, tmp_path):
        """Should find the DLL inside a directory pointed to by PYSYSFAN_LHM_PATH."""
        dll = tmp_path / LHM_DLL_NAME
        dll.write_bytes(b"fake")

        with patch.dict(os.environ, {"PYSYSFAN_LHM_PATH": str(tmp_path)}):
            result = get_lhm_dll_path()
        assert result == dll

    def test_default_location(self, tmp_path):
        """Should find the DLL in the default LHM_DIR."""
        dll = tmp_path / LHM_DLL_NAME
        dll.write_bytes(b"fake")

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("pysysfan.lhm.LHM_DIR", tmp_path),
        ):
            result = get_lhm_dll_path()
        assert result == dll

    def test_not_found_raises(self, tmp_path):
        """Should raise FileNotFoundError when DLL is nowhere to be found."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("pysysfan.lhm.LHM_DIR", tmp_path),
        ):
            with pytest.raises(FileNotFoundError, match="LibreHardwareMonitorLib.dll"):
                get_lhm_dll_path()


# ── get_lhm_version ──────────────────────────────────────────────────


class TestGetLhmVersion:
    """Tests for get_lhm_version()."""

    def test_returns_none_when_dll_missing(self):
        """Should return None when the DLL is not found."""
        with patch(
            "pysysfan.lhm.get_lhm_dll_path",
            side_effect=FileNotFoundError("not found"),
        ):
            assert get_lhm_version() is None


class TestLoadLhm:
    """Tests for lazy CLR/LHM loading."""

    def test_import_does_not_initialize_clr(self):
        """Importing the module should not eagerly load pythonnet runtime."""
        with patch("pythonnet.load") as mock_load:
            module = importlib.import_module("pysysfan.lhm")
            importlib.reload(module)
            mock_load.assert_not_called()

    def test_load_lhm_is_cached(self):
        """load_lhm() should initialize CLR and assembly only on first call."""
        module = importlib.import_module("pysysfan.lhm")
        importlib.reload(module)

        class _FakeClr:
            def __init__(self) -> None:
                self.calls = 0

            def AddReference(self, _name: str) -> None:  # noqa: N802
                self.calls += 1

        fake_clr = _FakeClr()
        fake_hardware = object()

        with (
            patch("pysysfan.lhm._ensure_clr") as mock_ensure_clr,
            patch("pysysfan.lhm.get_lhm_dll_path") as mock_get_path,
            patch.dict("sys.modules", {"clr": fake_clr}),
            patch.dict(
                "sys.modules",
                {"LibreHardwareMonitor": type("_M", (), {"Hardware": fake_hardware})},
            ),
        ):
            from pathlib import Path

            mock_get_path.return_value = Path("C:/tmp/LibreHardwareMonitorLib.dll")
            first = module.load_lhm()
            second = module.load_lhm()

        assert first is fake_hardware
        assert second is fake_hardware
        assert mock_ensure_clr.call_count == 1
        assert fake_clr.calls == 1
