"""Tests for pysysfan.lhm — DLL path resolution and version checking."""

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
