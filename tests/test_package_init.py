"""Tests for pysysfan.__init__ - Package version handling."""

import pytest
from unittest.mock import patch, MagicMock


class TestPackageVersion:
    """Tests for __version__ handling."""

    def test_version_when_package_found(self):
        """Should return version when package is installed."""
        # Patch at the module level where it's imported
        with patch("importlib.metadata.version", return_value="1.2.3"):
            import importlib
            import pysysfan

            importlib.reload(pysysfan)
            assert pysysfan.__version__ == "1.2.3"

    def test_version_when_package_not_found(self):
        """Should return dev version when package not installed."""
        from importlib.metadata import PackageNotFoundError

        # Patch at the module level
        with patch(
            "importlib.metadata.version", side_effect=PackageNotFoundError("pysysfan")
        ):
            import importlib
            import pysysfan

            importlib.reload(pysysfan)
            assert pysysfan.__version__ == "0.0.0-dev"
