"""Notification system for temperature and fan alerts."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Represents a triggered alert."""

    rule_id: str
    sensor_id: str
    alert_type: str
    message: str
    value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class AlertRule:
    """Rule for triggering alerts based on sensor readings."""

    sensor_id: str
    alert_type: str
    threshold: float
    enabled: bool = True
    cooldown_seconds: float = 60.0


class NotificationManager:
    """Manages alert rules and checks sensor readings against them.

    Supports multiple alert types:
    - high_temp: Triggered when temperature exceeds threshold
    - low_temp: Triggered when temperature falls below threshold
    - fan_failure: Triggered when fan RPM is zero or below threshold
    - fan_high: Triggered when fan RPM exceeds threshold

    Each rule has a cooldown period to prevent alert spam.
    """

    VALID_ALERT_TYPES = frozenset({"high_temp", "low_temp", "fan_failure", "fan_high"})

    def __init__(self):
        self.rules: list[AlertRule] = []
        self.last_alert_time: dict[str, float] = {}
        self._alert_history: list[Alert] = []
        self._max_history = 100

    @staticmethod
    def build_rule_id(sensor_id: str, alert_type: str) -> str:
        """Build the stable identifier used for alert rules and history."""
        return f"{sensor_id}:{alert_type}"

    def _rule_matches_identifier(self, rule: AlertRule, identifier: str) -> bool:
        """Match either the composite rule ID or the legacy sensor-only ID."""
        return (
            self.build_rule_id(rule.sensor_id, rule.alert_type) == identifier
            or rule.sensor_id == identifier
        )

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule to the manager."""
        if rule.alert_type not in self.VALID_ALERT_TYPES:
            raise ValueError(
                f"Invalid alert_type: {rule.alert_type}. "
                f"Valid types: {self.VALID_ALERT_TYPES}"
            )
        self.rules.append(rule)
        logger.debug(
            f"Added alert rule: {rule.alert_type} for {rule.sensor_id} "
            f"(threshold: {rule.threshold}, cooldown: {rule.cooldown_seconds}s)"
        )

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by its sensor_id and alert_type combination.

        Returns True if rule was found and removed.
        """
        initial_len = len(self.rules)
        self.rules = [
            r for r in self.rules if not self._rule_matches_identifier(r, rule_id)
        ]
        removed = len(self.rules) < initial_len
        if removed:
            logger.debug(f"Removed alert rule: {rule_id}")
        return removed

    def get_rules(self) -> list[dict[str, Any]]:
        """Get all rules as dictionaries."""
        return [
            {
                "rule_id": self.build_rule_id(r.sensor_id, r.alert_type),
                "sensor_id": r.sensor_id,
                "alert_type": r.alert_type,
                "threshold": r.threshold,
                "enabled": r.enabled,
                "cooldown_seconds": r.cooldown_seconds,
            }
            for r in self.rules
        ]

    def update_rule(
        self,
        rule_id: str,
        alert_type: str | None = None,
        threshold: float | None = None,
        enabled: bool | None = None,
        cooldown_seconds: float | None = None,
    ) -> bool:
        """Update an existing rule.

        Returns True if rule was found and updated.
        """
        if alert_type is not None and alert_type not in self.VALID_ALERT_TYPES:
            raise ValueError(
                f"Invalid alert_type: {alert_type}. "
                f"Valid types: {self.VALID_ALERT_TYPES}"
            )

        for rule in self.rules:
            if self._rule_matches_identifier(rule, rule_id):
                if alert_type is not None:
                    rule.alert_type = alert_type
                if threshold is not None:
                    rule.threshold = threshold
                if enabled is not None:
                    rule.enabled = enabled
                if cooldown_seconds is not None:
                    rule.cooldown_seconds = cooldown_seconds
                logger.debug(f"Updated alert rule: {rule_id}")
                return True
        return False

    def check(
        self, sensor_readings: dict[str, float], current_time: float | None = None
    ) -> list[Alert]:
        """Check all rules against current readings.

        Args:
            sensor_readings: Dictionary mapping sensor IDs to their current values.
            current_time: Current timestamp (defaults to time.time())

        Returns:
            List of triggered alerts (respecting cooldown periods).
        """
        if current_time is None:
            current_time = time.time()

        new_alerts: list[Alert] = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            value = sensor_readings.get(rule.sensor_id)
            if value is None:
                continue

            triggered, message = self._check_rule(rule, value)

            if triggered:
                key = f"{rule.sensor_id}:{rule.alert_type}"
                last_time = self.last_alert_time.get(key, 0)
                if current_time - last_time < rule.cooldown_seconds:
                    continue

                self.last_alert_time[key] = current_time
                alert = Alert(
                    rule_id=self.build_rule_id(rule.sensor_id, rule.alert_type),
                    sensor_id=rule.sensor_id,
                    alert_type=rule.alert_type,
                    message=message,
                    value=value,
                    threshold=rule.threshold,
                    timestamp=current_time,
                )
                new_alerts.append(alert)
                self._add_to_history(alert)
                logger.info(f"Alert triggered: {message}")

        return new_alerts

    def _check_rule(self, rule: AlertRule, value: float) -> tuple[bool, str]:
        """Check a single rule against a value.

        Returns:
            Tuple of (triggered: bool, message: str)
        """
        if rule.alert_type == "high_temp":
            if value > rule.threshold:
                return True, (
                    f"High temperature: {value:.1f}°C (threshold: {rule.threshold}°C)"
                )

        elif rule.alert_type == "low_temp":
            if value < rule.threshold:
                return True, (
                    f"Low temperature: {value:.1f}°C (threshold: {rule.threshold}°C)"
                )

        elif rule.alert_type == "fan_failure":
            if value <= rule.threshold:
                return True, (
                    f"Fan failure warning: {value:.0f} RPM "
                    f"(threshold: {rule.threshold:.0f} RPM)"
                )

        elif rule.alert_type == "fan_high":
            if value > rule.threshold:
                return True, (
                    f"High fan speed: {value:.0f} RPM "
                    f"(threshold: {rule.threshold:.0f} RPM)"
                )

        return False, ""

    def _add_to_history(self, alert: Alert) -> None:
        """Add alert to history, maintaining max size."""
        self._alert_history.append(alert)
        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history :]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent alert history."""
        recent = self._alert_history[-limit:]
        return [
            {
                "rule_id": a.rule_id,
                "sensor_id": a.sensor_id,
                "alert_type": a.alert_type,
                "message": a.message,
                "value": a.value,
                "threshold": a.threshold,
                "timestamp": a.timestamp,
            }
            for a in recent
        ]

    def clear_history(self) -> None:
        """Clear alert history."""
        self._alert_history.clear()
        self.last_alert_time.clear()
