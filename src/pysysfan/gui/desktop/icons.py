"""Icon and Windows application identity helpers for the desktop GUI."""

from __future__ import annotations

import ctypes
import logging
import sys
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

logger = logging.getLogger(__name__)

WINDOWS_APP_USER_MODEL_ID = "lucashutch.pysysfan"
_ICON_RESOURCE_NAME = "pysysfan.svg"
_ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


@lru_cache(maxsize=1)
def icon_svg_bytes() -> bytes:
    """Return the packaged SVG bytes for the application icon."""
    return files("pysysfan.assets").joinpath(_ICON_RESOURCE_NAME).read_bytes()


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    """Build a multi-size `QIcon` from the packaged SVG asset."""
    renderer = QSvgRenderer(QByteArray(icon_svg_bytes()))
    if not renderer.isValid():
        logger.warning("Failed to load packaged PySysFan SVG icon.")
        return QIcon()

    icon = QIcon()
    for size in _ICON_SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            renderer.render(painter, QRectF(0.0, 0.0, float(size), float(size)))
        finally:
            painter.end()
        icon.addPixmap(pixmap)
    return icon


def write_windows_icon_file(output_path: Path | str, size: int = 256) -> bool:
    """Render the packaged SVG icon to a Windows `.ico` file."""
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    existing_app = QGuiApplication.instance()
    temporary_app: QGuiApplication | None = None
    if existing_app is None:
        temporary_app = QGuiApplication([])

    try:
        saved = app_icon().pixmap(size, size).save(str(target_path), "ICO")
        if not saved:
            logger.warning(
                "Unable to write PySysFan Windows icon file: %s", target_path
            )
        return saved
    finally:
        if temporary_app is not None:
            temporary_app.quit()


def configure_windows_app_id(
    app_id: str = WINDOWS_APP_USER_MODEL_ID,
) -> None:
    """Set the explicit Windows AppUserModelID for taskbar grouping and icons."""
    if sys.platform != "win32":
        return

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        logger.debug("Unable to set the Windows AppUserModelID.", exc_info=True)
