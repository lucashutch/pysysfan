"""Tests for pysysfan.service_entry — windowless service entry point."""

from pathlib import Path
from unittest.mock import patch, MagicMock


from pysysfan.service_entry import (
    DEFAULT_LOG_PATH,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
    _setup_logging,
    main,
)


class TestDefaults:
    """Verify default configuration constants."""

    def test_log_path_is_in_config_dir(self):
        assert DEFAULT_LOG_PATH.name == "service.log"
        assert ".pysysfan" in str(DEFAULT_LOG_PATH)

    def test_log_max_bytes(self):
        assert LOG_MAX_BYTES == 5 * 1024 * 1024

    def test_log_backup_count(self):
        assert LOG_BACKUP_COUNT == 3


class TestSetupLogging:
    """Tests for _setup_logging()."""

    def test_creates_log_directory(self, tmp_path):
        log_path = tmp_path / "subdir" / "test.log"
        _setup_logging(log_path)
        assert log_path.parent.is_dir()

    def test_adds_rotating_handler(self, tmp_path):
        import logging

        log_path = tmp_path / "test.log"
        _setup_logging(log_path)
        root = logging.getLogger()
        handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
            and Path(h.baseFilename) == log_path
        ]
        assert len(handlers) >= 1
        # Cleanup
        for h in handlers:
            root.removeHandler(h)
            h.close()


class TestServiceEntryMain:
    """Tests for the main() entry point."""

    @patch("pysysfan.daemon.FanDaemon")
    @patch("pysysfan.service_entry._setup_logging")
    @patch("pysysfan.service_entry._redirect_stdio")
    @patch("sys.argv", ["pysysfan-service"])
    def test_main_creates_and_runs_daemon(self, mock_redir, mock_log, mock_daemon_cls):
        """main() should create a FanDaemon with default config and call run()."""
        daemon_instance = MagicMock()
        mock_daemon_cls.return_value = daemon_instance

        main()

        mock_daemon_cls.assert_called_once()
        daemon_instance.run.assert_called_once()

    @patch("pysysfan.daemon.FanDaemon")
    @patch("pysysfan.service_entry._setup_logging")
    @patch("pysysfan.service_entry._redirect_stdio")
    @patch("sys.argv", ["pysysfan-service", "--config", "C:\\test\\config.yaml"])
    def test_main_passes_config(self, mock_redir, mock_log, mock_daemon_cls):
        """main() should pass --config flag through to FanDaemon."""
        daemon_instance = MagicMock()
        mock_daemon_cls.return_value = daemon_instance

        main()

        call_kwargs = mock_daemon_cls.call_args
        config_arg = (
            call_kwargs[1]["config_path"] if call_kwargs[1] else call_kwargs[0][0]
        )
        assert str(config_arg) == "C:\\test\\config.yaml"

    @patch("pysysfan.daemon.FanDaemon")
    @patch("pysysfan.service_entry._setup_logging")
    @patch("pysysfan.service_entry._redirect_stdio")
    @patch("sys.argv", ["pysysfan-service"])
    def test_main_handles_keyboard_interrupt(
        self, mock_redir, mock_log, mock_daemon_cls
    ):
        """main() should handle KeyboardInterrupt gracefully."""
        daemon_instance = MagicMock()
        daemon_instance.run.side_effect = KeyboardInterrupt
        mock_daemon_cls.return_value = daemon_instance

        # Should not raise
        main()
