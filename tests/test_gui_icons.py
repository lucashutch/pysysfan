"""Tests for packaged GUI icon resources."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from pysysfan.gui.desktop.app import get_or_create_application
from pysysfan.gui.desktop.icons import app_icon, icon_svg_bytes


def test_packaged_icon_svg_is_available() -> None:
    """The packaged SVG asset should be readable at runtime."""
    svg = icon_svg_bytes().decode("utf-8")

    assert "<svg" in svg
    assert "curveGradient" in svg


def test_app_icon_loads_from_packaged_svg() -> None:
    """The desktop GUI should be able to build a non-null application icon."""
    get_or_create_application([])

    icon = app_icon()

    assert icon.isNull() is False
    assert icon.availableSizes()
