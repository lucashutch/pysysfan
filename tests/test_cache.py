"""Tests for pysysfan.cache — Hardware scan caching functionality."""

import json
from pathlib import Path
from unittest.mock import patch


from pysysfan.cache import (
    CACHE_VERSION,
    DEFAULT_CACHE_PATH,
    HardwareCache,
    HardwareCacheManager,
    get_default_cache_manager,
)
from pysysfan.platforms.base import ControlInfo, HardwareScanResult, SensorInfo


# ── HardwareCache Tests ──────────────────────────────────────────────


class TestHardwareCache:
    """Tests for HardwareCache dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        cache = HardwareCache()
        assert cache.version == CACHE_VERSION
        assert cache.fingerprint == ""
        assert cache.temperatures == []
        assert cache.fans == []
        assert cache.controls == []
        assert cache.timestamp == ""

    def test_custom_values(self):
        """Should accept custom values."""
        cache = HardwareCache(
            version=2,
            fingerprint="abc123",
            temperatures=[{"identifier": "/cpu/0", "name": "Core 0"}],
            timestamp="2024-01-01T00:00:00",
        )
        assert cache.version == 2
        assert cache.fingerprint == "abc123"
        assert len(cache.temperatures) == 1


class TestHardwareCacheFromScanResult:
    """Tests for HardwareCache.from_scan_result()."""

    def test_from_empty_result(self):
        """Should handle empty scan result."""
        result = HardwareScanResult()
        cache = HardwareCache.from_scan_result("fp123", result)

        assert cache.fingerprint == "fp123"
        assert cache.temperatures == []
        assert cache.fans == []
        assert cache.controls == []
        assert cache.version == CACHE_VERSION
        assert cache.timestamp != ""

    def test_from_result_with_data(self):
        """Should extract data from scan result."""
        result = HardwareScanResult()
        result.temperatures.append(
            SensorInfo(
                hardware_name="CPU",
                hardware_type="Cpu",
                sensor_name="Core 0",
                sensor_type="Temperature",
                identifier="/cpu/0/temp",
                value=45.0,
            )
        )
        result.fans.append(
            SensorInfo(
                hardware_name="Motherboard",
                hardware_type="Motherboard",
                sensor_name="Fan 1",
                sensor_type="Fan",
                identifier="/mb/fan/0",
                value=1200.0,
            )
        )
        result.controls.append(
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="Fan Control 1",
                identifier="/mb/control/0",
                current_value=50.0,
                has_control=True,
            )
        )

        cache = HardwareCache.from_scan_result("fp456", result)

        assert cache.fingerprint == "fp456"
        assert len(cache.temperatures) == 1
        assert cache.temperatures[0]["identifier"] == "/cpu/0/temp"
        assert cache.temperatures[0]["name"] == "Core 0"
        assert cache.temperatures[0]["hardware"] == "CPU"

        assert len(cache.fans) == 1
        assert cache.fans[0]["identifier"] == "/mb/fan/0"

        assert len(cache.controls) == 1
        assert cache.controls[0]["identifier"] == "/mb/control/0"
        assert cache.controls[0]["has_control"] is True


class TestHardwareCacheToScanResult:
    """Tests for HardwareCache.to_scan_result()."""

    def test_to_empty_result(self):
        """Should handle empty cache."""
        cache = HardwareCache()
        result = cache.to_scan_result()

        assert isinstance(result, HardwareScanResult)
        assert result.temperatures == []
        assert result.fans == []
        assert result.controls == []

    def test_to_result_with_data(self):
        """Should reconstruct scan result from cache."""
        cache = HardwareCache(
            temperatures=[
                {"identifier": "/cpu/0", "name": "Core 0", "hardware": "CPU"}
            ],
            fans=[{"identifier": "/mb/fan/0", "name": "Fan 1", "hardware": "MB"}],
            controls=[
                {
                    "identifier": "/mb/control/0",
                    "name": "Control 1",
                    "hardware": "MB",
                    "has_control": True,
                }
            ],
        )

        result = cache.to_scan_result()

        assert len(result.temperatures) == 1
        temp = result.temperatures[0]
        assert temp.identifier == "/cpu/0"
        assert temp.sensor_name == "Core 0"
        assert temp.hardware_name == "CPU"
        assert temp.sensor_type == "Temperature"
        assert temp.value is None

        assert len(result.fans) == 1
        assert len(result.controls) == 1
        assert result.controls[0].has_control is True

    def test_missing_optional_fields(self):
        """Should handle missing optional fields gracefully."""
        cache = HardwareCache(
            temperatures=[{"identifier": "/cpu/0"}],  # Missing name and hardware
            fans=[{}],  # Empty fan dict
            controls=[{"identifier": "/ctrl/0"}],  # Missing has_control
        )

        result = cache.to_scan_result()

        assert len(result.temperatures) == 1
        assert result.temperatures[0].sensor_name == ""  # Default
        assert result.temperatures[0].hardware_name == ""  # Default

        assert len(result.fans) == 1
        assert result.fans[0].identifier == ""  # Default

        assert len(result.controls) == 1
        assert result.controls[0].has_control is False  # Default


# ── HardwareCacheManager Tests ───────────────────────────────────────


class TestHardwareCacheManager:
    """Tests for HardwareCacheManager."""

    def test_default_path(self):
        """Should use default cache path."""
        manager = HardwareCacheManager()
        assert manager.cache_path == DEFAULT_CACHE_PATH

    def test_custom_path(self):
        """Should accept custom cache path."""
        custom_path = Path("/tmp/test_cache.json")
        manager = HardwareCacheManager(cache_path=custom_path)
        assert manager.cache_path == custom_path


class TestHardwareCacheManagerLoad:
    """Tests for loading cache from disk."""

    def test_load_nonexistent_file(self):
        """Should return None when file doesn't exist."""
        manager = HardwareCacheManager(cache_path=Path("/nonexistent/cache.json"))
        result = manager.load()
        assert result is None

    def test_load_valid_cache(self, tmp_path):
        """Should load valid cache file."""
        cache_file = tmp_path / "cache.json"
        cache_data = {
            "version": CACHE_VERSION,
            "fingerprint": "test_fp",
            "temperatures": [{"identifier": "/cpu/0", "name": "Core 0"}],
            "fans": [],
            "controls": [],
            "timestamp": "2024-01-01T00:00:00",
        }
        cache_file.write_text(json.dumps(cache_data))

        manager = HardwareCacheManager(cache_path=cache_file)
        result = manager.load()

        assert result is not None
        assert result.fingerprint == "test_fp"
        assert result.version == CACHE_VERSION

    def test_load_version_mismatch(self, tmp_path):
        """Should return None when version doesn't match."""
        cache_file = tmp_path / "cache.json"
        cache_data = {
            "version": 999,  # Wrong version
            "fingerprint": "test_fp",
            "temperatures": [],
            "fans": [],
            "controls": [],
            "timestamp": "2024-01-01T00:00:00",
        }
        cache_file.write_text(json.dumps(cache_data))

        manager = HardwareCacheManager(cache_path=cache_file)
        result = manager.load()

        assert result is None

    def test_load_invalid_json(self, tmp_path):
        """Should return None for invalid JSON."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("not valid json")

        manager = HardwareCacheManager(cache_path=cache_file)
        result = manager.load()

        assert result is None

    def test_load_missing_fields(self, tmp_path):
        """Should handle missing optional fields."""
        cache_file = tmp_path / "cache.json"
        cache_data = {
            "version": CACHE_VERSION,
            "fingerprint": "test_fp",
            # Missing temperatures, fans, controls, timestamp
        }
        cache_file.write_text(json.dumps(cache_data))

        manager = HardwareCacheManager(cache_path=cache_file)
        result = manager.load()

        assert result is not None
        assert result.temperatures == []
        assert result.fans == []
        assert result.controls == []
        assert result.timestamp == ""


class TestHardwareCacheManagerSave:
    """Tests for saving cache to disk."""

    def test_save_creates_directory(self, tmp_path):
        """Should create parent directories."""
        cache_file = tmp_path / "subdir" / "cache.json"
        manager = HardwareCacheManager(cache_path=cache_file)

        cache = HardwareCache(fingerprint="test")
        manager.save(cache)

        assert cache_file.exists()

    def test_save_writes_valid_json(self, tmp_path):
        """Should write valid JSON."""
        cache_file = tmp_path / "cache.json"
        manager = HardwareCacheManager(cache_path=cache_file)

        cache = HardwareCache(
            fingerprint="abc123",
            temperatures=[{"identifier": "/cpu/0", "name": "Core 0"}],
            timestamp="2024-01-01T00:00:00",
        )
        manager.save(cache)

        data = json.loads(cache_file.read_text())
        assert data["fingerprint"] == "abc123"
        assert data["version"] == CACHE_VERSION
        assert len(data["temperatures"]) == 1

    def test_save_handles_error(self, tmp_path):
        """Should handle write errors gracefully."""
        cache_file = tmp_path / "cache.json"
        manager = HardwareCacheManager(cache_path=cache_file)

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            cache = HardwareCache(fingerprint="test")
            # Should not raise
            manager.save(cache)


class TestHardwareCacheManagerIsValid:
    """Tests for cache validation."""

    def test_valid_when_fingerprint_matches(self):
        """Should return True when fingerprint matches."""
        manager = HardwareCacheManager()
        manager._cache = HardwareCache(fingerprint="matching_fp")

        assert manager.is_valid("matching_fp") is True

    def test_invalid_when_no_cache(self):
        """Should return False when no cache loaded."""
        manager = HardwareCacheManager()
        assert manager.is_valid("any_fp") is False

    def test_invalid_when_fingerprint_mismatch(self):
        """Should return False when fingerprint doesn't match."""
        manager = HardwareCacheManager()
        manager._cache = HardwareCache(fingerprint="old_fp")

        assert manager.is_valid("new_fp") is False


class TestHardwareCacheManagerGetCachedScanResult:
    """Tests for retrieving cached scan result."""

    def test_returns_none_when_no_cache(self):
        """Should return None when no cache loaded."""
        manager = HardwareCacheManager()
        result = manager.get_cached_scan_result()
        assert result is None

    def test_returns_scan_result_when_cached(self):
        """Should return scan result from cache."""
        manager = HardwareCacheManager()
        manager._cache = HardwareCache(
            fingerprint="test",
            temperatures=[{"identifier": "/cpu/0", "name": "Core 0"}],
        )

        result = manager.get_cached_scan_result()

        assert result is not None
        assert isinstance(result, HardwareScanResult)
        assert len(result.temperatures) == 1


# ── Module-level Functions ───────────────────────────────────────────


class TestGetDefaultCacheManager:
    """Tests for get_default_cache_manager()."""

    def test_returns_manager(self):
        """Should return a HardwareCacheManager."""
        manager = get_default_cache_manager()
        assert isinstance(manager, HardwareCacheManager)
        assert manager.cache_path == DEFAULT_CACHE_PATH
