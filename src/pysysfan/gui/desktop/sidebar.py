"""Shared sidebar widget for Dashboard and Graphs pages."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pysysfan.gui.desktop.data_provider import DashboardDataProvider
from pysysfan.gui.desktop.theme import sidebar_stylesheet
from pysysfan.state_file import DaemonStateFile

_NAV_ITEMS = [
    (0, "Dashboard"),
    (1, "Graphs"),
    (2, "Config"),
    (3, "Service"),
]


class SidebarWidget(QFrame):
    """Shared sidebar for Dashboard and Graphs pages."""

    tabRequested = Signal(int)

    def __init__(
        self,
        provider: DashboardDataProvider,
        active_tab: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(250)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._provider = provider
        self._active_tab = active_tab
        self._applying_theme = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        # -- Brand ---
        brand = QLabel("PySysFan", self)
        brand.setObjectName("sidebarBrand")
        layout.addWidget(brand)

        subtitle = QLabel("Desktop Fan Controller", self)
        subtitle.setObjectName("sidebarSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # -- Navigation ---
        self._nav_buttons: dict[int, QPushButton] = {}
        for tab_index, label in _NAV_ITEMS:
            btn = QPushButton(label, self)
            btn.setProperty("sidebarNav", True)
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setChecked(tab_index == active_tab)
            btn.clicked.connect(
                lambda checked, idx=tab_index: self._on_nav_clicked(idx)
            )
            layout.addWidget(btn)
            self._nav_buttons[tab_index] = btn

        layout.addWidget(self._separator())

        # -- Status section ---
        self._status_dot = QLabel("● Running  —", self)
        self._status_dot.setObjectName("sidebarStatusLine")
        self._status_dot.setProperty("class", "sidebarValue")
        layout.addWidget(self._status_dot)

        self._profile_label = QLabel("Profile: —", self)
        self._profile_label.setProperty("class", "sidebarMuted")
        layout.addWidget(self._profile_label)

        self._poll_label = QLabel("Poll: —", self)
        self._poll_label.setProperty("class", "sidebarMuted")
        layout.addWidget(self._poll_label)

        layout.addWidget(self._separator())

        # -- Temperature gauges ---
        temp_row = QHBoxLayout()
        temp_row.setSpacing(12)

        self._cpu_temp = self._build_temp_gauge("CPU")
        self._gpu_temp = self._build_temp_gauge("GPU")
        temp_row.addWidget(self._cpu_temp)
        temp_row.addWidget(self._gpu_temp)
        layout.addLayout(temp_row)

        layout.addWidget(self._separator())

        # -- Max fan / Alerts ---
        self._max_fan_label = QLabel("Max Fan: —", self)
        self._max_fan_label.setProperty("class", "sidebarValue")
        layout.addWidget(self._max_fan_label)

        footer = QWidget(self)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)

        self._alerts_title = QLabel("Notifications", footer)
        self._alerts_title.setObjectName("sidebarNotificationsLabel")
        footer_layout.addWidget(self._alerts_title)

        self._alerts_label = QToolButton(footer)
        self._alerts_label.setObjectName("sidebarAlertsButton")
        self._alerts_label.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._alerts_label.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._alerts_menu = QMenu(self._alerts_label)
        self._alerts_label.setMenu(self._alerts_menu)
        footer_layout.addWidget(self._alerts_label)
        layout.addWidget(footer)

        layout.addStretch(1)

        # -- Connect signals ---
        self._provider.stateUpdated.connect(self._update_from_state)
        self._provider.offlineDetected.connect(self._update_offline)

        empty_action = QAction("No recent alerts", self._alerts_menu)
        empty_action.setEnabled(False)
        self._alerts_menu.addAction(empty_action)
        self._alerts_label.setText("⚠ 0")
        self._alerts_label.setToolTip("No recent alerts")

        self._apply_theme()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def set_active_tab(self, index: int) -> None:
        """Update the highlighted nav item."""
        self._active_tab = index
        for idx, btn in self._nav_buttons.items():
            btn.setChecked(idx == index)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self._apply_theme()

    def _apply_theme(self) -> None:
        if self._applying_theme:
            return
        self._applying_theme = True
        self.setStyleSheet(sidebar_stylesheet(self.palette()))
        self._applying_theme = False

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def _update_from_state(self, state: DaemonStateFile) -> None:
        # Status line
        uptime = self._format_uptime(state.uptime_seconds)
        indicator_color = "#22c55e" if not state.config_error else "#ef4444"
        muted_color = "#9ca3af"
        self._status_dot.setText(f"● Running  {uptime}")
        self._status_dot.setStyleSheet(
            f"color: {indicator_color}; font-size: 11px; font-weight: 700;"
        )

        # Profile + poll
        profile_name, _ = self._provider.load_profile_metadata(state)
        self._profile_label.setText(f"Profile: {profile_name}")
        self._poll_label.setText(f"Poll: {state.poll_interval:.1f}s")

        # Temperature gauges
        cpu_temp, gpu_temp = self._extract_cpu_gpu_temps(state)
        self._update_temp_gauge(self._cpu_temp, "CPU", cpu_temp)
        self._update_temp_gauge(self._gpu_temp, "GPU", gpu_temp)

        # Max fan
        fans_with_rpm = [f for f in state.fan_speeds if f.rpm is not None]
        if fans_with_rpm:
            fastest = max(fans_with_rpm, key=lambda f: f.rpm)
            self._max_fan_label.setText(f"Max Fan: {fastest.rpm:,.0f} RPM")
        else:
            self._max_fan_label.setText("Max Fan: —")

        # Alerts
        alert_count = len(state.recent_alerts)
        color = "#22c55e" if alert_count == 0 else "#ef4444"
        self._alerts_menu.clear()
        if alert_count == 0:
            empty_action = QAction("No recent alerts", self._alerts_menu)
            empty_action.setEnabled(False)
            self._alerts_menu.addAction(empty_action)
            self._alerts_label.setText("⚠ 0")
            self._alerts_label.setToolTip("No recent alerts")
        else:
            for alert in state.recent_alerts:
                action = QAction(alert.message, self._alerts_menu)
                self._alerts_menu.addAction(action)
            self._alerts_label.setText(f"⚠ {alert_count}")
            self._alerts_label.setToolTip("Recent alerts")
        self._alerts_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: 700;"
        )
        self._alerts_title.setStyleSheet(
            f"color: {muted_color}; font-size: 10px; font-weight: 700;"
        )

    def _update_offline(self, service_status: object | None) -> None:
        self._status_dot.setText("● Offline")
        self._status_dot.setStyleSheet(
            "color: #f59e0b; font-size: 11px; font-weight: 700;"
        )
        self._profile_label.setText("Profile: —")
        self._poll_label.setText("Poll: —")
        self._update_temp_gauge(self._cpu_temp, "CPU", None)
        self._update_temp_gauge(self._gpu_temp, "GPU", None)
        self._max_fan_label.setText("Max Fan: —")
        self._alerts_menu.clear()
        empty_action = QAction("No recent alerts", self._alerts_menu)
        empty_action.setEnabled(False)
        self._alerts_menu.addAction(empty_action)
        self._alerts_label.setText("⚠ 0")
        self._alerts_label.setToolTip("No recent alerts")
        self._alerts_label.setStyleSheet(
            "color: #22c55e; font-size: 11px; font-weight: 700;"
        )
        self._alerts_title.setStyleSheet(
            "color: #9ca3af; font-size: 10px; font-weight: 700;"
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_nav_clicked(self, index: int) -> None:
        self.set_active_tab(index)
        self.tabRequested.emit(index)

    def _separator(self) -> QLabel:
        sep = QLabel(self)
        sep.setObjectName("sidebarSeparator")
        sep.setFixedHeight(1)
        return sep

    def _build_temp_gauge(self, label: str) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(label, container)
        title.setProperty("class", "sidebarMuted")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        value = QLabel("—", container)
        value.setObjectName(f"sidebarTemp{label}")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(value)

        return container

    def _update_temp_gauge(
        self, gauge: QWidget, label: str, value: float | None
    ) -> None:
        value_label = gauge.findChild(QLabel, f"sidebarTemp{label}")
        if value_label is None:
            return
        if value is None:
            value_label.setText("—")
            value_label.setStyleSheet("font-size: 18px; font-weight: 800;")
        else:
            color = self._temperature_color(value)
            value_label.setText(f"{value:.0f}°")
            value_label.setStyleSheet(
                f"font-size: 18px; font-weight: 800; color: {color};"
            )

    @staticmethod
    def _extract_cpu_gpu_temps(
        state: DaemonStateFile,
    ) -> tuple[float | None, float | None]:
        """Find the hottest CPU and GPU temperatures from state."""
        blocked_terms = (
            "alarm",
            "limit",
            "critical",
            "warning",
            "threshold",
            "max",
            "tjmax",
            "tj max",
            "distance",
        )
        cpu_temps: list[float] = []
        gpu_temps: list[float] = []
        for sensor in state.temperatures:
            if sensor.value is None:
                continue
            if sensor.value > 105.0 or sensor.value == 0.0:
                continue
            combined = (
                f"{sensor.hardware_name} {sensor.sensor_name} {sensor.identifier}"
            ).lower()
            if any(term in combined for term in blocked_terms):
                continue
            hw_lower = sensor.hardware_name.lower()
            name_lower = sensor.sensor_name.lower()
            ident_lower = sensor.identifier.lower()
            is_cpu = (
                "cpu" in hw_lower
                or "cpu" in name_lower
                or "core" in name_lower
                or "package" in name_lower
                or "ccd" in name_lower
                or "/cpu" in ident_lower
            )
            is_gpu = (
                "gpu" in hw_lower
                or "gpu" in name_lower
                or "hotspot" in name_lower
                or "hot spot" in name_lower
                or "/gpu" in ident_lower
                or "nvidia" in hw_lower
                or "amd radeon" in hw_lower
            )
            if is_cpu:
                cpu_temps.append(sensor.value)
            elif is_gpu:
                gpu_temps.append(sensor.value)

        cpu = max(cpu_temps) if cpu_temps else None
        gpu = max(gpu_temps) if gpu_temps else None
        return cpu, gpu

    @staticmethod
    def _temperature_color(value: float) -> str:
        if value >= 80.0:
            return "#ef4444"
        if value >= 60.0:
            return "#f59e0b"
        return "#22c55e"

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"
