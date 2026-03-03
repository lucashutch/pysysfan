"""Fan control daemon — the main control loop."""

from __future__ import annotations

import atexit
import logging
import signal
import time
from pathlib import Path

from pysysfan.config import Config, DEFAULT_CONFIG_PATH
from pysysfan.curves import FanCurve

logger = logging.getLogger(__name__)


class FanDaemon:
    """Background fan control loop.

    Polls temperature sensors at a configured interval, evaluates fan curves,
    and applies speed settings to controllable fan outputs.

    Safety guarantee: on any exit (normal, exception, or signal), all fan
    controls are restored to BIOS/automatic mode via atexit and signal handlers.
    """

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._running = False
        self._hw = None
        self._curves: dict[str, FanCurve] = {}

    # ── Setup / teardown ──────────────────────────────────────────────

    def _load_config(self) -> Config:
        logger.info(f"Loading config from {self.config_path}")
        return Config.load(self.config_path)

    def _build_curves(self, cfg: Config) -> dict[str, FanCurve]:
        curves: dict[str, FanCurve] = {}
        for name, c in cfg.curves.items():
            curves[name] = FanCurve(name=name, points=c.points, hysteresis=c.hysteresis)
            logger.debug(
                f"Loaded curve '{name}' with {len(c.points)} points, hysteresis={c.hysteresis}°C"
            )
        return curves

    def _open_hardware(self):
        from pysysfan.hardware import HardwareManager

        hw = HardwareManager()
        hw.open()
        return hw

    def _register_safety_handlers(self):
        """Register atexit and signal handlers to restore fan control on exit."""
        atexit.register(self._emergency_restore)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._signal_handler)
            except (OSError, ValueError):
                pass  # May fail if not in main thread

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self._running = False

    def _emergency_restore(self):
        """atexit: best-effort restore of BIOS fan control."""
        if self._hw is not None:
            try:
                self._hw.restore_defaults()
                logger.info("Fan controls restored to BIOS defaults.")
            except Exception as e:
                logger.warning(f"Could not restore fan defaults: {e}")

    # ── Update check ────────────────────────────────────────────────

    def _check_for_updates(self, cfg) -> None:
        """Optionally check for a newer pysysfan release at startup."""
        if not cfg.update.auto_check:
            return

        try:
            from pysysfan.updater import check_for_update, perform_update

            info = check_for_update()
            if not info.available:
                logger.debug("pysysfan is up-to-date (%s).", info.current_version)
                return

            if cfg.update.notify_only:
                logger.info(
                    "A new pysysfan version is available: %s → %s. "
                    "Run 'pysysfan update apply' to upgrade.",
                    info.current_version,
                    info.latest_version,
                )
            else:
                logger.info(
                    "Auto-updating pysysfan %s → %s...",
                    info.current_version,
                    info.latest_version,
                )
                perform_update(info.latest_version)
                logger.info("Update installed. Restart the daemon for the new version.")
        except Exception as exc:
            logger.warning("Update check failed (non-fatal): %s", exc)

    # ── Control logic ─────────────────────────────────────────────────

    def _get_temperature(self, source_id: str, temperatures: list) -> float | None:
        """Look up a temperature reading by sensor identifier."""
        for sensor in temperatures:
            if sensor.identifier == source_id:
                return sensor.value
        return None

    def _run_once(self, cfg: Config) -> dict[str, float]:
        """Perform a single control pass. Returns {fan_name: speed_percent}."""
        applied: dict[str, float] = {}

        temps = self._hw.get_temperatures()

        for fan_name, fan_cfg in cfg.fans.items():
            curve = self._curves.get(fan_cfg.curve)
            if curve is None:
                logger.warning(
                    f"Fan '{fan_name}': curve '{fan_cfg.curve}' not found, skipping."
                )
                continue

            temp = self._get_temperature(fan_cfg.temp_id, temps)
            if temp is None:
                logger.warning(
                    f"Fan '{fan_name}': temperature source '{fan_cfg.temp_id}' not found. "
                    "Is the daemon running as Administrator?"
                )
                continue

            if temp == 0.0:
                # LHM sometimes returns 0.0 for unavailable sensors (not None)
                logger.debug(
                    f"Fan '{fan_name}': source returned 0.0°C — skipping this pass."
                )
                continue

            target_pct = curve.evaluate(temp)

            try:
                self._hw.set_fan_speed(fan_cfg.fan_id, target_pct)
                applied[fan_name] = target_pct
                logger.debug(f"Fan '{fan_name}': {temp:.1f}°C → {target_pct:.1f}%")
            except Exception as e:
                logger.error(f"Fan '{fan_name}': failed to set speed: {e}")

        return applied

    # ── Public API ────────────────────────────────────────────────────

    def run_once(self) -> dict[str, float]:
        """Perform a single evaluation pass and return applied speeds.

        Opens hardware, runs one control pass, then closes hardware.
        Useful for testing configuration without starting the daemon loop.
        """
        cfg = self._load_config()
        self._curves = self._build_curves(cfg)

        self._hw = self._open_hardware()
        try:
            # Do an initial scan to populate the control map
            self._hw.scan()
            result = self._run_once(cfg)
        finally:
            self._hw.restore_defaults()
            self._hw.close()
            self._hw = None
        return result

    def run(self):
        """Start the main fan control loop. Blocks until stopped.

        Restores BIOS fan control on exit in all cases.
        """
        logger.info("pysysfan daemon starting...")

        cfg = self._load_config()
        self._curves = self._build_curves(cfg)
        self._check_for_updates(cfg)
        self._register_safety_handlers()

        self._hw = self._open_hardware()
        try:
            # Initial scan to populate the controllable fan map
            scan_result = self._hw.scan()
            logger.info(
                f"Hardware scan found: {len(scan_result.temperatures)} temps, "
                f"{len(scan_result.fans)} fans, "
                f"{sum(1 for c in scan_result.controls if c.has_control)} controllable outputs"
            )

            self._running = True
            logger.info(f"Control loop started (poll interval: {cfg.poll_interval}s)")

            while self._running:
                try:
                    applied = self._run_once(cfg)
                    if applied:
                        status = ", ".join(f"{k}={v:.0f}%" for k, v in applied.items())
                        logger.info(f"Applied: {status}")
                except Exception as e:
                    logger.error(f"Control loop error: {e}", exc_info=True)

                time.sleep(cfg.poll_interval)

        finally:
            logger.info("Restoring BIOS fan control and shutting down...")
            self._hw.restore_defaults()
            self._hw.close()
            self._hw = None
            logger.info("Daemon stopped.")
