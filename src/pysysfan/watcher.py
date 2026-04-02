"""File watcher for live config reloading."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# watchdog is optional - graceful degradation if not installed
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object
    FileModifiedEvent = None


class ConfigFileHandler(FileSystemEventHandler):
    """Handles file system events for config file changes."""

    def __init__(
        self,
        config_path: Path,
        on_modified: Callable[[], None],
        on_error: Callable[[Exception], None] | None = None,
    ):
        self.config_path = Path(config_path).resolve()
        self._on_modified_callback = on_modified
        self._on_error = on_error
        self._debounce_timer: threading.Timer | None = None
        self._debounce_delay = 0.5  # seconds

    def on_modified(self, event):
        """Called when a file or directory is modified."""
        if not isinstance(event, FileModifiedEvent):  # type: ignore
            return

        event_path = Path(event.src_path).resolve()
        if event_path != self.config_path:
            return

        # Debounce rapid successive modifications
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()

        self._debounce_timer = threading.Timer(
            self._debounce_delay, self._handle_change
        )
        self._debounce_timer.start()

    def _handle_change(self):
        """Process the config change notification."""
        try:
            self._on_modified_callback()
        except Exception as e:
            logger.error(f"Config change handler error: {e}")
            if self._on_error:
                try:
                    self._on_error(e)
                except Exception:
                    pass


class ConfigWatcher:
    """Watches the config file for changes and triggers reloads.

    Uses watchdog library if available; gracefully degrades to polling
    or manual-only reloads when watchdog is not installed.
    """

    def __init__(
        self,
        config_path: Path | str,
        on_reload: Callable[[], None],
        on_error: Callable[[Exception], None] | None = None,
    ):
        """Initialize the config watcher.

        Args:
            config_path: Path to the config file to watch
            on_reload: Callback to invoke when config is modified
            on_error: Optional callback for error handling
        """
        self.config_path = Path(config_path).resolve()
        self.on_reload = on_reload
        self.on_error = on_error
        self._observer: Observer | None = None
        self._watch = None
        self._running = False

    def start(self) -> bool:
        """Start watching the config file for changes.

        Returns:
            True if watching started successfully, False otherwise
        """
        if not WATCHDOG_AVAILABLE:
            logger.warning(
                "watchdog library not installed. Install with: uv pip install watchdog"
            )
            return False

        if self._running:
            return True

        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return False

        try:
            self._observer = Observer()  # type: ignore
            handler = ConfigFileHandler(
                config_path=self.config_path,
                on_modified=self.on_reload,
                on_error=self.on_error,
            )
            self._watch = self._observer.schedule(
                handler,
                path=str(self.config_path.parent),
                recursive=False,
            )
            self._observer.start()
            self._running = True
            logger.info(f"Started watching config file: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to start config watcher: {e}")
            return False

    def stop(self):
        """Stop watching the config file."""
        if not self._running or self._observer is None:
            return

        try:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            logger.info("Stopped config file watcher")
        except Exception as e:
            logger.warning(f"Error stopping config watcher: {e}")
        finally:
            self._running = False
            self._observer = None
            self._watch = None

    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running

    @staticmethod
    def is_available() -> bool:
        """Check if file watching is available (watchdog installed)."""
        return WATCHDOG_AVAILABLE
