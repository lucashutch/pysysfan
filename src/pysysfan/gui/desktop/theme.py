"""Shared styling helpers for the PySide6 desktop GUI."""

from __future__ import annotations

PAGE_HEADING_STYLE = "font-size: 22px; font-weight: 700; color: #0f172a;"
SECTION_HINT_STYLE = "font-size: 12px; color: #475569;"
SUBTLE_TEXT_STYLE = "font-size: 12px; color: #64748b;"
EMPHASIS_TEXT_STYLE = "font-size: 13px; font-weight: 600; color: #0f172a;"

_DASHBOARD_BADGE_TONES = {
    "neutral": ("#e2e8f0", "#334155"),
    "info": ("#dbeafe", "#1d4ed8"),
    "success": ("#dcfce7", "#166534"),
    "warning": ("#fef3c7", "#92400e"),
    "critical": ("#fee2e2", "#b91c1c"),
}

DASHBOARD_PAGE_QSS = """
QGroupBox {
    border: 1px solid #dbe4f0;
    border-radius: 16px;
    margin-top: 12px;
    background: #ffffff;
    color: #0f172a;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
}

QLabel#connectionLabel {
    color: #334155;
    font-size: 12px;
    font-weight: 600;
}

QFrame#profileOverviewCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eff6ff, stop:1 #f8fafc);
    border: 1px solid #bfdbfe;
    border-radius: 20px;
}

QFrame[cardRole="metric"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
    border: 1px solid #dbe4f0;
    border-radius: 16px;
}

QFrame[cardRole="fan-summary"] {
    background: #ffffff;
    border: 1px solid #dbe4f0;
    border-radius: 16px;
}

QLabel[cardTextRole="eyebrow"] {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748b;
}

QLabel[cardTextRole="title"] {
    font-size: 13px;
    font-weight: 700;
    color: #0f172a;
}

QLabel[cardTextRole="value"] {
    font-size: 26px;
    font-weight: 800;
    color: #0f172a;
}

QLabel[cardTextRole="body"] {
    font-size: 12px;
    color: #475569;
}

QLabel[cardTextRole="muted"] {
    font-size: 11px;
    color: #64748b;
}

QLabel[cardTextRole="icon"] {
    font-size: 20px;
    font-weight: 700;
    color: #1d4ed8;
}

QTableWidget, QListWidget {
    border: 1px solid #dbe4f0;
    border-radius: 12px;
    background: #ffffff;
    gridline-color: #e2e8f0;
}

QHeaderView::section {
    background: #f8fafc;
    color: #334155;
    border: 0;
    border-bottom: 1px solid #dbe4f0;
    padding: 8px;
    font-weight: 700;
}
"""


def badge_stylesheet(tone: str) -> str:
    """Return a rounded badge stylesheet for a semantic tone."""
    background, foreground = _DASHBOARD_BADGE_TONES.get(
        tone, _DASHBOARD_BADGE_TONES["neutral"]
    )
    return (
        "border-radius: 999px;"
        "padding: 4px 10px;"
        "font-size: 11px;"
        "font-weight: 700;"
        f"background: {background};"
        f"color: {foreground};"
    )


def message_stylesheet(*, is_error: bool) -> str:
    """Return a consistent message color style."""
    color = "#b91c1c" if is_error else "#166534"
    return f"font-size: 12px; font-weight: 600; color: {color};"
