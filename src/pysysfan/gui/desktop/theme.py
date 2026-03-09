"""Shared styling helpers for the PySide6 desktop GUI."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

PAGE_HEADING_STYLE = "font-size: 24px; font-weight: 800;"
SECTION_HINT_STYLE = "font-size: 12px;"
SUBTLE_TEXT_STYLE = "font-size: 12px;"
EMPHASIS_TEXT_STYLE = "font-size: 13px; font-weight: 600;"
SECTION_TITLE_STYLE = "font-size: 16px; font-weight: 700;"
SECTION_SUBTITLE_STYLE = "font-size: 12px;"


class DesktopColors(dict[str, str]):
    """Simple palette token mapping for desktop styles."""


def _hex(color: QColor) -> str:
    return color.name(QColor.NameFormat.HexRgb)


def _mix(color: QColor, other: QColor, ratio: float) -> QColor:
    inverse = 1.0 - ratio
    return QColor(
        round(color.red() * inverse + other.red() * ratio),
        round(color.green() * inverse + other.green() * ratio),
        round(color.blue() * inverse + other.blue() * ratio),
    )


def is_dark_palette(palette: QPalette) -> bool:
    """Return whether a palette is visually dark."""
    return palette.color(QPalette.ColorRole.Window).lightness() < 128


def desktop_colors(palette: QPalette) -> DesktopColors:
    """Build a set of palette-aware surface and text colors."""
    dark = is_dark_palette(palette)
    window = palette.color(QPalette.ColorRole.Window)
    base = palette.color(QPalette.ColorRole.Base)
    text = palette.color(QPalette.ColorRole.WindowText)
    accent = palette.color(QPalette.ColorRole.Highlight)
    muted = _mix(text, window, 0.45 if dark else 0.6)
    border = _mix(text, window, 0.78 if dark else 0.86)
    raised = _mix(base, window, 0.3 if dark else 0.1)
    panel = _mix(base, accent, 0.08 if dark else 0.03)
    card = _mix(base, accent, 0.06 if dark else 0.015)
    graph = _mix(base, window, 0.12 if dark else 0.03)
    return DesktopColors(
        window=_hex(window),
        base=_hex(base),
        text=_hex(text),
        muted=_hex(muted),
        border=_hex(border),
        raised=_hex(raised),
        panel=_hex(panel),
        card=_hex(card),
        accent=_hex(accent),
        graph=_hex(graph),
    )


def dashboard_page_stylesheet(palette: QPalette) -> str:
    """Return a palette-aware stylesheet for the dashboard page."""
    colors = desktop_colors(palette)
    return f"""
QWidget#dashboardRoot {{
    background: {colors["window"]};
    color: {colors["text"]};
}}

QScrollArea#dashboardScrollArea {{
    border: 0;
    background: transparent;
}}

QWidget#dashboardContent {{
    background: {colors["window"]};
}}

QGroupBox {{
    border: 1px solid {colors["border"]};
    border-radius: 18px;
    margin-top: 14px;
    padding-top: 8px;
    background: {colors["raised"]};
    color: {colors["text"]};
    font-size: 15px;
    font-weight: 800;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: {colors["text"]};
}}

QFrame#profileSummaryCard,
QFrame[cardRole="fan-summary"],
QFrame#statusStrip {{
    border: 1px solid {colors["border"]};
    border-radius: 18px;
    background: {colors["card"]};
}}

QLabel#daemonIndicator {{
    font-size: 18px;
    font-weight: 900;
}}

QLabel#dashboardMessageLabel {{
    border-radius: 12px;
    padding: 8px 10px;
    background: {colors["raised"]};
}}

QLabel[sectionRole="title"] {{
    font-size: 18px;
    font-weight: 800;
    color: {colors["text"]};
}}

QLabel[sectionRole="subtitle"] {{
    font-size: 12px;
    color: {colors["muted"]};
}}

QLabel[cardTextRole="eyebrow"] {{
    font-size: 11px;
    font-weight: 700;
    color: {colors["muted"]};
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}

QLabel[cardTextRole="title"] {{
    font-size: 14px;
    font-weight: 800;
    color: {colors["text"]};
}}

QLabel[cardTextRole="value"] {{
    font-size: 22px;
    font-weight: 900;
    color: {colors["text"]};
}}

QLabel[cardTextRole="body"] {{
    font-size: 12px;
    color: {colors["text"]};
}}

QLabel[cardTextRole="muted"] {{
    font-size: 12px;
    color: {colors["muted"]};
}}

QLabel[cardTextRole="icon"] {{
    font-size: 18px;
}}

QToolButton#alertsButton,
QComboBox#historySelector {{
    border: 1px solid {colors["border"]};
    border-radius: 12px;
    padding: 6px 10px;
    background: {colors["raised"]};
    color: {colors["text"]};
    font-weight: 700;
}}

QToolButton#alertsButton::menu-indicator {{
    image: none;
    width: 0;
}}

QTableWidget, QListWidget {{
    border: 1px solid {colors["border"]};
    border-radius: 12px;
    background: {colors["base"]};
    color: {colors["text"]};
    gridline-color: {colors["border"]};
}}

QHeaderView::section {{
    background: {colors["raised"]};
    color: {colors["text"]};
    border: 0;
    border-bottom: 1px solid {colors["border"]};
    padding: 8px;
    font-weight: 700;
}}
"""


def badge_stylesheet(tone: str, palette: QPalette) -> str:
    """Return a rounded badge stylesheet for a semantic tone."""
    colors = desktop_colors(palette)
    dark = is_dark_palette(palette)
    tone_map = {
        "neutral": (colors["raised"], colors["text"]),
        "info": ("#1d4ed8" if dark else "#dbeafe", "#dbeafe" if dark else "#1d4ed8"),
        "success": ("#166534" if dark else "#dcfce7", "#dcfce7" if dark else "#166534"),
        "warning": ("#92400e" if dark else "#fef3c7", "#fef3c7" if dark else "#92400e"),
        "critical": (
            "#b91c1c" if dark else "#fee2e2",
            "#fee2e2" if dark else "#b91c1c",
        ),
    }
    background, foreground = tone_map.get(tone, tone_map["neutral"])
    return (
        "border-radius: 999px;"
        "padding: 4px 10px;"
        "font-size: 11px;"
        "font-weight: 800;"
        f"background: {background};"
        f"color: {foreground};"
    )


def message_stylesheet(*, is_error: bool, palette: QPalette) -> str:
    """Return a consistent message style that respects the active palette."""
    colors = desktop_colors(palette)
    accent = "#ef4444" if is_error else colors["accent"]
    return f"font-size: 12px;font-weight: 700;color: {accent};"


def plot_theme(palette: QPalette) -> dict[str, str | list[str]]:
    """Return palette-aware colors for pyqtgraph widgets."""
    colors = desktop_colors(palette)
    dark = is_dark_palette(palette)
    series = [
        "#60a5fa",
        "#34d399",
        "#f59e0b",
        "#f87171",
        "#a78bfa",
        "#22d3ee",
        "#f472b6",
        "#c084fc",
    ]
    if not dark:
        series = [
            "#2563eb",
            "#059669",
            "#d97706",
            "#dc2626",
            "#7c3aed",
            "#0891b2",
            "#db2777",
            "#9333ea",
        ]
    return {
        "background": colors["graph"],
        "foreground": colors["text"],
        "grid": colors["border"],
        "muted": colors["muted"],
        "series": series,
    }
