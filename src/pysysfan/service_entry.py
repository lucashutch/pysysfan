"""Windowless service entry point for pysysfan.

This module is registered as a ``gui-scripts`` entry point so that the
generated ``pysysfan-service.exe`` uses the Windows GUI subsystem and
never allocates a console window.  It wraps :class:`FanDaemon` with
file-based logging suitable for unattended Task Scheduler execution.

Usage (typically invoked by Task Scheduler, not manually)::

    pysysfan-service --config ~/.pysysfan/config.yaml
"""

from __future__ import annotations

import argparse
import atexit
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pysysfan.config import DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_PATH

DEFAULT_LOG_PATH = DEFAULT_CONFIG_DIR / "service.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3


class _RobustRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that gracefully handles Windows file locking."""

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except PermissionError:
            self.stream = open(self.baseFilename, "a", encoding="utf-8")


def _setup_logging(log_path: Path) -> None:
    """Configure root logger to write to a rotating log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = _RobustRotatingFileHandler(
        str(log_path),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def _redirect_stdio(log_path: Path) -> None:
    """Redirect stdout/stderr to the log file.

    GUI-subsystem executables (pythonw / gui-scripts) have no console
    attached, so writing to the default sys.stdout would raise an error.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    atexit.register(log_file.close)
    sys.stdout = log_file
    sys.stderr = log_file


def main() -> None:
    """Entry point for the windowless service executable."""
    parser = argparse.ArgumentParser(
        description="pysysfan windowless service daemon",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to config file. Default: ~/.pysysfan/config.yaml",
    )
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="Path to log file. Default: ~/.pysysfan/service.log",
    )
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    log_path = Path(args.log) if args.log else DEFAULT_LOG_PATH

    # Set up logging before anything else so crashes are captured.
    _redirect_stdio(log_path)
    _setup_logging(log_path)

    logger = logging.getLogger("pysysfan.service")
    logger.info("pysysfan service starting (config: %s)", config_path)

    try:
        from pysysfan.daemon import FanDaemon

        daemon = FanDaemon(config_path=config_path)
        daemon.run()
    except KeyboardInterrupt:
        logger.info("Service interrupted — shutting down.")
    except Exception:
        logger.exception("Service crashed with unhandled exception")
        sys.exit(1)
    finally:
        logger.info("pysysfan service stopped.")


if __name__ == "__main__":
    main()
