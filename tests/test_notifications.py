"""Tests for pysysfan.notifications — Alert rules and notification manager."""

import pytest
from pysysfan.notifications import AlertRule, NotificationManager


@pytest.fixture
def manager():
    return NotificationManager()


@pytest.fixture
def high_temp_rule():
    return AlertRule(
        sensor_id="cpu_temp",
        alert_type="high_temp",
        threshold=80.0,
        enabled=True,
        cooldown_seconds=60.0,
    )


@pytest.fixture
def low_temp_rule():
    return AlertRule(
        sensor_id="ambient_temp",
        alert_type="low_temp",
        threshold=10.0,
        enabled=True,
        cooldown_seconds=30.0,
    )


@pytest.fixture
def fan_failure_rule():
    return AlertRule(
        sensor_id="case_fan",
        alert_type="fan_failure",
        threshold=100.0,
        enabled=True,
        cooldown_seconds=120.0,
    )


class TestAlertRule:
    def test_create_rule(self):
        rule = AlertRule(
            sensor_id="test_sensor",
            alert_type="high_temp",
            threshold=75.0,
        )
        assert rule.sensor_id == "test_sensor"
        assert rule.alert_type == "high_temp"
        assert rule.threshold == 75.0
        assert rule.enabled is True
        assert rule.cooldown_seconds == 60.0

    def test_default_values(self):
        rule = AlertRule(sensor_id="x", alert_type="high_temp", threshold=50.0)
        assert rule.enabled is True
        assert rule.cooldown_seconds == 60.0


class TestNotificationManager:
    def test_add_rule(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        rules = manager.get_rules()
        assert len(rules) == 1
        assert rules[0]["sensor_id"] == "cpu_temp"

    def test_add_invalid_alert_type(self, manager):
        rule = AlertRule(sensor_id="x", alert_type="invalid", threshold=50.0)
        with pytest.raises(ValueError, match="Invalid alert_type"):
            manager.add_rule(rule)

    def test_remove_rule(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        assert len(manager.get_rules()) == 1
        removed = manager.remove_rule("cpu_temp")
        assert removed is True
        assert len(manager.get_rules()) == 0

    def test_remove_nonexistent_rule(self, manager):
        removed = manager.remove_rule("nonexistent")
        assert removed is False

    def test_update_rule(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        success = manager.update_rule("cpu_temp", threshold=85.0, enabled=False)
        assert success is True
        rules = manager.get_rules()
        assert rules[0]["threshold"] == 85.0
        assert rules[0]["enabled"] is False

    def test_update_nonexistent_rule(self, manager):
        success = manager.update_rule("nonexistent", threshold=50.0)
        assert success is False


class TestHighTempAlert:
    def test_trigger_high_temp(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        readings = {"cpu_temp": 85.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "high_temp"
        assert alerts[0].value == 85.0
        assert "85.0" in alerts[0].message

    def test_no_trigger_below_threshold(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        readings = {"cpu_temp": 75.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 0

    def test_cooldown_prevents_repeat(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        readings = {"cpu_temp": 85.0}
        alerts1 = manager.check(readings, current_time=1000.0)
        assert len(alerts1) == 1
        alerts2 = manager.check(readings, current_time=1030.0)
        assert len(alerts2) == 0

    def test_cooldown_allows_after_expiry(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        readings = {"cpu_temp": 85.0}
        alerts1 = manager.check(readings, current_time=1000.0)
        assert len(alerts1) == 1
        alerts2 = manager.check(readings, current_time=1065.0)
        assert len(alerts2) == 1


class TestLowTempAlert:
    def test_trigger_low_temp(self, manager, low_temp_rule):
        manager.add_rule(low_temp_rule)
        readings = {"ambient_temp": 5.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "low_temp"

    def test_no_trigger_above_threshold(self, manager, low_temp_rule):
        manager.add_rule(low_temp_rule)
        readings = {"ambient_temp": 15.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 0


class TestFanFailureAlert:
    def test_trigger_fan_failure(self, manager, fan_failure_rule):
        manager.add_rule(fan_failure_rule)
        readings = {"case_fan": 50.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "fan_failure"

    def test_no_trigger_fan_ok(self, manager, fan_failure_rule):
        manager.add_rule(fan_failure_rule)
        readings = {"case_fan": 500.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 0


class TestFanHighAlert:
    def test_trigger_fan_high(self, manager):
        rule = AlertRule(
            sensor_id="intake_fan",
            alert_type="fan_high",
            threshold=2000.0,
            enabled=True,
        )
        manager.add_rule(rule)
        readings = {"intake_fan": 2500.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "fan_high"


class TestMultipleRules:
    def test_multiple_sensors(self, manager, high_temp_rule, low_temp_rule):
        manager.add_rule(high_temp_rule)
        manager.add_rule(low_temp_rule)
        readings = {"cpu_temp": 85.0, "ambient_temp": 5.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 2

    def test_disabled_rule_skipped(self, manager, high_temp_rule):
        high_temp_rule.enabled = False
        manager.add_rule(high_temp_rule)
        readings = {"cpu_temp": 85.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 0

    def test_missing_sensor_skipped(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        readings = {"other_sensor": 85.0}
        alerts = manager.check(readings, current_time=1000.0)
        assert len(alerts) == 0


class TestAlertHistory:
    def test_history_tracking(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        readings = {"cpu_temp": 85.0}
        manager.check(readings, current_time=1000.0)
        history = manager.get_history()
        assert len(history) == 1
        assert history[0]["alert_type"] == "high_temp"

    def test_history_limit(self, manager):
        rule = AlertRule(
            sensor_id="temp",
            alert_type="high_temp",
            threshold=50.0,
        )
        manager.add_rule(rule)
        for i in range(150):
            readings = {"temp": 60.0}
            manager.check(readings, current_time=float(i * 100))
        history = manager.get_history(limit=200)
        assert len(history) == 100

    def test_clear_history(self, manager, high_temp_rule):
        manager.add_rule(high_temp_rule)
        readings = {"cpu_temp": 85.0}
        manager.check(readings, current_time=1000.0)
        assert len(manager.get_history()) == 1
        manager.clear_history()
        assert len(manager.get_history()) == 0
