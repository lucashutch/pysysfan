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

QFrame#headerBar {{
    background: {colors["raised"]};
    border: 1px solid {colors["border"]};
    border-radius: 12px;
    padding: 8px 16px;
}}

QFrame#healthSummary {{
    background: {colors["card"]};
    border: 1px solid {colors["border"]};
    border-radius: 12px;
    padding: 8px 16px;
}}

QFrame#tableHeader {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {colors["border"]};
    border-radius: 0;
    padding: 6px 0;
}}

QFrame[cardRole="fan-summary"],
QWidget#dashboardStatusCorner {{
    background: transparent;
}}

QFrame[cardRole="fan-summary"] {{
    border: none;
    border-radius: 0;
    padding: 0;
    background: {colors["card"]};
}}

QFrame[cardRole="fan-summary"]:hover {{
    background: {colors["raised"]};
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

QLabel[cardTextRole="metricTitle"] {{
    font-size: 11px;
    font-weight: 700;
    color: {colors["muted"]};
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}

QLabel[cardTextRole="metricValue"] {{
    font-size: 15px;
    font-weight: 800;
    color: {colors["text"]};
}}

QLabel[cardTextRole="body"] {{
    font-size: 12px;
    color: {colors["muted"]};
}}

QLabel[cardTextRole="muted"] {{
    font-size: 12px;
    color: {colors["muted"]};
}}

QLabel[cardTextRole="icon"] {{
    font-size: 18px;
}}

QToolButton#alertsButton {{
    border: 1px solid {colors["border"]};
    border-radius: 12px;
    padding: 5px 10px;
    background: {colors["raised"]};
    color: {colors["text"]};
    font-weight: 700;
}}

QToolButton#alertsButton::menu-indicator {{
    image: none;
    width: 0;
}}
"""


def graphs_page_stylesheet(palette: QPalette) -> str:
    """Return a palette-aware stylesheet for the graphs page."""
    colors = desktop_colors(palette)
    active_border = colors["accent"]
    return f"""
QWidget#graphsRoot {{
    background: {colors["window"]};
    color: {colors["text"]};
}}

QFrame#graphsHeader {{
    background: transparent;
}}

QLabel#graphsHeaderTitle {{
    color: {colors["text"]};
    font-size: 20px;
    font-weight: 900;
}}

QLabel#graphsHeaderSubtitle {{
    color: {colors["muted"]};
    font-size: 12px;
}}

QPushButton[graphTab="true"] {{
    border: 1px solid {colors["border"]};
    border-radius: 8px;
    padding: 6px 16px;
    font-weight: 700;
    font-size: 12px;
    background: {colors["raised"]};
    color: {colors["muted"]};
}}

QPushButton[graphTab="true"]:checked {{
    background: {colors["panel"]};
    border-color: {active_border};
    color: {colors["text"]};
}}

QPushButton[historyBtn="true"] {{
    border: 1px solid {colors["border"]};
    border-radius: 8px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
    background: {colors["raised"]};
    color: {colors["muted"]};
}}

QPushButton[historyBtn="true"]:checked {{
    background: {colors["panel"]};
    border-color: {active_border};
    color: {colors["text"]};
}}

QFrame#graphsDrawer {{
    background: {colors["raised"]};
    border: 1px solid {colors["border"]};
    border-radius: 14px;
}}

QFrame#graphsStatsRow {{
    background: transparent;
}}

QLabel#graphsStatsLabel {{
    color: {colors["muted"]};
    font-size: 11px;
    font-weight: 700;
}}

QFrame#graphsLegendBar {{
    background: {colors["panel"]};
    border: 1px solid {colors["border"]};
    border-radius: 12px;
    min-height: 32px;
}}

QFrame#graphsControlsRow {{
    background: transparent;
}}
"""


def main_window_stylesheet(palette: QPalette) -> str:
    """Return palette-aware tab styling for the desktop shell."""
    colors = desktop_colors(palette)
    selected_background = colors["panel"]
    hover_background = _hex(
        _mix(QColor(colors["raised"]), QColor(colors["accent"]), 0.12)
    )
    border_color = colors["border"]
    selected_border = colors["accent"]
    muted = colors["muted"]
    return f"""
QMainWindow#mainWindow {{
    background: {colors["window"]};
    color: {colors["text"]};
}}

QTabWidget#mainTabs::pane {{
    border: 1px solid {border_color};
    border-radius: 18px;
    top: -1px;
    background: {colors["window"]};
}}

QTabBar::tab {{
    background: {colors["raised"]};
    color: {muted};
    border: 1px solid transparent;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    padding: 12px 22px;
    margin-right: 6px;
    font-size: 14px;
    font-weight: 700;
    min-width: 130px;
}}

QTabBar::tab:selected {{
    color: {colors["text"]};
    background: {selected_background};
    border-color: {selected_border};
}}

QTabBar::tab:hover:!selected {{
    background: {hover_background};
    color: {colors["text"]};
}}

QWidget#dashboardStatusCorner {{
    background: transparent;
}}

QStatusBar {{
    background: {colors["window"]};
    color: {muted};
}}
"""


def management_page_stylesheet(palette: QPalette) -> str:
    """Return a shared stylesheet for the Config and Service management pages."""
    colors = desktop_colors(palette)
    hover_background = _hex(
        _mix(QColor(colors["raised"]), QColor(colors["accent"]), 0.12)
    )
    button_text = colors["text"]
    return f"""
QWidget#managementPageRoot {{
    background: {colors["window"]};
    color: {colors["text"]};
}}

QGroupBox {{
    border: 1px solid {colors["border"]};
    border-radius: 4px;
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
}}

QLabel[serviceSectionHeader="true"] {{
    color: {colors["muted"]};
    font-size: 11px;
    font-weight: 700;
}}

QLabel#serviceConnectionLabel {{
    color: {colors["muted"]};
    font-size: 12px;
}}

QLabel#serviceMessageLabel {{
    color: {colors["text"]};
    font-size: 12px;
    padding: 2px 8px;
}}

QFrame#serviceSidebar,
QFrame#serviceDiagnosticsPanel {{
    background: {colors["window"]};
    border: none;
}}

QFrame#serviceDivider {{
    background: {colors["border"]};
}}

QFrame[serviceCard="true"] {{
    background: {colors["raised"]};
    border: none;
}}

QFrame#serviceStatusBox {{
    background: {colors["raised"]};
    border: none;
}}

QFrame#serviceStatusDot {{
    border-radius: 10px;
    background: {colors["muted"]};
}}

QFrame#serviceStatusDot[status="running"] {{
    background: #22c55e;
}}

QFrame#serviceStatusDot[status="stopped"] {{
    background: #ef4444;
}}

QLabel#servicePidLabel {{
    color: {colors["muted"]};
    font-size: 11px;
}}

QLabel#detailValue {{
    color: {colors["text"]};
    font-size: 11px;
    font-weight: 600;
}}

QCheckBox#traySwitch {{
    spacing: 0;
}}

QCheckBox#traySwitch::indicator {{
    width: 36px;
    height: 18px;
    border-radius: 2px;
    background: {colors["raised"]};
    border: 1px solid {colors["border"]};
}}

QCheckBox#traySwitch::indicator:checked {{
    background: {colors["accent"]};
    border-color: {colors["accent"]};
}}

QFrame#serviceComponentCard {{
    background: {colors["raised"]};
    border: none;
}}

QFrame#serviceComponentCard[componentAccent="lhm"] QFrame#componentAccentBar {{
    background: #60a5fa;
}}

QFrame#serviceComponentCard[componentAccent="pawnio"] QFrame#componentAccentBar {{
    background: #a78bfa;
}}

QPushButton#serviceInstallLhmBtn,
QPushButton#serviceInstallPawnioBtn {{
    background: transparent;
    border: none;
    color: {colors["text"]};
    font-size: 14px;
    padding: 4px 8px;
}}

QPushButton#serviceInstallLhmBtn:hover,
QPushButton#serviceInstallPawnioBtn:hover {{
    color: {colors["accent"]};
}}

QLabel#serviceComponentTitle {{
    color: {colors["text"]};
    font-size: 12px;
    font-weight: 600;
    padding-left: 8px;
}}

QFrame#serviceComponentCard[componentAccent="pawnio"] QLabel#serviceComponentTitle {{
    color: {colors["text"]};
}}

QLabel#serviceComponentDetail {{
    color: {colors["muted"]};
    font-size: 11px;
}}

QLabel#serviceDiagnosticsTitle {{
    color: {colors["muted"]};
    font-size: 11px;
    font-weight: 700;
    padding-top: 8px;
}}

QSplitter::handle {{
    background: transparent;
    width: 0px;
}}

QPlainTextEdit#diagnosticsView {{
    background: {colors["base"]};
    border: none;
    font-family: Consolas, monospace;
    font-size: 11px;
}}

QFrame[liveValueCard="true"] {{
    background: {colors["panel"]};
    border: 1px solid {colors["border"]};
    border-radius: 12px;
}}

QLabel#liveValueTitle {{
    color: {colors["muted"]};
    font-size: 10px;
    font-weight: 700;
}}

QLabel#liveTempValue,
QLabel#liveFanValue {{
    color: {colors["text"]};
    font-size: 22px;
    font-weight: 900;
}}

QLabel#curvesMessageLabel,
QLabel#serviceMessageLabel {{
    border-radius: 12px;
    padding: 8px 10px;
    background: {colors["raised"]};
}}

QPushButton,
QComboBox,
QLineEdit,
QDoubleSpinBox,
QPlainTextEdit,
QTableWidget {{
    border: 1px solid {colors["border"]};
    border-radius: 12px;
    background: {colors["base"]};
    color: {colors["text"]};
}}

QPushButton {{
    background: {colors["panel"]};
    border: none;
    border-radius: 0;
    color: {button_text};
    padding: 8px 12px;
}}

QPushButton:hover {{
    background: {colors["raised"]};
}}

QPushButton:pressed {{
    background: {colors["accent"]};
    color: {colors["window"]};
}}

QComboBox,
QLineEdit,
QDoubleSpinBox {{
    padding: 6px 10px;
}}

QComboBox::drop-down {{
    border: 0;
    width: 22px;
}}

QTableWidget,
QPlainTextEdit {{
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

QFrame[accordionSection="true"] {{
    background: {colors["raised"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
}}

QToolButton[accordionHeader="true"] {{
    border: 0;
    background: transparent;
    padding: 10px 12px;
    color: {colors["text"]};
    font-size: 13px;
    font-weight: 800;
    text-align: left;
}}

QToolButton[accordionHeader="true"]:hover {{
    background: {hover_background};
}}

QLabel[accordionSummary="true"] {{
    color: {colors["muted"]};
    font-size: 11px;
    font-weight: 600;
}}

QWidget[accordionBody="true"] {{
    background: {colors["raised"]};
}}
"""


def flat_management_page_stylesheet(palette: QPalette) -> str:
    """Return a flat, borderless stylesheet for Config and Service pages."""
    colors = desktop_colors(palette)
    button_text = colors["text"]
    return f"""
QWidget#managementPageRoot {{
    background: {colors["window"]};
    color: {colors["text"]};
}}

QGroupBox {{
    border: none;
    border-radius: 0;
    margin-top: 0;
    padding-top: 0;
    background: {colors["raised"]};
    color: {colors["text"]};
    font-size: 15px;
    font-weight: 800;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
}}

QLabel[serviceSectionHeader="true"] {{
    color: {colors["muted"]};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
}}

QLabel#serviceConnectionLabel {{
    color: {colors["muted"]};
    font-size: 11px;
}}

QLabel#serviceMessageLabel {{
    color: {colors["text"]};
    font-size: 11px;
    padding: 2px 8px;
}}

QFrame#serviceSidebar,
QFrame#serviceDiagnosticsPanel {{
    background: {colors["window"]};
    border: none;
}}

QFrame#serviceDivider {{
    background: {colors["raised"]};
}}

QFrame[serviceCard="true"] {{
    background: {colors["raised"]};
    border: none;
}}

QFrame#serviceStatusBox {{
    background: {colors["raised"]};
    border: none;
}}

QFrame#serviceStatusDot {{
    border-radius: 0;
    background: {colors["muted"]};
}}

QFrame#serviceStatusDot[status="running"] {{
    background: #22c55e;
}}

QFrame#serviceStatusDot[status="stopped"] {{
    background: #ef4444;
}}

QLabel#servicePidLabel {{
    color: {colors["muted"]};
    font-size: 11px;
}}

QLabel#detailValue {{
    color: {colors["text"]};
    font-size: 11px;
    font-weight: 600;
}}

QCheckBox#traySwitch {{
    spacing: 0;
}}

QCheckBox#traySwitch::indicator {{
    width: 36px;
    height: 18px;
    border-radius: 0;
    background: {colors["raised"]};
    border: none;
}}

QCheckBox#traySwitch::indicator:checked {{
    background: {colors["accent"]};
}}

QFrame#serviceComponentCard {{
    background: {colors["raised"]};
    border: none;
}}

QFrame#serviceComponentCard[componentAccent="lhm"] QFrame#componentAccentBar {{
    background: #60a5fa;
}}

QFrame#serviceComponentCard[componentAccent="pawnio"] QFrame#componentAccentBar {{
    background: #a78bfa;
}}

QPushButton#serviceInstallLhmBtn,
QPushButton#serviceInstallPawnioBtn {{
    background: transparent;
    border: none;
    color: {colors["text"]};
    font-size: 14px;
    padding: 4px 8px;
}}

QPushButton#serviceInstallLhmBtn:hover,
QPushButton#serviceInstallPawnioBtn:hover {{
    color: {colors["accent"]};
}}

QLabel#serviceComponentTitle {{
    color: {colors["text"]};
    font-size: 12px;
    font-weight: 600;
    padding-left: 8px;
}}

QFrame#serviceComponentCard[componentAccent="pawnio"] QLabel#serviceComponentTitle {{
    color: {colors["text"]};
}}

QLabel#serviceComponentDetail {{
    color: {colors["muted"]};
    font-size: 11px;
}}

QLabel#serviceDiagnosticsTitle {{
    color: {colors["muted"]};
    font-size: 11px;
    font-weight: 700;
    padding-top: 8px;
}}

QSplitter::handle {{
    background: transparent;
    width: 0px;
}}

QPlainTextEdit#diagnosticsView {{
    background: {colors["base"]};
    border: none;
    font-family: Consolas, monospace;
    font-size: 11px;
}}

QFrame[liveValueCard="true"] {{
    background: {colors["raised"]};
    border: none;
}}

QLabel#liveValueTitle {{
    color: {colors["muted"]};
    font-size: 9px;
    font-weight: 700;
}}

QLabel#liveTempValue,
QLabel#liveFanValue {{
    color: {colors["text"]};
    font-size: 20px;
    font-weight: 900;
}}

QLabel#curvesMessageLabel,
QLabel#serviceMessageLabel {{
    border-radius: 0;
    padding: 8px 10px;
    background: {colors["raised"]};
}}

QPushButton,
QComboBox,
QLineEdit,
QDoubleSpinBox,
QPlainTextEdit,
QTableWidget {{
    border: none;
    border-radius: 0;
    background: {colors["base"]};
    color: {colors["text"]};
}}

QPushButton {{
    background: {colors["raised"]};
    border: none;
    border-radius: 0;
    color: {button_text};
    padding: 8px 16px;
}}

QPushButton:hover {{
    background: {colors["card"]};
}}

QPushButton:pressed {{
    background: {colors["accent"]};
    color: {colors["window"]};
}}

QPushButton#curveActionBtn {{
    background: {colors["card"]};
    border: none;
    border-radius: 0;
    color: {button_text};
    padding: 8px 16px;
}}

QPushButton#curveActionBtn:hover {{
    background: {colors["accent"]};
    color: {colors["window"]};
}}

QComboBox,
QLineEdit,
QDoubleSpinBox {{
    padding: 6px 10px;
    background: {colors["raised"]};
}}

QComboBox {{
    border: 1px solid {colors["border"]};
    background: {colors["base"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox::down-arrow {{
    image: none;
    width: 10px;
    height: 10px;
}}

QComboBox::down-arrow:after {{
    content: "▼";
    color: {colors["text"]};
    font-size: 10px;
    font-weight: 700;
}}

QComboBox:hover {{
    background: {colors["raised"]};
    border-color: {colors["accent"]};
}}

QComboBox::item:hover {{
    background: {colors["accent"]};
    color: {colors["window"]};
}}

QDoubleSpinBox {{
    padding-right: 2px;
}}

QDoubleSpinBox::up-button {{
    width: 16px;
}}

QDoubleSpinBox::down-button {{
    width: 16px;
}}

QDoubleSpinBox::up-arrow {{
    image: none;
    width: 8px;
    height: 8px;
}}

QDoubleSpinBox::up-arrow:after {{
    content: "▲";
    color: {colors["text"]};
    font-size: 8px;
}}

QDoubleSpinBox::down-arrow {{
    image: none;
    width: 8px;
    height: 8px;
}}

QDoubleSpinBox::down-arrow:after {{
    content: "▼";
    color: {colors["text"]};
    font-size: 8px;
}}

QTableWidget,
QPlainTextEdit {{
    gridline-color: {colors["border"]};
    background: {colors["raised"]};
}}

QHeaderView::section {{
    background: {colors["raised"]};
    color: {colors["text"]};
    border: 0;
    border-bottom: 1px solid {colors["border"]};
    padding: 8px;
    font-weight: 700;
}}

QFrame[accordionSection="true"] {{
    background: {colors["raised"]};
    border: none;
    border-radius: 0;
    max-width: 388px;
}}

QToolButton[accordionHeader="true"] {{
    border: 0;
    background: transparent;
    padding: 8px 0;
    color: {colors["text"]};
    font-size: 12px;
    font-weight: 700;
    text-align: left;
}}

QLabel[accordionSummary="true"] {{
    color: {colors["muted"]};
    font-size: 11px;
    font-weight: 600;
}}

QWidget[accordionBody="true"] {{
    background: {colors["raised"]};
}}

QWidget#accordionWidget {{
    background: transparent;
    max-width: 388px;
}}

QWidget#accordionScrollContent {{
    background: transparent;
    max-width: 400px;
}}

QWidget#curvesLeftColumn,
QWidget#curvesRightColumn {{
    background: {colors["window"]};
    border: none;
    max-width: 400px;
}}

QFrame#previewGroup {{
    background: {colors["raised"]};
    border: none;
    border-radius: 0;
}}
"""


def badge_stylesheet(tone: str, palette: QPalette) -> str:
    """Return a rounded badge stylesheet for a semantic tone."""
    colors = desktop_colors(palette)
    dark = is_dark_palette(palette)
    tone_map = {
        "neutral": (colors["raised"], colors["text"]),
        "info": ("#1e3a5f" if dark else "#e0e7f1", "#8eafd0" if dark else "#3b6fa0"),
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
        "padding: 2px 8px;"
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


def sidebar_stylesheet(palette: QPalette) -> str:
    """Return a palette-aware stylesheet for the shared sidebar."""
    colors = desktop_colors(palette)
    dark = is_dark_palette(palette)
    sidebar_bg = _hex(
        _mix(QColor(colors["window"]), QColor("#000000"), 0.15 if dark else 0.03)
    )
    return f"""
QFrame#sidebar {{
    background: {sidebar_bg};
    border-right: 1px solid {colors["border"]};
}}
QLabel#sidebarBrand {{
    font-size: 16px;
    font-weight: 800;
    color: {colors["text"]};
}}
QLabel#sidebarSubtitle {{
    font-size: 10px;
    color: {colors["muted"]};
}}
QPushButton[sidebarNav="true"] {{
    text-align: left;
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    color: {colors["muted"]};
    background: transparent;
}}
QPushButton[sidebarNav="true"]:checked {{
    background: rgba(37, 99, 235, 0.12);
    color: {colors["accent"]};
    font-weight: 700;
}}
QLabel#sidebarSeparator {{
    background: {colors["border"]};
    max-height: 1px;
}}
QLabel.sidebarMuted {{
    font-size: 10px;
    color: {colors["muted"]};
}}
QLabel.sidebarValue {{
    font-size: 11px;
    font-weight: 700;
    color: {colors["text"]};
}}
"""


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
