"""Tests for the PySide6 dashboard page."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from pysysfan.gui.desktop.dashboard_page import DashboardPage


class FakeClient:
    """Small fake daemon client for dashboard tests."""

    def __init__(self):
        self.status = {
            "active_profile": "default",
            "uptime_seconds": 42.0,
            "poll_interval": 2.0,
            "fans_configured": 2,
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

    def get_status(self):
        return self.status

    def get_sensors(self):
        return self.sensors

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
