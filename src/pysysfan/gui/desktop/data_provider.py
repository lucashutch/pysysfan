"""Dashboard data provider — extracts polling, history, and label logic.

This module provides a ``DashboardDataProvider`` QObject that owns all data
management previously embedded in the monolithic ``DashboardPage``.  It reads
the daemon state file, maintains rolling history deques, resolves human-friendly
sensor labels, and emits signals that UI layers can subscribe to.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, Signal

from pysysfan.config import Config, FanConfig
from pysysfan.gui.desktop.local_backend import (
    read_daemon_history,
    read_daemon_state,
    run_service_command,
)
from pysysfan.history_file import DEFAULT_HISTORY_PATH, HistorySample
from pysysfan.platforms import windows_service
from pysysfan.profiles import ProfileManager
from pysysfan.state_file import DEFAULT_STATE_PATH, DaemonStateFile


class _HasSensorAttrs(Protocol):
    """Protocol for objects with sensor attributes."""

    hardware_name: str
    sensor_name: str
    identifier: str


class DashboardDataProvider(QObject):
    """Headless data provider backing the dashboard UI.

    Polls the daemon state file on a timer, maintains history deques, resolves
    friendly sensor/fan labels, and emits signals when data changes.  Contains
    no widget or layout code — only data logic.
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    stateUpdated = Signal(object)
    historyUpdated = Signal()
    offlineDetected = Signal(object)
    alertsChanged = Signal(list)

    # ------------------------------------------------------------------
    # Polling cadences
    # ------------------------------------------------------------------
    REFRESH_INTERVAL_MS = 1000
    IDLE_REFRESH_INTERVAL_MS = 3000
    OFFLINE_REFRESH_INTERVAL_MS = 5000

    # ------------------------------------------------------------------
    # History windows
    # ------------------------------------------------------------------
    HISTORY_WINDOWS: dict[str, int] = {
        "60 s": 60,
        "5 min": 300,
        "15 min": 900,
    }

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------
    def __init__(
        self,
        state_path: Path = DEFAULT_STATE_PATH,
        history_path: Path = DEFAULT_HISTORY_PATH,
        service_action_runner=None,
        service_status_getter=None,
        profile_manager: ProfileManager | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._state_path = Path(state_path)
        self._history_path = Path(history_path)
        self._service_action_runner = service_action_runner or run_service_command
        self._service_status_getter = (
            service_status_getter or windows_service.get_service_status
        )
        self._profile_manager = profile_manager or ProfileManager()

        # History
        self._history_seconds: int = self.HISTORY_WINDOWS["60 s"]
        self._temperature_history: dict[str, deque[tuple[float, float]]] = defaultdict(
            deque
        )
        self._fan_rpm_history: dict[str, deque[tuple[float, float]]] = defaultdict(
            deque
        )
        self._fan_target_history: dict[str, deque[tuple[float, float]]] = defaultdict(
            deque
        )

        # Labels / groups
        self._temperature_labels: dict[str, str] = {}
        self._fan_labels: dict[str, str] = {}
        self._target_labels: dict[str, str] = {}
        self._fan_groups: dict[str, str] = {}
        self._target_groups: dict[str, str] = {}

        # State tracking
        self._last_state_timestamp: float | None = None
        self._last_polled_state_timestamp: float | None = None
        self._daemon_indicator_tone: str = "warning"
        self._alerts_badge_tone: str = "neutral"
        self._recent_alerts: list[str] = []
        self._active_config: Config | None = None
        self._daemon_state: DaemonStateFile | None = None

        # Timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh_data)

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------
    @property
    def temperature_history(self) -> dict[str, deque[tuple[float, float]]]:
        return self._temperature_history

    @property
    def fan_rpm_history(self) -> dict[str, deque[tuple[float, float]]]:
        return self._fan_rpm_history

    @property
    def fan_target_history(self) -> dict[str, deque[tuple[float, float]]]:
        return self._fan_target_history

    @property
    def temperature_labels(self) -> dict[str, str]:
        return self._temperature_labels

    @property
    def fan_labels(self) -> dict[str, str]:
        return self._fan_labels

    @property
    def target_labels(self) -> dict[str, str]:
        return self._target_labels

    @property
    def fan_groups(self) -> dict[str, str]:
        return self._fan_groups

    @property
    def target_groups(self) -> dict[str, str]:
        return self._target_groups

    @property
    def active_config(self) -> Config | None:
        return self._active_config

    @property
    def daemon_state(self) -> DaemonStateFile | None:
        return self._daemon_state

    @property
    def recent_alerts(self) -> list[str]:
        return self._recent_alerts

    @property
    def history_seconds(self) -> int:
        return self._history_seconds

    @property
    def daemon_indicator_tone(self) -> str:
        return self._daemon_indicator_tone

    @property
    def alerts_badge_tone(self) -> str:
        return self._alerts_badge_tone

    # ------------------------------------------------------------------
    # Polling control
    # ------------------------------------------------------------------
    def start_polling(self) -> None:
        """Start the periodic refresh timer."""
        self.refresh_data()
        self._refresh_timer.start()

    def stop_polling(self) -> None:
        """Stop the periodic refresh timer."""
        self._refresh_timer.stop()

    def refresh_data(self) -> None:
        """Poll the daemon state file and update internal data."""
        try:
            service_status = self._service_status_getter()
        except Exception:
            service_status = None

        state = read_daemon_state(self._state_path)
        if state is None:
            self._set_refresh_interval(self.OFFLINE_REFRESH_INTERVAL_MS)
            self._last_polled_state_timestamp = None
            self._apply_offline_state(service_status)
            self.offlineDetected.emit(service_status)
            return

        # Keep redraw cadence stable while the daemon is running.
        # The daemon may skip rewriting `daemon_state.json` when its logical
        # state signature is unchanged, so using `state.timestamp` for cadence
        # causes sporadic UI stalls.
        if state.running:
            self._set_refresh_interval(self.REFRESH_INTERVAL_MS)
        else:
            self._set_refresh_interval(self.IDLE_REFRESH_INTERVAL_MS)

        self._last_polled_state_timestamp = state.timestamp

        self._daemon_state = state
        self._apply_summary(state)
        self._apply_alerts(state)
        self._record_live_labels(state)
        self._load_history(state)

        self.stateUpdated.emit(state)
        self.historyUpdated.emit()

    def set_history_window(self, seconds: int) -> None:
        """Change the history window and trim existing data."""
        self._history_seconds = seconds
        if self._last_state_timestamp is not None:
            self._trim_history(self._last_state_timestamp)
            self.historyUpdated.emit()

    def start_service(self) -> tuple[bool, str]:
        """Request startup of the configured service/task."""
        success, message = self._service_action_runner("start")
        self.refresh_data()
        return success, message

    # ------------------------------------------------------------------
    # Catalog builders (for graph series selection)
    # ------------------------------------------------------------------
    def build_temperature_catalog(self) -> dict[str, str]:
        """Return ``{sensor_id: display_label}`` for temperatures with data."""
        return {
            sensor_id: self._temperature_labels[sensor_id]
            for sensor_id, series in sorted(self._temperature_history.items())
            if series and sensor_id in self._temperature_labels
        }

    def build_fan_rpm_catalog(self) -> dict[str, str]:
        """Return grouped + individual fan RPM catalog entries."""
        return self._build_grouped_catalog(
            self._fan_rpm_history,
            self._fan_labels,
            self._fan_groups,
            singular_prefix="Fan",
        )

    def build_fan_target_catalog(self) -> dict[str, str]:
        """Return grouped + individual fan target catalog entries."""
        return self._build_grouped_catalog(
            self._fan_target_history,
            self._target_labels,
            self._target_groups,
            singular_prefix="Target",
        )

    def build_grouped_history(
        self,
        history_map: dict[str, deque[tuple[float, float]]],
        group_map: dict[str, str],
    ) -> dict[str, list[tuple[float, float]]]:
        """Aggregate per-series history into grouped averages."""
        grouped_points: dict[str, dict[float, list[float]]] = defaultdict(dict)
        for series_id, series in history_map.items():
            group = group_map.get(series_id)
            if not group:
                continue
            bucket = grouped_points.setdefault(group, {})
            for timestamp, value in series:
                bucket.setdefault(timestamp, []).append(value)

        return {
            group: [
                (timestamp, sum(values) / len(values))
                for timestamp, values in sorted(points.items())
            ]
            for group, points in grouped_points.items()
        }

    # ------------------------------------------------------------------
    # Internal: refresh interval
    # ------------------------------------------------------------------
    def _set_refresh_interval(self, interval_ms: int) -> None:
        if self._refresh_timer.interval() != interval_ms:
            self._refresh_timer.setInterval(interval_ms)

    # ------------------------------------------------------------------
    # Internal: offline handling
    # ------------------------------------------------------------------
    def _apply_offline_state(self, service_status: object | None) -> None:
        installed = bool(getattr(service_status, "task_installed", False))
        self._daemon_indicator_tone = "warning" if installed else "critical"
        self._active_config = None
        self._daemon_state = None
        self._last_state_timestamp = None
        self._temperature_history.clear()
        self._fan_rpm_history.clear()
        self._fan_target_history.clear()
        self._apply_alert_menu([])

    # ------------------------------------------------------------------
    # Internal: summary / config
    # ------------------------------------------------------------------
    def _apply_summary(self, state: DaemonStateFile) -> None:
        active_config = self._load_active_config(state)
        self._active_config = active_config
        self._daemon_indicator_tone = "critical" if state.config_error else "success"

    def _load_active_config(self, state: DaemonStateFile) -> Config | None:
        config_path = Path(state.config_path)
        if config_path.exists():
            try:
                return Config.load(config_path)
            except Exception:
                return None
        return None

    def load_profile_metadata(self, state: DaemonStateFile) -> tuple[str, str]:
        """Return ``(display_name, description)`` for the state's active profile."""
        try:
            profile = self._profile_manager.get_profile(state.active_profile)
        except Exception:
            return state.active_profile, ""

        display_name = profile.metadata.display_name or state.active_profile
        return display_name, profile.metadata.description

    # ------------------------------------------------------------------
    # Internal: alerts
    # ------------------------------------------------------------------
    def _apply_alerts(self, state: DaemonStateFile) -> None:
        labels = [
            f"{alert.sensor_id} [{alert.alert_type}] - {alert.message}"
            for alert in reversed(state.recent_alerts[-10:])
        ]
        self._apply_alert_menu(labels)

    def _apply_alert_menu(self, alert_lines: list[str]) -> None:
        self._recent_alerts = alert_lines
        if alert_lines:
            self._alerts_badge_tone = "critical"
        else:
            self._alerts_badge_tone = "neutral"
        self.alertsChanged.emit(alert_lines)

    # ------------------------------------------------------------------
    # Internal: labels / groups
    # ------------------------------------------------------------------
    def _record_live_labels(self, state: DaemonStateFile) -> None:
        self._fan_groups.clear()
        self._target_groups.clear()
        for sensor in state.temperatures:
            if not self._is_relevant_temperature(sensor):
                continue
            self._temperature_labels[sensor.identifier] = self._display_sensor_name(
                str(sensor.hardware_name),
                str(sensor.sensor_name),
                sensor.identifier,
            )

        for fan in state.fan_speeds:
            group_name, fan_config = self._resolve_live_fan_config(fan)
            if group_name is None:
                continue
            label = self._series_display_name(group_name, fan_config, fan)
            series_id = fan.control_identifier or fan.identifier
            self._fan_labels[series_id] = label
            self._fan_groups[series_id] = group_name
            self._target_labels[series_id] = label
            self._target_groups[series_id] = group_name

        if self._active_config is not None:
            for group_name, fan_config in sorted(self._active_config.fans.items()):
                label = self._series_display_name(group_name, fan_config, None)
                self._target_labels[fan_config.fan_id] = label
                self._target_groups[fan_config.fan_id] = group_name

        self._prune_unmapped_fan_history()

    # ------------------------------------------------------------------
    # Internal: history
    # ------------------------------------------------------------------
    def _load_history(self, state: DaemonStateFile) -> None:
        samples = read_daemon_history(self._history_path)
        if not samples:
            samples = [self._build_fallback_history_sample(state)]

        self._temperature_history.clear()
        self._fan_rpm_history.clear()
        self._fan_target_history.clear()

        latest_timestamp = state.timestamp
        for sample in samples:
            latest_timestamp = max(latest_timestamp, sample.timestamp)
            for sensor_id, value in sample.temperatures.items():
                self._temperature_history[sensor_id].append((sample.timestamp, value))
            for series_id, value in sample.fan_rpm.items():
                self._fan_rpm_history[series_id].append((sample.timestamp, value))
            for series_id, value in sample.fan_targets.items():
                self._fan_target_history[series_id].append((sample.timestamp, value))

        self._last_state_timestamp = latest_timestamp
        self._prune_unmapped_fan_history()
        self._trim_history(latest_timestamp)

    def _build_fallback_history_sample(self, state: DaemonStateFile) -> HistorySample:
        temperatures = {
            sensor.identifier: float(sensor.value)
            for sensor in state.temperatures
            if sensor.value is not None and self._is_relevant_temperature(sensor)
        }
        fan_rpm = {
            (fan.control_identifier or fan.identifier): float(fan.rpm)
            for fan in state.fan_speeds
            if fan.rpm is not None
        }
        fan_targets = {
            identifier: float(value) for identifier, value in state.fan_targets.items()
        }
        return HistorySample(
            timestamp=state.timestamp,
            temperatures=temperatures,
            fan_rpm=fan_rpm,
            fan_targets=fan_targets,
        )

    def _trim_history(self, latest_timestamp: float) -> None:
        cutoff = latest_timestamp - self._history_seconds
        for history_map in (
            self._temperature_history,
            self._fan_rpm_history,
            self._fan_target_history,
        ):
            for sensor_id in list(history_map.keys()):
                series = history_map[sensor_id]
                while series and series[0][0] < cutoff:
                    series.popleft()
                if not series:
                    del history_map[sensor_id]

    def _prune_unmapped_fan_history(self) -> None:
        mapped_fan_ids = set(self._fan_groups)
        mapped_target_ids = set(self._target_groups)
        for history_map, mapped_ids in (
            (self._fan_rpm_history, mapped_fan_ids),
            (self._fan_target_history, mapped_target_ids),
        ):
            for series_id in list(history_map.keys()):
                if series_id not in mapped_ids:
                    del history_map[series_id]

    # ------------------------------------------------------------------
    # Internal: fan config resolution helpers
    # ------------------------------------------------------------------
    def _resolve_live_fan_config(
        self,
        live_fan: object,
    ) -> tuple[str | None, FanConfig | None]:
        if self._active_config is None:
            return None, None

        candidate_ids = self._candidate_fan_ids(live_fan)
        for fan_name, fan_config in sorted(self._active_config.fans.items()):
            if fan_config.fan_id in candidate_ids:
                return fan_name, fan_config

        return None, None

    def _series_display_name(
        self,
        group_name: str,
        fan_config: FanConfig | None,
        live_fan: object | None,
    ) -> str:
        group_label = self._display_group_name(group_name)
        detail = ""
        if fan_config is not None and fan_config.header_name:
            detail = self._humanize_fan_label(fan_config.header_name)
        elif live_fan is not None:
            sensor_name = getattr(live_fan, "sensor_name", None)
            if sensor_name is not None:
                detail = self._humanize_fan_label(str(sensor_name))
            else:
                hardware_name = getattr(live_fan, "hardware_name", None)
                if hardware_name is not None:
                    detail = self._humanize_fan_label(str(hardware_name))
        if detail:
            if detail.strip().lower() == group_label.strip().lower():
                return group_label
            return f"{group_label} · {detail}"
        return group_label

    # ------------------------------------------------------------------
    # Internal: grouped catalog builder
    # ------------------------------------------------------------------
    def _build_grouped_catalog(
        self,
        history_map: dict[str, deque[tuple[float, float]]],
        labels: dict[str, str],
        group_map: dict[str, str],
        *,
        singular_prefix: str,
    ) -> dict[str, str]:
        catalog: dict[str, str] = {}
        groups = sorted({group for group in group_map.values() if group})
        for group in groups:
            catalog[f"group::{group}"] = self._display_group_name(group)
        for series_id, series in sorted(history_map.items()):
            if not series:
                continue
            catalog[f"series::{series_id}"] = (
                f"{singular_prefix} · {labels.get(series_id, series_id)}"
            )
        return catalog

    # ------------------------------------------------------------------
    # Static / class helpers
    # ------------------------------------------------------------------
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
    def _display_sensor_name(
        cls,
        hardware_name: str,
        sensor_name: str,
        identifier: str,
    ) -> str:
        """Return ``<model> <sensor_type>`` — e.g. ``Ryzen 7 7700X Core``."""
        hardware_key = cls._normalize_lookup_key(hardware_name)
        sensor_key = cls._normalize_lookup_key(sensor_name)
        identifier_key = cls._normalize_lookup_key(identifier)
        model = cls._trim_model_suffix(cls._trim_brand_prefix(hardware_name.strip()))

        # CPU package / overall temp
        if sensor_key in {"package", "package temp"}:
            if model:
                return f"{model} Package"
            return "CPU Package"

        # CPU core / Tctl / Tdie / CCD sensors
        if sensor_key in {"tctl", "tdie"} or sensor_key.startswith("core"):
            return cls._cpu_core_name(hardware_name, sensor_name, identifier)

        # AMD CCD temps (e.g. "CCD1 (Tdie)", "CCD2 (Tdie)")
        if sensor_key.startswith("ccd"):
            return cls._cpu_ccd_name(hardware_name, sensor_name)

        # RAM / DIMM
        if sensor_key.startswith("dimm") or "dimm" in sensor_key:
            return cls._ram_name(hardware_name, sensor_name)

        # Chipset / PCH
        if sensor_key in {"pch", "chipset"} or hardware_key == "pch":
            if model:
                return f"{model} Chipset"
            return "Chipset"

        # GPU Core / Edge / Hotspot
        if "gpu" in hardware_key and any(
            token in sensor_key for token in {"core", "edge", "hotspot"}
        ):
            return cls._gpu_core_name(hardware_name, sensor_name)

        # GPU VR / VRAM / VRM
        if "gpu" in hardware_key and any(
            token in sensor_key for token in {"vram", "vrm", "vrs", "vr soc", "vr"}
        ):
            return cls._gpu_vr_name(hardware_name, sensor_name)

        # Detect "Temperature #N" in the raw sensor name (# is lost in
        # the normalized key).
        _is_numbered_temp = bool(
            re.match(r"temperature\s*#\d+", sensor_name.strip(), re.IGNORECASE)
        )
        _is_composite_temp = "composite" in sensor_key and "temperature" in sensor_key

        # Motherboard sensor chips (Nuvoton, ITE, etc.) — route before SSD.
        _is_motherboard_hw = any(
            token in hardware_key
            for token in {"nuvoton", "motherboard", "ite ", "nct", "it87"}
        )
        if _is_motherboard_hw and (_is_numbered_temp or sensor_name.strip()):
            return cls._motherboard_temp_name(hardware_name, sensor_name, identifier)

        # SSD / NVMe — composite or numbered temperature
        if (
            "ssd" in hardware_key
            or "nvme" in hardware_key
            or "ssd" in identifier_key
            or _is_composite_temp
        ):
            return cls._ssd_temp_name(hardware_name, sensor_name, identifier)

        # Generic numbered temperature sensors not caught above
        if _is_numbered_temp:
            return cls._motherboard_temp_name(hardware_name, sensor_name, identifier)

        # Fallback: model + humanized sensor label
        if sensor_name.strip():
            tail = cls._sensor_tail(sensor_name)
            if model and tail:
                return f"{model} {tail}".strip()
            return tail or cls._compact_identifier(identifier)
        return cls._compact_identifier(identifier)

    @classmethod
    def _cpu_core_name(
        cls, hardware_name: str, sensor_name: str, identifier: str
    ) -> str:
        model = cls._trim_model_suffix(cls._trim_brand_prefix(hardware_name.strip()))
        sensor_tail = cls._cpu_sensor_tail(sensor_name)
        if model and sensor_tail:
            return f"{model} {sensor_tail}".strip()
        if model:
            return f"{model} Core"
        if sensor_tail:
            return sensor_tail
        return cls._compact_identifier(identifier)

    @classmethod
    def _cpu_ccd_name(cls, hardware_name: str, sensor_name: str) -> str:
        model = cls._trim_model_suffix(cls._trim_brand_prefix(hardware_name.strip()))
        # Extract CCD number, e.g. "CCD1 (Tdie)" → "CCD1"
        match = re.match(r"(CCD\s*\d+)", sensor_name.strip(), re.IGNORECASE)
        ccd_label = match.group(1).upper().replace(" ", "") if match else "CCD"
        if model:
            return f"{model} {ccd_label}"
        return f"CPU {ccd_label}"

    @classmethod
    def _cpu_sensor_tail(cls, sensor_name: str) -> str:
        """Return the short sensor qualifier for a CPU temp sensor."""
        lowered = sensor_name.strip().lower()
        if lowered in {"tctl", "tdie"}:
            return "Core"
        if lowered.startswith("core (") and "tctl/tdie" in lowered:
            return "Core"
        if lowered.startswith("core #"):
            # Individual core, e.g. "Core #3"
            num = sensor_name.strip()[5:].strip()
            return f"Core {num}".strip()
        if lowered == "core":
            return "Core"
        return cls._sensor_tail(sensor_name)

    @classmethod
    def _gpu_core_name(cls, hardware_name: str, sensor_name: str) -> str:
        model = cls._trim_model_suffix(cls._trim_brand_prefix(hardware_name.strip()))
        sensor_tail = cls._gpu_sensor_tail(sensor_name)
        if model and sensor_tail:
            return f"{model} {sensor_tail}".strip()
        if model:
            return f"{model} Core"
        return sensor_tail or "GPU Core"

    @classmethod
    def _gpu_vr_name(cls, hardware_name: str, sensor_name: str) -> str:
        model = cls._trim_model_suffix(cls._trim_brand_prefix(hardware_name.strip()))
        sensor_tail = cls._gpu_sensor_tail(sensor_name)
        if model and sensor_tail:
            return f"{model} {sensor_tail}".strip()
        if model:
            return f"{model} VR"
        return sensor_tail or "GPU VR"

    @classmethod
    def _gpu_sensor_tail(cls, sensor_name: str) -> str:
        """Return the short qualifier for a GPU sensor, stripping 'GPU' prefix."""
        lowered = sensor_name.strip().lower()
        # Strip leading "gpu" since the model already implies it.
        cleaned = re.sub(r"^gpu\s+", "", lowered).strip()
        if not cleaned:
            return "Core"
        return cls._humanize_words(cleaned)

    @classmethod
    def _ram_name(cls, hardware_name: str, sensor_name: str) -> str:
        model = cls._trim_model_suffix(cls._trim_brand_prefix(hardware_name.strip()))
        tail = cls._sensor_tail(sensor_name)
        if model and tail:
            return f"{model} {tail}".strip()
        if model:
            return f"{model} Temp"
        return tail or "RAM"

    @classmethod
    def _motherboard_temp_name(
        cls, hardware_name: str, sensor_name: str, identifier: str
    ) -> str:
        hardware_label = cls._trim_brand_prefix(hardware_name.strip())
        model = cls._trim_model_suffix(hardware_label)
        sensor_tail = cls._sensor_tail(sensor_name)
        hardware_key = cls._normalize_lookup_key(hardware_name)
        if "nuvoton" in hardware_key or "motherboard" in hardware_key:
            if sensor_tail:
                return f"Motherboard {sensor_tail}".strip()
        if model and sensor_tail:
            return f"{model} {sensor_tail}".strip()
        return sensor_tail or cls._compact_identifier(identifier)

    @classmethod
    def _ssd_temp_name(
        cls, hardware_name: str, sensor_name: str, identifier: str
    ) -> str:
        model = cls._trim_model_suffix(cls._trim_brand_prefix(hardware_name.strip()))
        sensor_key = cls._normalize_lookup_key(sensor_name)
        if model:
            if "composite" in sensor_key:
                return f"{model} Temp"
            tail = cls._sensor_tail(sensor_name)
            if tail:
                return f"{model} {tail}".strip()
            return f"{model} Temp"
        return cls._sensor_tail(sensor_name) or cls._compact_identifier(identifier)

    @classmethod
    def _sensor_tail(cls, label: str) -> str:
        normalized = label.strip()
        if not normalized:
            return ""
        replacements = {
            "tctl": "Core",
            "tdie": "Core",
            "temperature #1": "Temp #1",
            "temperature #2": "Temp #2",
            "temperature #3": "Temp #3",
            "temperature #4": "Temp #4",
        }
        lowered = normalized.lower()
        if lowered in replacements:
            return replacements[lowered]
        if lowered.startswith("core (") and "tctl/tdie" in lowered:
            return "Core"
        if any(token in lowered for token in {"vr soc", "vrsoc", "vrm", "vram", "vr"}):
            if "soc" in lowered:
                return "VR Soc"
            if "vram" in lowered:
                return "VRAM"
            if "vrm" in lowered:
                return "VRM"
            return "VR"
        if "(" in normalized and ")" in normalized:
            prefix = normalized.split("(", 1)[0].strip()
            suffix = normalized[normalized.index("(") :].strip()
            prefix = cls._humanize_words(prefix)
            return f"{prefix} {suffix}".strip()
        return cls._humanize_words(normalized)

    @staticmethod
    def _trim_brand_prefix(label: str) -> str:
        prefixes = (
            "AMD ",
            "Intel ",
            "NVIDIA ",
            "Nvidia ",
            "GeForce ",
            "Geforce ",
            "Nuvoton",
            "Team Group Inc",
        )
        trimmed = label.strip()
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                if trimmed.startswith(prefix):
                    trimmed = trimmed[len(prefix) :].strip()
                    changed = True
                    break
        return trimmed

    @staticmethod
    def _trim_model_suffix(label: str) -> str:
        lowered = label.lower().strip()
        for suffix in (" core", " gpu", " package", " composite"):
            if lowered.endswith(suffix):
                return label[: -len(suffix)].strip()
        return label

    @classmethod
    def _humanize_fan_label(cls, label: str) -> str:
        lowered = label.strip().lower()
        if lowered == "fan 1":
            return "Chassis Fan"
        if lowered.startswith("fan "):
            suffix = label.strip()[4:].strip()
            return f"Chassis Fan {suffix}".strip()
        return cls._humanize_words(label)

    @staticmethod
    def _normalize_lookup_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @classmethod
    def _humanize_words(cls, label: str) -> str:
        acronyms = {"cpu", "gpu", "ram", "aio", "vrm", "pch", "dimm"}
        parts = [part for part in re.split(r"[\s/_-]+", label.strip()) if part]
        if not parts:
            return label
        rendered: list[str] = []
        for part in parts:
            lowered = part.lower()
            if lowered in acronyms:
                rendered.append(lowered.upper())
                continue
            if part.isupper() and len(part) <= 4:
                rendered.append(part)
                continue
            rendered.append(part.capitalize())
        return " ".join(rendered)

    @staticmethod
    def _compact_identifier(identifier: str) -> str:
        trimmed = identifier.strip("/")
        if not trimmed:
            return identifier
        parts = trimmed.split("/")
        return " / ".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

    @staticmethod
    def _is_relevant_temperature(sensor: _HasSensorAttrs) -> bool:
        combined = (
            f"{sensor.hardware_name} {sensor.sensor_name} {sensor.identifier}"
        ).lower()
        blocked_terms = (
            r"\balarm\b",
            r"\blimit\b",
            r"\bcritical\b",
            r"\bwarning\b",
            r"\bthreshold\b",
            r"\bmax(?:imum)?\b",
            r"\bmin(?:imum)?\b",
            r"\btj[\s_-]?max\b",
            r"\bdistance\b",
        )
        return not any(re.search(pattern, combined) for pattern in blocked_terms)

    @staticmethod
    def _object_name_token(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip()
        if not cleaned:
            return "fanGroup"
        parts = cleaned.split()
        return parts[0].lower() + "".join(part.title() for part in parts[1:])
