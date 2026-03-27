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
    """Build a set of palette-aware surface and text colors.

    Uses fixed colour tokens from the dashboard.html design mockup
    to ensure visual consistency across light/dark system palettes.
    """
    return DesktopColors(
        window="#0e0e0e",  # surface - main background
        base="#131313",  # surface-container-low - input backgrounds
        text="#ffffff",  # on-surface - primary text
        muted="#adaaaa",  # on-surface-variant - secondary text
        border="#767575",  # outline - borders
        raised="#1a1a1a",  # surface-container - elevated surfaces
        panel="#20201f",  # surface-container-high - panel backgrounds
        card="#1a1a1a",  # surface-container - card backgrounds
        accent="#5eb4ff",  # primary - accent/selection
        graph="#131313",  # surface-container-low - graph background
        # Additional semantic colours from the design token set
        primary="#5eb4ff",
        secondary="#6ffb85",
        tertiary="#ffa84f",
        error="#ff716c",
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
    font-size: 1.5rem;
    font-weight: 900;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}}

QPushButton[graphTab="true"] {{
    border: none;
    padding: 6px 16px;
    font-weight: 700;
    font-size: 12px;
    background: transparent;
    color: {colors["muted"]};
}}

QPushButton[graphTab="true"]:checked {{
    background: {colors["accent"]};
    color: {colors["window"]};
}}

QPushButton[historyBtn="true"] {{
    border: none;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
    color: {colors["muted"]};
}}

QPushButton[historyBtn="true"]:checked {{
    background: {colors["accent"]};
    color: {colors["window"]};
}}

QFrame#graphsDrawer {{
    background: {colors["panel"]};
    border: none;
}}

QFrame#graphsStatsRow {{
    background: transparent;
}}

QLabel#graphsStatsLabel {{
    color: {colors["muted"]};
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}

QFrame#graphsLegendBar {{
    background: {colors["raised"]};
    border: none;
    min-height: 160px;
}}

QFrame#graphsControlsRow {{
    background: transparent;
}}

QLabel#graphsHoverLabel {{
    color: {colors["muted"]};
    font-size: 10px;
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
    background: {colors["panel"]};
    border: 1px solid {colors["border"]};
}}

QCheckBox#traySwitch::indicator:checked {{
    background: #22c55e;
    border-color: #22c55e;
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
    padding-top: 0px;
}}

QSplitter::handle {{
    background: transparent;
    width: 0px;
}}

    QTextEdit#diagnosticsView,
    QPlainTextEdit#diagnosticsView {{
    background: {colors["base"]};
    border: none;
    border-radius: 0px;
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

QLabel[accordionHeader="true"] {{
    border: 0;
    background: transparent;
    padding: 10px 12px;
    color: {colors["text"]};
    font-size: 13px;
    font-weight: 800;
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
    background: {colors["panel"]};
    border: 1px solid {colors["border"]};
}}

QCheckBox#traySwitch::indicator:checked {{
    background: #22c55e;
    border-color: #22c55e;
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
    font-size: 10px;
    font-weight: 700;
    padding-top: 0px;
    letter-spacing: 0.08em;
}}

QSplitter::handle {{
    background: transparent;
    width: 0px;
}}

    QTextEdit#diagnosticsView,
    QPlainTextEdit#diagnosticsView {{
    background: {colors["base"]};
    border: none;
    border-radius: 0px;
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
    max-width: 400px;
}}

QLabel[accordionHeader="true"] {{
    border: 0;
    background: transparent;
    padding: 8px 0;
    color: {colors["text"]};
    font-size: 12px;
    font-weight: 700;
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
    max-width: 400px;
}}

QWidget#accordionScrollContent {{
    background: transparent;
    max-width: 400px;
}}

QWidget#curvesLeftColumn {{
    background: {colors["window"]};
    border: none;
    max-width: 400px;
}}

QWidget#curvesRightColumn {{
    background: {colors["window"]};
    border: none;
}}

QFrame#previewGroup {{
    background: {colors["raised"]};
    border: none;
    border-radius: 0;
}}
"""


def badge_stylesheet(tone: str, palette: QPalette) -> str:
    """Return a rounded badge stylesheet for a semantic tone."""
    tone_map = {
        "neutral": ("#262626", "#adaaaa"),
        "info": ("#1a1a1a", "#5eb4ff"),
        "success": ("#1a1a1a", "#6ffb85"),
        "warning": ("#1a1a1a", "#ffa84f"),
        "critical": ("#1a1a1a", "#ff716c"),
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
    accent = "#ff716c" if is_error else "#6ffb85"
    return f"font-size: 12px;font-weight: 700;color: {accent};"


def sidebar_stylesheet(palette: QPalette) -> str:
    """Return a palette-aware stylesheet for the shared sidebar."""
    colors = desktop_colors(palette)
    return f"""
QFrame#sidebar {{
    background: #131313;
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
    background: rgba(94, 180, 255, 0.15);
    color: #5eb4ff;
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
    series = [
        "#60a5fa",  # blue
        "#34d399",  # green
        "#f59e0b",  # amber
        "#f87171",  # red
        "#a78bfa",  # purple
        "#22d3ee",  # cyan
        "#f472b6",  # pink
        "#c084fc",  # violet
    ]
    return {
        "background": colors["graph"],
        "foreground": colors["text"],
        "grid": colors["border"],
        "muted": colors["muted"],
        "series": series,
    }
