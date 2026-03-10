"""Persistent desktop GUI preference helpers backed by Qt settings."""

from __future__ import annotations

from PySide6.QtCore import QSettings

MINIMIZE_TO_TRAY_KEY = "desktop/minimizeToTray"


def _settings() -> QSettings:
    """Return the application settings store for desktop preferences."""
    return QSettings()


def get_minimize_to_tray(default: bool = False) -> bool:
    """Return whether title-bar minimize should hide the app to the tray."""
    return bool(
        _settings().value(MINIMIZE_TO_TRAY_KEY, defaultValue=default, type=bool)
    )


def set_minimize_to_tray(enabled: bool) -> None:
    """Persist whether title-bar minimize should hide the app to the tray."""
    settings = _settings()
    settings.setValue(MINIMIZE_TO_TRAY_KEY, bool(enabled))
    settings.sync()
