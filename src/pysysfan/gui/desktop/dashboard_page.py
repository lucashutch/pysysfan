"""Dashboard page for the PySide6 desktop GUI — V2 row-based layout."""

from __future__ import annotations

import re
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pysysfan.config import Config, FanConfig
from pysysfan.gui.desktop.data_provider import DashboardDataProvider
from pysysfan.gui.desktop.sidebar import SidebarWidget
from pysysfan.gui.desktop.theme import (
    dashboard_page_stylesheet,
    message_stylesheet,
)
from pysysfan.state_file import DaemonStateFile

GROUP_ACCENT_COLORS = [
    "#5eb4ff",  # blue (primary)
    "#6ffb85",  # green (secondary)
    "#ffa84f",  # amber (tertiary)
    "#ff716c",  # red (error)
    "#a78bfa",  # purple
    "#22d3ee",  # cyan
    "#f472b6",  # pink
    "#c084fc",  # violet
]


class DashboardPage(QWidget):
    """Desktop dashboard backed by a :class:`DashboardDataProvider`."""

    def __init__(
        self,
        provider: DashboardDataProvider,
        tab_switcher: Callable[[int], None] | None = None,
        include_sidebar: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._provider = provider
        self._fan_rows: list[QFrame] = []
        self._applying_theme = False

        self.setObjectName("dashboardRoot")
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -- Sidebar -------------------------------------------------------
        self.sidebar: SidebarWidget | None = None
        if include_sidebar:
            self.sidebar = SidebarWidget(provider=provider, active_tab=0, parent=self)
            if tab_switcher is not None:
                self.sidebar.tabRequested.connect(tab_switcher)
            root_layout.addWidget(self.sidebar)

        # -- Main content area --------------------------------------------
        main_area = QWidget(self)
        main_area.setObjectName("dashboardMainArea")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        root_layout.addWidget(main_area, stretch=1)

        # -- Scroll area ---------------------------------------------------
        self.scroll_area = QScrollArea(main_area)
        self.scroll_area.setObjectName("dashboardScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(self.scroll_area)

        self.content = QWidget(self.scroll_area)
        self.content.setObjectName("dashboardContent")
        self.scroll_area.setWidget(self.content)

        self._content_layout = QVBoxLayout(self.content)
        self._content_layout.setContentsMargins(18, 18, 18, 18)
        self._content_layout.setSpacing(12)

        # -- Message label (offline / error) --------------------------------
        self.message_label = QLabel("", self.content)
        self.message_label.setObjectName("dashboardMessageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        self._content_layout.addWidget(self.message_label)

        # -- "Fan Groups" heading ------------------------------------------
        fan_groups_title = QLabel("Fan Groups", self.content)
        fan_groups_title.setProperty("sectionRole", "title")
        self._content_layout.addWidget(fan_groups_title)

        # -- Table header row ----------------------------------------------
        self.table_header = self._build_table_header()
        self._content_layout.addWidget(self.table_header)

        # -- Fan rows container --------------------------------------------
        self.fan_rows_container = QWidget(self.content)
        self.fan_rows_container.setObjectName("fanRowsContainer")
        self._fan_rows_layout = QVBoxLayout(self.fan_rows_container)
        self._fan_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._fan_rows_layout.setSpacing(4)
        self._content_layout.addWidget(self.fan_rows_container)

        self._content_layout.addStretch(1)

        # -- Connect provider signals --------------------------------------
        self._provider.stateUpdated.connect(self._update_from_state)
        self._provider.offlineDetected.connect(self._update_offline)

        # -- Initial theme -------------------------------------------------
        self._apply_theme()

    # Polling is owned by MainWindow (desktop-level visibility control).

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
        self.setStyleSheet(dashboard_page_stylesheet(self.palette()))
        self._applying_theme = False

    # ------------------------------------------------------------------
    # Service helper
    # ------------------------------------------------------------------
    def start_service(self) -> None:
        """Request startup of the configured service/task."""
        success, message = self._provider.start_service()
        self._show_message(message, is_error=not success)

    # ------------------------------------------------------------------
    # Table header
    # ------------------------------------------------------------------
    def _build_table_header(self) -> QFrame:
        header = QFrame(self.content)
        header.setObjectName("tableHeader")
        header.setFrameShape(QFrame.Shape.NoFrame)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 6, 12, 6)
        layout.setSpacing(0)

        columns = [
            ("", 15),  # accent bar + spacing
            ("GROUP", 140),
            ("CURVE", 96),
            ("TARGET", 70),
            ("ACTUAL", 70),
            ("RPM", 80),
            ("", 18),  # extra gap before sensors
            ("SENSOR", 0),
            ("TEMP (°C)", 96),
        ]
        for text, width in columns:
            label = QLabel(text, header)
            label.setProperty("cardTextRole", "eyebrow")
            if text in {"GROUP", "SENSOR", "TEMP (°C)"}:
                label.setAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
                )
            else:
                label.setAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
                )
            if width > 0:
                label.setFixedWidth(width)
            else:
                label.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Preferred,
                )
            layout.addWidget(label)
        return header

    # ------------------------------------------------------------------
    # Fan row builder
    # ------------------------------------------------------------------
    def _build_fan_row(
        self,
        group_name: str,
        fan_config: FanConfig,
        state: DaemonStateFile,
        color: str,
    ) -> QFrame:
        row = QFrame(self.content)
        row.setObjectName(f"{self._object_name_token(group_name)}Row")
        row.setProperty("cardRole", "fan-summary")
        row.setFrameShape(QFrame.Shape.NoFrame)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(0)
        row.setMinimumHeight(56)

        # Accent bar — flush left, full height
        accent = QFrame(row)
        accent.setFixedWidth(3)
        accent.setStyleSheet(f"background: {color}; border-radius: 0;")
        accent.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(accent)
        layout.addSpacing(12)

        # Group name
        live_fan = self._find_live_fan(state, fan_config)
        group_display = self._display_fan_name(group_name, fan_config, live_fan)
        group_tooltip = self._raw_fan_name(group_name, fan_config, live_fan)

        group_label = QLabel(group_display, row)
        group_label.setObjectName("fanRowGroup")
        group_label.setFixedWidth(140)
        group_label.setProperty("cardTextRole", "title")
        group_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        group_label.setToolTip(group_tooltip)
        layout.addWidget(group_label)

        # Curve badge — pill-shaped, tightly wrapped
        curve_container = QWidget(row)
        curve_container.setFixedWidth(96)
        curve_container_layout = QHBoxLayout(curve_container)
        curve_container_layout.setContentsMargins(0, 0, 0, 0)
        curve_container_layout.setSpacing(0)
        curve_label = QLabel(fan_config.curve or "—", curve_container)
        curve_label.setObjectName("fanRowCurve")
        curve_label.setProperty("cardTextRole", "chip")
        curve_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        curve_label.setFixedWidth(96)
        curve_label.setStyleSheet(
            self._curve_chip_stylesheet(
                color, accent_text=getattr(live_fan, "text_color", None) or color
            )
        )
        curve_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        curve_container_layout.addWidget(curve_label)
        layout.addWidget(curve_container)

        # Target %
        target_value = state.fan_targets.get(fan_config.fan_id)
        target_text = f"{target_value:.0f}%" if target_value is not None else "—"
        target_label = QLabel(target_text, row)
        target_label.setObjectName("fanRowTarget")
        target_label.setFixedWidth(70)
        target_label.setProperty("cardTextRole", "metricValue")
        target_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(target_label)

        # Actual %
        actual_pct = (
            getattr(live_fan, "current_control_pct", None) if live_fan else None
        )
        actual_text = f"{actual_pct:.0f}%" if actual_pct is not None else "—"
        actual_label = QLabel(actual_text, row)
        actual_label.setObjectName("fanRowActual")
        actual_label.setFixedWidth(70)
        actual_label.setProperty("cardTextRole", "accentValue")
        actual_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        actual_label.setStyleSheet(self._accent_value_stylesheet(color))
        layout.addWidget(actual_label)

        # RPM
        rpm = getattr(live_fan, "rpm", None) if live_fan else None
        rpm_text = f"{rpm:.0f} RPM" if rpm is not None else "—"
        rpm_label = QLabel(rpm_text, row)
        rpm_label.setObjectName("fanRowRpm")
        rpm_label.setFixedWidth(80)
        rpm_label.setProperty("cardTextRole", "metricValue")
        rpm_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(rpm_label)

        layout.addSpacing(18)

        # Sensors
        sensor_details = self._resolve_sensor_details(state, fan_config.temp_ids)
        sensor_names = QLabel(
            "  •  ".join(item["display_name"] for item in sensor_details), row
        )
        sensor_names.setObjectName("fanRowSensors")
        sensor_names.setProperty("cardTextRole", "body")
        sensor_names.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        sensor_names.setWordWrap(True)
        sensor_names.setToolTip("\n".join(item["raw_label"] for item in sensor_details))
        sensor_names.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(sensor_names)

        sensor_values = QLabel(
            "  •  ".join(item["value_text"] for item in sensor_details), row
        )
        sensor_values.setObjectName("fanRowSensorValues")
        sensor_values.setFixedWidth(96)
        sensor_values.setProperty("cardTextRole", "sensorValue")
        sensor_values.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        sensor_values.setToolTip(sensor_names.toolTip())
        layout.addWidget(sensor_values)

        return row

    # ------------------------------------------------------------------
    # State update (from provider signal)
    # ------------------------------------------------------------------
    def _update_from_state(self, state: DaemonStateFile) -> None:
        self._show_message("", is_error=False)
        active_config = self._provider.active_config

        # Fan rows
        self._rebuild_fan_rows(state, active_config)

    def _rebuild_fan_rows(
        self,
        state: DaemonStateFile,
        active_config: Config | None,
    ) -> None:
        while self._fan_rows_layout.count():
            item = self._fan_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._fan_rows.clear()

        if active_config is None or not active_config.fans:
            empty = QLabel(
                "No active fan mappings available yet.", self.fan_rows_container
            )
            empty.setObjectName("fanRowsEmpty")
            empty.setWordWrap(True)
            empty.setProperty("cardTextRole", "muted")
            self._fan_rows_layout.addWidget(empty)
            return

        for index, (fan_name, fan_config) in enumerate(
            sorted(active_config.fans.items())
        ):
            color = GROUP_ACCENT_COLORS[index % len(GROUP_ACCENT_COLORS)]
            row = self._build_fan_row(fan_name, fan_config, state, color)
            self._fan_rows.append(row)
            self._fan_rows_layout.addWidget(row)

    # ------------------------------------------------------------------
    # Offline handling (from provider signal)
    # ------------------------------------------------------------------
    def _update_offline(self, service_status: object | None) -> None:
        installed = bool(getattr(service_status, "task_installed", False))

        while self._fan_rows_layout.count():
            item = self._fan_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._fan_rows.clear()

        if installed:
            self._show_message(
                "Daemon state file not found. Start the service to resume monitoring.",
                is_error=True,
            )
        else:
            self._show_message(
                "Daemon state file not found. Install the service from the Service tab.",
                is_error=True,
            )

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Message display
    # ------------------------------------------------------------------
    def _show_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.message_label.clear()
            self.message_label.hide()
            return
        self.message_label.setStyleSheet(
            message_stylesheet(is_error=is_error, palette=self.palette())
        )
        self.message_label.setText(message)
        self.message_label.show()

    # ------------------------------------------------------------------
    # Helper: find live fan state for a fan config
    # ------------------------------------------------------------------
    def _find_live_fan(
        self,
        state: DaemonStateFile,
        fan_config: FanConfig,
    ) -> object | None:
        for fan in state.fan_speeds:
            if fan_config.fan_id in self._candidate_fan_ids(fan):
                return fan
        return None

    # ------------------------------------------------------------------
    # Helper: resolve sensor details with temperature values
    # ------------------------------------------------------------------
    def _resolve_sensor_details(
        self,
        state: DaemonStateFile,
        sensor_ids: list[str],
    ) -> list[dict[str, str]]:
        by_id = {sensor.identifier: sensor for sensor in state.temperatures}
        resolved: list[dict[str, str]] = []
        for sensor_id in sensor_ids:
            sensor = by_id.get(sensor_id)
            label = self._compact_identifier(sensor_id)
            raw_label = sensor_id
            value_text = "—"
            if sensor is not None:
                label = DashboardDataProvider._display_sensor_name(
                    str(sensor.hardware_name), str(sensor.sensor_name), sensor_id
                )
                raw_label = f"{sensor.hardware_name} / {sensor.sensor_name}"
                if sensor.value is not None:
                    value_text = f"{sensor.value:.0f}°C"
            resolved.append(
                {
                    "display_name": label,
                    "raw_label": raw_label,
                    "value_text": value_text,
                }
            )
        return resolved or [
            {
                "display_name": "No sensors configured",
                "raw_label": "No sensors configured",
                "value_text": "—",
            }
        ]

    # ------------------------------------------------------------------
    # Helper: sensor count
    # ------------------------------------------------------------------
    @staticmethod
    def _sensor_count(active_config: Config | None) -> int:
        if active_config is None:
            return 0
        sensor_ids = {
            sensor_id
            for fan in active_config.fans.values()
            for sensor_id in fan.temp_ids
        }
        return len(sensor_ids)

    # ------------------------------------------------------------------
    # Static / class helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _temperature_color(value: float) -> str:
        if value >= 80.0:
            return "#ef4444"
        if value >= 60.0:
            return "#f59e0b"
        return "#22c55e"

    @staticmethod
    def _display_group_name(group_name: str) -> str:
        acronyms = {"cpu", "gpu", "ram", "aio", "vrm"}
        parts = [part for part in group_name.replace("-", "_").split("_") if part]
        if not parts:
            return group_name
        rendered: list[str] = []
        for part in parts:
            lowered = part.lower()
            if lowered in acronyms:
                rendered.append(lowered.upper())
                continue
            rendered.append(part.capitalize())
        return " ".join(rendered)

    @classmethod
    def _display_fan_name(
        cls,
        group_name: str,
        fan_config: FanConfig,
        live_fan: object | None,
    ) -> str:
        raw_name = cls._raw_fan_name(group_name, fan_config, live_fan)
        return DashboardDataProvider._humanize_fan_label(
            raw_name or cls._display_group_name(group_name)
        )

    @staticmethod
    def _display_sensor_name(
        hardware_name: str, sensor_name: str, identifier: str
    ) -> str:
        return DashboardDataProvider._display_sensor_name(
            hardware_name,
            sensor_name,
            identifier,
        )

    @staticmethod
    def _humanize_fan_label(label: str) -> str:
        return DashboardDataProvider._humanize_fan_label(label)

    @staticmethod
    def _raw_fan_name(
        group_name: str,
        fan_config: FanConfig,
        live_fan: object | None,
    ) -> str:
        for candidate in (
            getattr(live_fan, "sensor_name", None),
            getattr(fan_config, "header_name", None),
            getattr(live_fan, "hardware_name", None),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return group_name

    @staticmethod
    def _curve_chip_stylesheet(color: str, accent_text: str | None = None) -> str:
        base = QColor(color)
        base.lighter(170)
        if accent_text is None:
            accent_text = color
        accent_rgb = QColor(accent_text)
        return (
            f"background-color: rgba({base.red()}, {base.green()}, {base.blue()}, 28);"
            f"color: {accent_rgb.name(QColor.NameFormat.HexRgb)};"
            "padding: 5px 5px;"
            "border-radius: 2px;"
            "margin-top: 15px;"
            "margin-bottom: 15px;"
        )

    @staticmethod
    def _accent_value_stylesheet(color: str) -> str:
        return f"color: {QColor(color).name(QColor.NameFormat.HexRgb)};"

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"

    @staticmethod
    def _candidate_fan_ids(live_fan: object) -> set[str]:
        candidates = {
            value
            for value in (
                getattr(live_fan, "control_identifier", None),
                getattr(live_fan, "identifier", None),
            )
            if isinstance(value, str) and value
        }
        identifier = getattr(live_fan, "identifier", None)
        if isinstance(identifier, str) and "/fan/" in identifier:
            candidates.add(identifier.replace("/fan/", "/control/"))
        if isinstance(identifier, str) and "/control/" in identifier:
            candidates.add(identifier.replace("/control/", "/fan/"))
        return candidates

    @staticmethod
    def _compact_identifier(identifier: str) -> str:
        trimmed = identifier.strip("/")
        if not trimmed:
            return identifier
        parts = trimmed.split("/")
        return " / ".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

    @staticmethod
    def _is_relevant_temperature(sensor: object) -> bool:
        combined = (
            f"{sensor.hardware_name} {sensor.sensor_name} {sensor.identifier}"
        ).lower()
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
        return not any(term in combined for term in blocked_terms)

    @staticmethod
    def _object_name_token(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip()
        if not cleaned:
            return "fanGroup"
        parts = cleaned.split()
        return parts[0].lower() + "".join(part.title() for part in parts[1:])
