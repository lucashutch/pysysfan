"""Tests for the PySide6 dashboard page."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from pysysfan.gui.desktop.dashboard_page import DashboardPage


class FakeClient:
    """Small fake daemon client for dashboard tests."""

    def __init__(self):
        self.active_profile = "default"
        self.status = {
            "active_profile": self.active_profile,
            "uptime_seconds": 42.0,
            "poll_interval": 2.0,
            "fans_configured": 2,
        }
        self.profiles = {
            "profiles": [
                {"name": "default", "display_name": "Default"},
                {"name": "gaming", "display_name": "Gaming"},
            ],
            "active": self.active_profile,
        }
        self.alert_rules = {
            "rules": [
                {
                    "rule_id": "cpu_temp:high_temp",
                    "sensor_id": "cpu_temp",
                    "alert_type": "high_temp",
                }
            ],
            "count": 1,
        }
        self.alert_history = {
            "alerts": [
                {
                    "sensor_id": "cpu_temp",
                    "alert_type": "high_temp",
                    "value": 85.0,
                }
            ],
            "count": 1,
        }
        self.sensors = {
            "temperatures": [
                {"sensor_name": "CPU Core", "value": 47.5},
            ],
            "fans": [
                {"sensor_name": "CPU Fan", "rpm": 1250},
            ],
        }
        self.stream_payloads = [
            {
                "temperatures": [{"sensor_name": "CPU Core", "value": 50.0}],
                "fans": [{"sensor_name": "CPU Fan", "rpm": 1300}],
            }
        ]
        self.profile_activations: list[str] = []
        self.alert_history_cleared = False

    def get_status(self):
        self.status["active_profile"] = self.active_profile
        return self.status

    def get_sensors(self):
        return self.sensors

    def list_profiles(self):
        self.profiles["active"] = self.active_profile
        return self.profiles

    def activate_profile(self, name):
        self.active_profile = name
        self.profile_activations.append(name)
        return {"success": True, "message": f"Switched to profile: {name}"}

    def list_alert_rules(self):
        self.alert_rules["count"] = len(self.alert_rules["rules"])
        return self.alert_rules

    def get_alert_history(self, limit=50):
        return {
            "alerts": self.alert_history["alerts"][:limit],
            "count": len(self.alert_history["alerts"][:limit]),
        }

    def clear_alert_history(self):
        self.alert_history["alerts"] = []
        self.alert_history_cleared = True
        return {"success": True}

    def stream_sensors(self):
        for payload in self.stream_payloads:
            yield payload


def test_dashboard_refresh_populates_snapshot(qtbot) -> None:
    """Refreshing the dashboard should populate status and sensor widgets."""
    fake_client = FakeClient()
    page = DashboardPage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.connection_label.text() == "Connection: Connected"
    assert page.active_profile_label.text() == "Active profile: default"
    assert page.uptime_label.text() == "Uptime: 42.0s"
    assert page.poll_interval_label.text() == "Poll interval: 2.0s"
    assert page.fans_configured_label.text() == "Configured fans: 2"
    assert page.profile_selector.count() == 2
    assert page.profile_selector.currentText() == "default"
    assert page.alert_rules_label.text() == "Alert rules: 1"
    assert page.alert_history_label.text() == "Recent alerts: 1"
    assert page.alerts_list.item(0).text() == "cpu_temp [high_temp] -> 85.0"
    assert page.temperatures_list.count() == 1
    assert page.fans_list.count() == 1


def test_dashboard_shows_error_when_client_creation_fails(qtbot) -> None:
    """Dashboard should surface client errors instead of crashing."""

    def broken_factory():
        raise FileNotFoundError("API token not found")

    page = DashboardPage(client_factory=broken_factory)
    qtbot.addWidget(page)

    page.refresh_data()

    assert page.connection_label.text() == "Connection: Disconnected"
    assert page.error_label.text() == "API token not found"
    assert not page.error_label.isHidden()


def test_dashboard_live_updates_apply_stream_payload(qtbot) -> None:
    """Starting live updates should apply streamed sensor payloads."""
    fake_client = FakeClient()
    page = DashboardPage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)

    page.toggle_live_updates()
    qtbot.waitUntil(lambda: page.temperatures_list.count() == 1)

    assert page.live_updates_button.text() == "Start Live Updates"
    assert page.temperatures_list.item(0).text() == "CPU Core: 50.0 C"
    assert page.fans_list.item(0).text() == "CPU Fan: 1300 RPM"


def test_dashboard_activates_selected_profile(qtbot) -> None:
    """Activating a profile should call the client and refresh the active label."""
    fake_client = FakeClient()
    page = DashboardPage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)
    page.refresh_data()

    page.profile_selector.setCurrentText("gaming")
    page.activate_selected_profile()

    assert fake_client.profile_activations == ["gaming"]
    assert page.active_profile_label.text() == "Active profile: gaming"
    assert page.error_label.text() == "Switched to profile: gaming"


def test_dashboard_clears_alert_history(qtbot) -> None:
    """Clearing alert history should empty the alert list and update the summary."""
    fake_client = FakeClient()
    page = DashboardPage(client_factory=lambda: fake_client)
    qtbot.addWidget(page)
    page.refresh_data()

    page.clear_alert_history()

    assert fake_client.alert_history_cleared is True
    assert page.alert_history_label.text() == "Recent alerts: 0"
    assert page.alerts_list.item(0).text() == "No recent alerts"
    assert page.error_label.text() == "Alert history cleared"
