"""G5 Tabbed Focus graphs page for the PySide6 desktop GUI.

One large graph displayed at a time with Temperature / Fan RPM tabs,
history-window selectors, and an interactive legend bar for toggling
individual series visibility.
"""

from __future__ import annotations

from math import ceil
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pysysfan.gui.desktop.data_provider import DashboardDataProvider
from pysysfan.gui.desktop.sidebar import SidebarWidget
from pysysfan.gui.desktop.theme import (
    desktop_colors,
    graphs_page_stylesheet,
    plot_theme,
)

try:  # pragma: no cover - optional GUI dependency
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional GUI dependency
    pg = None

from pysysfan.gui.desktop.plotting import DashboardPlotWidget, ElapsedSecondsAxis


# ------------------------------------------------------------------
# Legend item widget
# ------------------------------------------------------------------


class LegendItem(QWidget):
    """Clickable legend entry that toggles series visibility."""

    toggled = Signal(str, bool)  # (series_id, now_visible)

    def __init__(
        self,
        series_id: str,
        color: str,
        label: str,
        visible: bool = True,
        muted_color: str = "#4b5563",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.series_id = series_id
        self._color = color
        self._visible = visible
        self._muted_color = muted_color
        self.setObjectName("legendItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        self.color_label = QLabel(self)
        self.color_label.setObjectName("legendColor")
        self.color_label.setFixedWidth(16)
        self.color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text_label = QLabel(label, self)
        self.text_label.setObjectName("legendText")

        layout.addWidget(self.color_label)
        layout.addWidget(self.text_label)

        self._apply_visual()

    @property
    def visible(self) -> bool:
        return self._visible

    def set_visible_state(self, visible: bool) -> None:
        """Update the visual state without emitting a signal."""
        self._visible = visible
        self._apply_visual()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._visible = not self._visible
        self._apply_visual()
        self.toggled.emit(self.series_id, self._visible)

    def _apply_visual(self) -> None:
        if self._visible:
            self.color_label.setText("\u25cf")
            self.color_label.setStyleSheet(f"color: {self._color}; font-size: 14px;")
            self.text_label.setStyleSheet("")
        else:
            self.color_label.setText("\u25cb")
            self.color_label.setStyleSheet(f"color: {self._color}; font-size: 14px;")
            self.text_label.setStyleSheet(f"color: {self._muted_color};")


# ------------------------------------------------------------------
# Graphs page
# ------------------------------------------------------------------


class GraphsPage(QWidget):
    """G5 Tabbed Focus graphs page: one large graph with tab switching."""

    _GRAPH_TABS = ("temperature", "fan_rpm")
    _DEFAULT_TAB = "temperature"

    def __init__(
        self,
        provider: DashboardDataProvider,
        tab_switcher: Callable[[int], None] | None = None,
        include_sidebar: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("graphsRoot")
        self._provider = provider

        # Per-tab enabled series sets
        self._enabled_series: dict[str, set[str]] = {
            "temperature": set(),
            "fan_rpm": set(),
        }
        self._initialized_tabs: set[str] = set()
        self._active_tab: str = self._DEFAULT_TAB
        self._applying_theme: bool = False
        self._hover_point: tuple[float, float] | None = None
        self._legend_columns = 4
        self._hover_marker_item = None

        # Build the outer layout: sidebar + main content
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # -- Sidebar ---
        self.sidebar: SidebarWidget | None = None
        if include_sidebar:
            self.sidebar = SidebarWidget(provider=provider, active_tab=1, parent=self)
            if tab_switcher is not None:
                self.sidebar.tabRequested.connect(tab_switcher)
            outer_layout.addWidget(self.sidebar)

        # -- Main content ---
        main_area = QWidget(self)
        main_area.setObjectName("graphsMainArea")
        root_layout = QVBoxLayout(main_area)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(10)
        outer_layout.addWidget(main_area, stretch=1)

        self._header_frame = QFrame(self)
        self._header_frame.setObjectName("graphsHeader")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        header_title = QLabel("SYSTEM TELEMETRY", self._header_frame)
        header_title.setObjectName("graphsHeaderTitle")
        header_layout.addWidget(header_title)

        root_layout.addWidget(self._header_frame)

        # --- top controls row ---
        self._controls_row = QFrame(self)
        self._controls_row.setObjectName("graphsControlsRow")
        controls_layout = QVBoxLayout(self._controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self._tab_row = QWidget(self._controls_row)
        self._tab_row.setObjectName("graphsTabRow")
        tab_row_layout = QHBoxLayout(self._tab_row)
        tab_row_layout.setContentsMargins(0, 0, 0, 0)
        tab_row_layout.setSpacing(8)

        self._tab_buttons: dict[str, QPushButton] = {}
        for tab_key, tab_label in (
            ("temperature", "Temperature"),
            ("fan_rpm", "Fan RPM"),
        ):
            btn = QPushButton(tab_label, self._controls_row)
            btn.setObjectName(f"graphTab_{tab_key}")
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setProperty("graphTab", True)
            btn.clicked.connect(lambda checked, key=tab_key: self._switch_tab(key))
            tab_row_layout.addWidget(btn)
            self._tab_buttons[tab_key] = btn
        self._tab_buttons[self._active_tab].setChecked(True)
        self._showgrid_applied = False

        tab_row_layout.addStretch()

        self._history_row = QWidget(self._controls_row)
        self._history_row.setObjectName("graphsHistoryRow")
        history_row_layout = QHBoxLayout(self._history_row)
        history_row_layout.setContentsMargins(0, 0, 0, 0)
        history_row_layout.setSpacing(8)

        # History window buttons
        self._history_buttons: dict[int, QPushButton] = {}
        for label, seconds in DashboardDataProvider.HISTORY_WINDOWS.items():
            btn = QPushButton(label, self._controls_row)
            btn.setObjectName(f"historyBtn_{seconds}")
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setProperty("historyBtn", True)
            btn.clicked.connect(lambda checked, s=seconds: self._set_history_window(s))
            history_row_layout.addWidget(btn)
            self._history_buttons[seconds] = btn
        history_row_layout.addStretch()

        controls_layout.addWidget(self._tab_row)
        controls_layout.addWidget(self._history_row)
        # Default history is the provider's current window
        default_seconds = provider.history_seconds
        if default_seconds in self._history_buttons:
            self._history_buttons[default_seconds].setChecked(True)

        # --- plot widget ---
        if pg is not None:
            self._plot_widget = DashboardPlotWidget(
                axisItems={"bottom": ElapsedSecondsAxis(orientation="bottom")},
            )
            self._plot_widget.setObjectName("graphsPlotWidget")
            self._plot_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._hover_marker_item = pg.ScatterPlotItem(pxMode=True)
            self._hover_marker_item.setZValue(1000)
            self._plot_widget.addItem(self._hover_marker_item)
            self._plot_widget.hoverChanged.connect(self._handle_plot_hover_changed)
            root_layout.addWidget(self._plot_widget, stretch=1)
        else:
            self._plot_widget = None
            self._hover_marker_item = None
            placeholder = QLabel("pyqtgraph not available", self)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root_layout.addWidget(placeholder, stretch=1)

        # --- bottom drawer ---
        self._drawer_frame = QFrame(self)
        self._drawer_frame.setObjectName("graphsDrawer")
        drawer_layout = QVBoxLayout(self._drawer_frame)
        drawer_layout.setContentsMargins(12, 12, 12, 12)
        drawer_layout.setSpacing(8)

        drawer_layout.addWidget(self._controls_row)

        self._stats_row = QFrame(self._drawer_frame)
        self._stats_row.setObjectName("graphsStatsRow")
        stats_layout = QHBoxLayout(self._stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)
        self._visible_count_label = QLabel("0 visible", self._stats_row)
        self._visible_count_label.setObjectName("graphsStatsLabel")
        self._range_label = QLabel("Window 60 s", self._stats_row)
        self._range_label.setObjectName("graphsStatsLabel")
        stats_layout.addWidget(self._visible_count_label)
        stats_layout.addWidget(self._range_label)
        stats_layout.addStretch(1)
        drawer_layout.addWidget(self._stats_row)

        self._hover_row = QFrame(self._drawer_frame)
        self._hover_row.setObjectName("graphsHoverRow")
        hover_layout = QHBoxLayout(self._hover_row)
        hover_layout.setContentsMargins(0, 0, 0, 0)
        hover_layout.setSpacing(0)
        self._default_hover_text = (
            "Hover a visible line to inspect the values at that point in time."
        )
        self._hover_label = QLabel(self._default_hover_text, self._hover_row)
        self._hover_label.setObjectName("graphsHoverLabel")
        self._hover_label.setWordWrap(True)
        hover_layout.addWidget(self._hover_label, 1)
        drawer_layout.addWidget(self._hover_row)

        # --- legend bar ---
        self._legend_frame = QFrame(self)
        self._legend_frame.setObjectName("graphsLegendBar")
        self._legend_layout = QGridLayout(self._legend_frame)
        self._legend_layout.setContentsMargins(4, 4, 4, 4)
        self._legend_layout.setHorizontalSpacing(4)
        self._legend_layout.setVerticalSpacing(4)
        self._legend_items: list[LegendItem] = []
        drawer_layout.addWidget(self._legend_frame)

        root_layout.addWidget(self._drawer_frame)

        # Connect provider signals
        self._provider.historyUpdated.connect(self._refresh_plot)
        self._provider.stateUpdated.connect(self._on_state_updated)

        self._apply_theme()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def active_tab(self) -> str:
        return self._active_tab

    @property
    def enabled_series(self) -> dict[str, set[str]]:
        return self._enabled_series

    # ------------------------------------------------------------------
    # Show / hide lifecycle
    # ------------------------------------------------------------------

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self._apply_theme()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh_plot()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def _switch_tab(self, tab_key: str) -> None:
        if tab_key == self._active_tab:
            self._tab_buttons[tab_key].setChecked(True)
            return
        self._active_tab = tab_key
        for key, btn in self._tab_buttons.items():
            btn.setChecked(key == tab_key)
        if self._plot_widget is not None:
            self._plot_widget.clear_all_series()
        self._rebuild_legend()
        self._refresh_plot()

    # ------------------------------------------------------------------
    # History window
    # ------------------------------------------------------------------

    def _set_history_window(self, seconds: int) -> None:
        for s, btn in self._history_buttons.items():
            btn.setChecked(s == seconds)
        self._provider.set_history_window(seconds)

    # ------------------------------------------------------------------
    # State updated handler
    # ------------------------------------------------------------------

    def _on_state_updated(self, state: object) -> None:
        self._rebuild_legend()
        self._refresh_plot()

    # ------------------------------------------------------------------
    # Legend management
    # ------------------------------------------------------------------

    def _rebuild_legend(self) -> None:
        """Rebuild the legend bar for the active tab."""
        for item in self._legend_items:
            self._legend_layout.removeWidget(item)
            item.deleteLater()
        self._legend_items.clear()

        # Remove remaining stretch spacers
        while self._legend_layout.count():
            spacer = self._legend_layout.takeAt(0)
            if spacer.widget():
                spacer.widget().deleteLater()

        catalog = self._current_catalog()
        colors = self._series_colors()
        muted_color = desktop_colors(self.palette())["muted"]
        enabled = self._enabled_series[self._active_tab]

        # Initialize default selection on first data for this tab
        if self._active_tab not in self._initialized_tabs and catalog:
            self._initialize_default_selection(catalog)

        enabled = self._enabled_series[self._active_tab]
        if not catalog:
            return

        rows = max(1, ceil(len(catalog) / self._legend_columns))

        for idx, (series_id, label) in enumerate(catalog.items()):
            color = colors[idx % len(colors)] if colors else "#888888"
            is_visible = series_id in enabled
            item = LegendItem(
                series_id=series_id,
                color=color,
                label=label,
                visible=is_visible,
                muted_color=muted_color,
                parent=self._legend_frame,
            )
            item.toggled.connect(self._on_legend_toggled)
            row = idx % rows
            column = idx // rows
            self._legend_layout.addWidget(item, row, column)
            self._legend_items.append(item)

    def _initialize_default_selection(self, catalog: dict[str, str]) -> None:
        """Set initial enabled series for the active tab."""
        tab = self._active_tab
        keys = list(catalog.keys())

        if tab == "temperature":
            self._enabled_series[tab] = set(keys[:5])
        elif tab == "fan_rpm":
            group_keys = [k for k in keys if k.startswith("group::")]
            if group_keys:
                self._enabled_series[tab] = set(group_keys)
            else:
                self._enabled_series[tab] = set(keys[:3])

        self._initialized_tabs.add(tab)

    def _on_legend_toggled(self, series_id: str, now_visible: bool) -> None:
        if now_visible:
            self._enabled_series[self._active_tab].add(series_id)
        else:
            self._enabled_series[self._active_tab].discard(series_id)
        self._refresh_plot()

    # ------------------------------------------------------------------
    # Plot rendering
    # ------------------------------------------------------------------

    def _refresh_plot(self) -> None:
        """Redraw the graph with current tab's enabled series."""
        if self._plot_widget is None or pg is None:
            return

        catalog = self._current_catalog()
        history = self._current_history()
        enabled = self._enabled_series.get(self._active_tab, set())
        colors = self._series_colors()
        catalog_keys = list(catalog.keys())

        # Find latest timestamp across all enabled series
        latest_ts = 0.0
        for sid in enabled:
            series_data = self._resolve_series_data(sid, history)
            if series_data:
                latest_ts = max(latest_ts, max(t for t, _ in series_data))

        if latest_ts == 0.0:
            self._plot_widget.remove_stale_series(set())
            self._update_drawer_stats(0, len(catalog))
            self._clear_hover_summary()
            return

        active_ids: set[str] = set()
        for sid in enabled:
            series_data = self._resolve_series_data(sid, history)
            if not series_data:
                continue
            idx = catalog_keys.index(sid) if sid in catalog_keys else 0
            color = colors[idx % len(colors)] if colors else "#888888"
            x_vals = [t - latest_ts for t, _ in series_data]
            y_vals = [v for _, v in series_data]
            pen = pg.mkPen(color=color, width=2.5)
            self._plot_widget.update_series(sid, x_vals, y_vals, pen)
            active_ids.add(sid)

        self._plot_widget.remove_stale_series(active_ids)
        self._update_drawer_stats(len(active_ids), len(catalog))

        # Axis labels (lightweight)
        plot_item = self._plot_widget.getPlotItem()
        if self._active_tab == "temperature":
            plot_item.setLabel("left", "\u00b0C")
        else:
            plot_item.setLabel("left", "RPM")
        plot_item.setLabel("bottom", "Elapsed (s)")

        if self._hover_point is not None:
            self._update_hover_summary(self._hover_point)
        else:
            self._clear_hover_summary()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _current_catalog(self) -> dict[str, str]:
        if self._active_tab == "temperature":
            catalog = self._provider.build_temperature_catalog()
        else:
            catalog = self._provider.build_fan_rpm_catalog()
        return {
            series_id: label
            for series_id, label in catalog.items()
            if self._is_selectable_series_id(series_id)
        }

    def _current_history(self) -> dict:
        if self._active_tab == "temperature":
            return dict(self._provider.temperature_history)
        return dict(self._provider.fan_rpm_history)

    def _resolve_series_data(
        self, series_id: str, history: dict
    ) -> list[tuple[float, float]]:
        """Resolve a catalog series_id to history data points."""
        if series_id.startswith("group::"):
            group_name = series_id[len("group::") :]
            grouped = self._provider.build_grouped_history(
                self._provider.fan_rpm_history,
                self._provider.fan_groups,
            )
            return grouped.get(group_name, [])

        if series_id.startswith("series::"):
            raw_id = series_id[len("series::") :]
            deque_data = history.get(raw_id)
            if deque_data is not None:
                return list(deque_data)
            return []

        # Plain sensor ID (temperature)
        deque_data = history.get(series_id)
        if deque_data is not None:
            return list(deque_data)
        return []

    def _series_colors(self) -> list[str]:
        theme = plot_theme(self.palette())
        return theme.get("series", [])

    def _handle_plot_hover_changed(
        self, hover_point: tuple[float, float] | None
    ) -> None:
        if hover_point is None:
            self._hover_point = None
            self._clear_hover_summary()
            return

        self._hover_point = (float(hover_point[0]), float(hover_point[1]))
        self._update_hover_summary(self._hover_point)

    def _update_drawer_stats(self, visible_count: int, catalog_count: int) -> None:
        self._visible_count_label.setText(f"{visible_count} visible")
        self._range_label.setText(
            f"{catalog_count} selectable · window {self._provider.history_seconds} s"
        )

    def _update_hover_summary(
        self, hover_point: tuple[float, float] | None = None
    ) -> None:
        if self._plot_widget is None or pg is None:
            self._clear_hover_summary()
            return

        if hover_point is None:
            hover_point = self._hover_point
        if hover_point is None:
            self._clear_hover_summary()
            return

        x_value = float(hover_point[0])
        catalog = self._current_catalog()
        history = self._current_history()
        enabled = self._enabled_series.get(self._active_tab, set())
        colors = self._series_colors()
        summary_lines = [f"Hover @ {abs(x_value):g} s ago"]
        marker_spots: list[dict[str, object]] = []
        unit = "°C" if self._active_tab == "temperature" else "RPM"

        for idx, (series_id, label) in enumerate(catalog.items()):
            if series_id not in enabled:
                continue

            series_data = self._resolve_series_data(series_id, history)
            sample = self._sample_series_value(series_data, x_value)
            if sample is None:
                continue

            sample_x, sample_y = sample
            summary_lines.append(f"{label}: {format(sample_y, 'g')} {unit}")
            color = colors[idx % len(colors)] if colors else "#888888"
            marker_spots.append(
                {
                    "pos": (sample_x, sample_y),
                    "size": 11,
                    "brush": pg.mkBrush(color),
                    "pen": pg.mkPen(color, width=2),
                }
            )

        if len(summary_lines) == 1:
            self._clear_hover_summary()
            return

        self._hover_label.setText("\n".join(summary_lines))
        self._set_hover_markers(marker_spots)

    def _clear_hover_summary(self) -> None:
        self._hover_label.setText(self._default_hover_text)
        self._set_hover_markers([])

    def _set_hover_markers(self, marker_spots: list[dict[str, object]]) -> None:
        if self._hover_marker_item is None or pg is None:
            return

        self._hover_marker_item.setData(marker_spots)
        self._hover_marker_item.setVisible(bool(marker_spots))

    @staticmethod
    def _sample_series_value(
        series_data: list[tuple[float, float]], x_value: float
    ) -> tuple[float, float] | None:
        if not series_data:
            return None

        if len(series_data) == 1:
            sample_x, sample_y = series_data[0]
            return (sample_x, sample_y)

        first_x, _ = series_data[0]
        last_x, _ = series_data[-1]
        if x_value < first_x or x_value > last_x:
            return None

        previous_x, previous_y = series_data[0]
        for current_x, current_y in series_data[1:]:
            if x_value > current_x:
                previous_x, previous_y = current_x, current_y
                continue

            if current_x == previous_x:
                return (current_x, current_y)

            ratio = (x_value - previous_x) / (current_x - previous_x)
            sample_y = previous_y + (current_y - previous_y) * ratio
            return (x_value, sample_y)

        return (last_x, series_data[-1][1])

    @staticmethod
    def _is_selectable_series_id(series_id: str) -> bool:
        blocked_prefixes = ("const::", "min::", "max::", "marker::")
        return not series_id.startswith(blocked_prefixes)

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def _apply_plot_theme(self) -> None:
        """Apply theme to the plot widget — called once, not per refresh."""
        if self._plot_widget is None or pg is None:
            return
        theme = plot_theme(self.palette())
        self._plot_widget.setBackground(theme["background"])
        plot_item = self._plot_widget.getPlotItem()
        for axis_name in ("left", "bottom"):
            plot_item.getAxis(axis_name).setTextPen(theme["foreground"])
            plot_item.getAxis(axis_name).setPen(theme["muted"])
        if not self._showgrid_applied:
            plot_item.showGrid(x=True, y=True, alpha=0.25)
            self._showgrid_applied = True

    def _apply_theme(self) -> None:
        """Apply palette-aware colors to controls and legend."""
        if self._applying_theme:
            return
        self._applying_theme = True
        self._apply_plot_theme()
        self.setStyleSheet(graphs_page_stylesheet(self.palette()))
        self._applying_theme = False
