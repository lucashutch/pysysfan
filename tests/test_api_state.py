"""Tests for pysysfan.api.state — Thread-safe daemon state management."""

import time
import threading

from pysysfan.api.state import DaemonState, StateManager


class TestDaemonState:
    """Tests for DaemonState dataclass."""

    def test_create_daemon_state(self):
        """Creating a DaemonState with all fields should work."""
        state = DaemonState(
            pid=1234,
            config_path="/test/config.yaml",
            started_at=1000.0,
            running=True,
            uptime_seconds=42.5,
            last_poll_time=1042.5,
            last_error=None,
            poll_interval=2.0,
            fans_configured=3,
            curves_configured=2,
            active_profile="default",
            current_temps={"/cpu/0": 45.0},
            current_fan_speeds={"/fan/0": 1200.0},
            current_targets={"/fan/0": 50.0},
            auto_reload_enabled=True,
            api_enabled=True,
            api_port=8765,
        )

        assert state.pid == 1234
        assert state.config_path == "/test/config.yaml"
        assert state.running is True
        assert state.uptime_seconds == 42.5
        assert state.current_temps == {"/cpu/0": 45.0}
        assert state.api_port == 8765

    def test_daemon_state_defaults(self):
        """DaemonState should have sensible defaults for optional fields."""
        state = DaemonState(
            pid=1234,
            config_path="/test/config.yaml",
            started_at=1000.0,
            running=True,
            uptime_seconds=0.0,
            last_poll_time=1000.0,
            last_error=None,
            poll_interval=2.0,
            fans_configured=0,
            curves_configured=0,
            active_profile="default",
        )

        assert state.current_temps == {}
        assert state.current_fan_speeds == {}
        assert state.current_targets == {}
        assert state.auto_reload_enabled is True
        assert state.api_enabled is False
        assert state.api_port == 8765


class TestStateManager:
    """Tests for StateManager thread-safe container."""

    def test_state_manager_initial_state(self):
        """StateManager should start with no state."""
        manager = StateManager()
        assert manager.get_snapshot() is None

    def test_update_state_creates_new_state(self):
        """First update_state should create a new DaemonState."""
        manager = StateManager()

        manager.update_state(
            pid=1234,
            config_path="/test/config.yaml",
            running=True,
            started_at=1000.0,
        )

        snapshot = manager.get_snapshot()
        assert snapshot is not None
        assert snapshot.pid == 1234
        assert snapshot.running is True

    def test_update_state_merges_with_existing(self):
        """Subsequent update_state calls should merge with existing state."""
        manager = StateManager()

        manager.update_state(
            pid=1234,
            config_path="/test/config.yaml",
            running=True,
            started_at=1000.0,
            fans_configured=2,
        )

        manager.update_state(
            fans_configured=3,
            curves_configured=2,
        )

        snapshot = manager.get_snapshot()
        assert snapshot is not None
        assert snapshot.pid == 1234
        assert snapshot.fans_configured == 3
        assert snapshot.curves_configured == 2
        assert snapshot.config_path == "/test/config.yaml"

    def test_update_state_replaces_dicts(self):
        """update_state should replace dict fields, not merge them."""
        manager = StateManager()

        manager.update_state(
            pid=1234,
            config_path="/test/config.yaml",
            running=True,
            started_at=1000.0,
            current_temps={"/cpu/0": 45.0, "/cpu/1": 46.0},
        )

        manager.update_state(
            current_temps={"/cpu/0": 50.0},
        )

        snapshot = manager.get_snapshot()
        assert snapshot is not None
        assert snapshot.current_temps == {"/cpu/0": 50.0}
        assert "/cpu/1" not in snapshot.current_temps

    def test_get_snapshot_returns_copy(self):
        """get_snapshot should return the current state (not a deep copy)."""
        manager = StateManager()

        manager.update_state(
            pid=1234,
            config_path="/test/config.yaml",
            running=True,
            started_at=1000.0,
            current_temps={"/cpu/0": 45.0},
        )

        snapshot1 = manager.get_snapshot()
        snapshot2 = manager.get_snapshot()

        assert snapshot1 is not None
        assert snapshot2 is not None
        assert snapshot1.pid == snapshot2.pid
        assert snapshot1.current_temps == snapshot2.current_temps

    def test_clear_error(self):
        """clear_error should set last_error to None."""
        manager = StateManager()

        manager.update_state(
            pid=1234,
            config_path="/test/config.yaml",
            running=True,
            started_at=1000.0,
            last_error="Something went wrong",
        )

        snapshot = manager.get_snapshot()
        assert snapshot is not None
        assert snapshot.last_error == "Something went wrong"

        manager.clear_error()

        snapshot = manager.get_snapshot()
        assert snapshot is not None
        assert snapshot.last_error is None

    def test_thread_safety(self):
        """StateManager should be thread-safe for concurrent updates."""
        manager = StateManager()
        errors = []

        def update_loop(thread_id: int):
            try:
                for i in range(100):
                    manager.update_state(
                        pid=thread_id,
                        fans_configured=i,
                    )
                    snapshot = manager.get_snapshot()
                    assert snapshot is not None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_loop, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_update_state_last_poll_time_default(self):
        """update_state should set last_poll_time to current time if not provided."""
        manager = StateManager()

        before = time.time()
        manager.update_state(
            pid=1234,
            config_path="/test/config.yaml",
            running=True,
            started_at=1000.0,
        )
        after = time.time()

        snapshot = manager.get_snapshot()
        assert snapshot is not None
        assert before <= snapshot.last_poll_time <= after
