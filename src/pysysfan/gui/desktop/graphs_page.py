"""G5 Tabbed Focus graphs page for the PySide6 desktop GUI.

One large graph displayed at a time with Temperature / Fan RPM tabs,
history-window selectors, and an interactive legend bar for toggling
individual series visibility.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pysysfan.gui.desktop.data_provider import DashboardDataProvider
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

        # Build the layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(8)

        # --- top controls row ---
        self._controls_row = QFrame(self)
        self._controls_row.setObjectName("graphsControlsRow")
        controls_layout = QHBoxLayout(self._controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

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
            controls_layout.addWidget(btn)
            self._tab_buttons[tab_key] = btn
        self._tab_buttons[self._active_tab].setChecked(True)
        self._showgrid_applied = False

        controls_layout.addStretch()

        # History window buttons
        self._history_buttons: dict[int, QPushButton] = {}
        for label, seconds in DashboardDataProvider.HISTORY_WINDOWS.items():
            btn = QPushButton(label, self._controls_row)
            btn.setObjectName(f"historyBtn_{seconds}")
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setProperty("historyBtn", True)
            btn.clicked.connect(lambda checked, s=seconds: self._set_history_window(s))
            controls_layout.addWidget(btn)
            self._history_buttons[seconds] = btn
        # Default history is the provider's current window
        default_seconds = provider.history_seconds
        if default_seconds in self._history_buttons:
            self._history_buttons[default_seconds].setChecked(True)

        root_layout.addWidget(self._controls_row)

        # --- plot widget ---
        if pg is not None:
            self._plot_widget = DashboardPlotWidget(
                axisItems={"bottom": ElapsedSecondsAxis(orientation="bottom")},
            )
            self._plot_widget.setObjectName("graphsPlotWidget")
            self._plot_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            root_layout.addWidget(self._plot_widget, stretch=1)
        else:
            self._plot_widget = None
            placeholder = QLabel("pyqtgraph not available", self)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root_layout.addWidget(placeholder, stretch=1)

        # --- legend bar ---
        self._legend_frame = QFrame(self)
        self._legend_frame.setObjectName("graphsLegendBar")
        self._legend_layout = QHBoxLayout(self._legend_frame)
        self._legend_layout.setContentsMargins(4, 4, 4, 4)
        self._legend_layout.setSpacing(4)
        self._legend_layout.addStretch()
        self._legend_items: list[LegendItem] = []
        root_layout.addWidget(self._legend_frame)

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
            self._legend_layout.addWidget(item)
            self._legend_items.append(item)

        self._legend_layout.addStretch()

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

        # Axis labels (lightweight)
        plot_item = self._plot_widget.getPlotItem()
        if self._active_tab == "temperature":
            plot_item.setLabel("left", "\u00b0C")
        else:
            plot_item.setLabel("left", "RPM")
        plot_item.setLabel("bottom", "Elapsed (s)")

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _current_catalog(self) -> dict[str, str]:
        if self._active_tab == "temperature":
            return self._provider.build_temperature_catalog()
        return self._provider.build_fan_rpm_catalog()

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
