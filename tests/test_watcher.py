"""Tests for pysysfan.watcher — Config file watching."""

import time
from unittest.mock import MagicMock, patch

import pytest

from pysysfan.watcher import ConfigWatcher, WATCHDOG_AVAILABLE


# ── Availability Check ────────────────────────────────────────────────


class TestAvailability:
    """Tests for watchdog availability checking."""

    def test_is_available_returns_bool(self):
        """is_available should return a boolean."""
        result = ConfigWatcher.is_available()
        assert isinstance(result, bool)


# ── ConfigWatcher Init ────────────────────────────────────────────────


class TestConfigWatcherInit:
    """Tests for ConfigWatcher initialization."""

    def test_stores_config_path(self, tmp_path):
        """Should store the provided config path."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")

        on_reload = MagicMock()
        watcher = ConfigWatcher(config_path=cfg_file, on_reload=on_reload)

        assert watcher.config_path == cfg_file.resolve()
        assert watcher.on_reload is on_reload
        assert watcher._running is False

    def test_stores_error_callback(self, tmp_path):
        """Should store the error callback."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")

        on_reload = MagicMock()
        on_error = MagicMock()
        watcher = ConfigWatcher(
            config_path=cfg_file, on_reload=on_reload, on_error=on_error
        )

        assert watcher.on_error is on_error


# ── ConfigWatcher Start/Stop ──────────────────────────────────────────


@pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="watchdog not installed")
class TestConfigWatcherLifecycle:
    """Tests for ConfigWatcher start and stop functionality."""

    def test_start_returns_false_when_no_watchdog(self, tmp_path):
        """Should return False if watchdog not available."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")

        with patch("pysysfan.watcher.WATCHDOG_AVAILABLE", False):
            watcher = ConfigWatcher(config_path=cfg_file, on_reload=MagicMock())
            result = watcher.start()
            assert result is False

    def test_start_returns_false_when_file_missing(self, tmp_path):
        """Should return False when config file doesn't exist."""
        cfg_file = tmp_path / "nonexistent.yaml"

        watcher = ConfigWatcher(config_path=cfg_file, on_reload=MagicMock())
        result = watcher.start()
        assert result is False

    def test_start_returns_true_when_successful(self, tmp_path):
        """Should return True when watcher starts successfully."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")

        watcher = ConfigWatcher(config_path=cfg_file, on_reload=MagicMock())
        result = watcher.start()

        try:
            assert result is True
            assert watcher.is_running() is True
        finally:
            watcher.stop()

    def test_stop_is_noop_when_not_running(self, tmp_path):
        """Should not raise when stopping an inactive watcher."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")

        watcher = ConfigWatcher(config_path=cfg_file, on_reload=MagicMock())
        watcher.stop()  # Should not raise

    def test_stop_stops_observer(self, tmp_path):
        """Should stop the observer when running."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")

        watcher = ConfigWatcher(config_path=cfg_file, on_reload=MagicMock())
        watcher.start()

        try:
            assert watcher.is_running() is True
            watcher.stop()
            assert watcher.is_running() is False
        finally:
            watcher.stop()

    def test_start_is_idempotent(self, tmp_path):
        """Multiple start calls should not create multiple observers."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")

        watcher = ConfigWatcher(config_path=cfg_file, on_reload=MagicMock())

        try:
            result1 = watcher.start()
            result2 = watcher.start()

            assert result1 is True
            assert result2 is True
        finally:
            watcher.stop()


# ── File Watching Callbacks ───────────────────────────────────────────


@pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="watchdog not installed")
class TestConfigWatcherCallbacks:
    """Tests for callback invocations on file changes."""

    def test_triggers_reload_on_file_change(self, tmp_path):
        """Should call on_reload when config file is modified."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("initial content")

        on_reload = MagicMock()
        watcher = ConfigWatcher(config_path=cfg_file, on_reload=on_reload)

        try:
            watcher.start()
            time.sleep(0.1)  # Let watcher start

            # Modify the file
            cfg_file.write_text("modified content")
            time.sleep(0.6)  # Wait for debounce (0.5s) + buffer

            on_reload.assert_called_once()
        finally:
            watcher.stop()

    def test_triggers_error_callback_on_handler_error(self, tmp_path):
        """Should call on_error when reload callback raises."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("initial")

        on_reload = MagicMock(side_effect=RuntimeError("test error"))
        on_error = MagicMock()
        watcher = ConfigWatcher(
            config_path=cfg_file, on_reload=on_reload, on_error=on_error
        )

        try:
            watcher.start()
            time.sleep(0.1)

            cfg_file.write_text("modified")
            time.sleep(0.6)

            on_error.assert_called_once()
            assert isinstance(on_error.call_args[0][0], RuntimeError)
        finally:
            watcher.stop()

    def test_ignores_other_files(self, tmp_path):
        """Should not trigger for other files in the same directory."""
        cfg_file = tmp_path / "config.yaml"
        other_file = tmp_path / "other.yaml"
        cfg_file.write_text("initial")
        other_file.write_text("other")

        on_reload = MagicMock()
        watcher = ConfigWatcher(config_path=cfg_file, on_reload=on_reload)

        try:
            watcher.start()
            time.sleep(0.1)

            # Modify other file
            other_file.write_text("modified other")
            time.sleep(0.6)

            on_reload.assert_not_called()
        finally:
            watcher.stop()


# ── Debouncing ─────────────────────────────────────────────────────────


@pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="watchdog not installed")
class TestConfigWatcherDebouncing:
    """Tests for debouncing rapid file changes."""

    def test_debounces_rapid_changes(self, tmp_path):
        """Should only call on_reload once for rapid changes."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("initial")

        on_reload = MagicMock()
        watcher = ConfigWatcher(config_path=cfg_file, on_reload=on_reload)

        try:
            watcher.start()
            time.sleep(0.1)

            # Rapidly modify file multiple times
            for i in range(5):
                cfg_file.write_text(f"content {i}")
                time.sleep(0.1)  # Less than debounce delay

            time.sleep(0.6)  # Wait for debounce

            # Should only be called once
            on_reload.assert_called_once()
        finally:
            watcher.stop()
