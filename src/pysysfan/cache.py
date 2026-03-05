"""Hardware scan caching to speed up daemon startup.

Caches the results of hardware scans to avoid re-detecting hardware on every
startup. The cache is invalidated when hardware changes (e.g., new devices).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pysysfan.platforms.base import HardwareScanResult

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".pysysfan"
DEFAULT_CACHE_PATH = DEFAULT_CACHE_DIR / "hardware_cache.json"


CACHE_VERSION = 1


@dataclass
class HardwareCache:
    """Cached hardware scan results with fingerprint for invalidation.

    Attributes:
        version: Cache format version for migration/invalidation
        fingerprint: Hash-like string representing the hardware configuration
        temperatures: Cached temperature sensor identifiers and names
        fans: Cached fan sensor identifiers and names
        controls: Cached control identifiers and names
        timestamp: When this cache was created
    """

    version: int = CACHE_VERSION
    fingerprint: str = ""
    temperatures: list[dict] = field(default_factory=list)
    fans: list[dict] = field(default_factory=list)
    controls: list[dict] = field(default_factory=list)
    timestamp: str = ""

    @classmethod
    def from_scan_result(
        cls, fingerprint: str, result: HardwareScanResult
    ) -> HardwareCache:
        """Create a cache from a scan result.

        Args:
            fingerprint: Hardware fingerprint
            result: Hardware scan result to cache

        Returns:
            HardwareCache instance
        """
        from datetime import datetime

        return cls(
            fingerprint=fingerprint,
            temperatures=[
                {
                    "identifier": t.identifier,
                    "name": t.sensor_name,
                    "hardware": t.hardware_name,
                }
                for t in result.temperatures
            ],
            fans=[
                {
                    "identifier": f.identifier,
                    "name": f.sensor_name,
                    "hardware": f.hardware_name,
                }
                for f in result.fans
            ],
            controls=[
                {
                    "identifier": c.identifier,
                    "name": c.sensor_name,
                    "hardware": c.hardware_name,
                    "has_control": c.has_control,
                }
                for c in result.controls
            ],
            timestamp=datetime.now().isoformat(),
        )

    def to_scan_result(self) -> HardwareScanResult:
        """Convert cached data back to a HardwareScanResult.

        Returns:
            Reconstructed HardwareScanResult
        """
        from pysysfan.platforms.base import HardwareScanResult, SensorInfo, ControlInfo

        result = HardwareScanResult()

        for t in self.temperatures:
            result.temperatures.append(
                SensorInfo(
                    hardware_name=t.get("hardware", ""),
                    hardware_type="",
                    sensor_name=t.get("name", ""),
                    sensor_type="Temperature",
                    identifier=t.get("identifier", ""),
                    value=None,
                )
            )

        for f in self.fans:
            result.fans.append(
                SensorInfo(
                    hardware_name=f.get("hardware", ""),
                    hardware_type="",
                    sensor_name=f.get("name", ""),
                    sensor_type="Fan",
                    identifier=f.get("identifier", ""),
                    value=None,
                )
            )

        for c in self.controls:
            result.controls.append(
                ControlInfo(
                    hardware_name=c.get("hardware", ""),
                    sensor_name=c.get("name", ""),
                    identifier=c.get("identifier", ""),
                    current_value=None,
                    has_control=c.get("has_control", False),
                )
            )

        return result


class HardwareCacheManager:
    """Manages hardware scan caching to speed up startup.

    The cache stores the results of hardware scans and automatically invalidates
    when hardware changes are detected.
    """

    def __init__(self, cache_path: Path = DEFAULT_CACHE_PATH):
        self.cache_path = Path(cache_path)
        self._cache: HardwareCache | None = None

    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> HardwareCache | None:
        """Load cache from disk.

        Returns:
            Cached hardware data, or None if no valid cache exists
        """
        if not self.cache_path.exists():
            logger.debug("No hardware cache file found")
            return None

        try:
            with open(self.cache_path, "r") as f:
                data = json.load(f)

            cache_version = data.get("version", 0)
            if cache_version != CACHE_VERSION:
                logger.info(
                    f"Hardware cache version mismatch ({cache_version} vs {CACHE_VERSION}), invalidating"
                )
                return None

            self._cache = HardwareCache(
                version=cache_version,
                fingerprint=data.get("fingerprint", ""),
                temperatures=data.get("temperatures", []),
                fans=data.get("fans", []),
                controls=data.get("controls", []),
                timestamp=data.get("timestamp", ""),
            )
            logger.debug(f"Loaded hardware cache from {self.cache_path}")
            return self._cache
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load hardware cache: {e}")
            return None

    def save(self, cache: HardwareCache) -> None:
        """Save cache to disk.

        Args:
            cache: Hardware cache to save
        """
        self._ensure_cache_dir()
        try:
            with open(self.cache_path, "w") as f:
                json.dump(asdict(cache), f, indent=2)
            logger.debug(f"Saved hardware cache to {self.cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save hardware cache: {e}")

    def is_valid(self, current_fingerprint: str) -> bool:
        """Check if the cached data is still valid.

        Args:
            current_fingerprint: Current hardware fingerprint

        Returns:
            True if cache is valid and matches current hardware
        """
        if self._cache is None:
            return False

        if self._cache.fingerprint != current_fingerprint:
            logger.info(
                f"Hardware cache invalidated: fingerprint mismatch "
                f"(cached: {self._cache.fingerprint[:16]}..., current: {current_fingerprint[:16]}...)"
            )
            return False

        logger.debug("Hardware cache is valid")
        return True

    def get_cached_scan_result(self) -> HardwareScanResult | None:
        """Get cached scan result if available.

        Returns:
            Cached scan result, or None if no valid cache
        """
        if self._cache is None:
            return None
        return self._cache.to_scan_result()


def get_default_cache_manager() -> HardwareCacheManager:
    """Get the default hardware cache manager.

    Returns:
        HardwareCacheManager instance
    """
    return HardwareCacheManager()
