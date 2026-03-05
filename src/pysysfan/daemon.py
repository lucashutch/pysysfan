"""Fan control daemon — the main control loop."""

from __future__ import annotations

import atexit
import logging
import signal
import time
from pathlib import Path

from pysysfan.config import Config, DEFAULT_CONFIG_PATH
from pysysfan.curves import FanCurve, StaticCurve, parse_curve, InvalidCurveError
from pysysfan.temperature import lookup_and_aggregate, get_valid_aggregation_methods
from pysysfan.watcher import ConfigWatcher

logger = logging.getLogger(__name__)


class FanDaemon:
    """Background fan control loop.

    Polls temperature sensors at a configured interval, evaluates fan curves,
    and applies speed settings to controllable fan outputs.

    Safety guarantee: on any exit (normal, exception, or signal), all fan
    controls are restored to BIOS/automatic mode via atexit and signal handlers.

    Supports live config reloading via file watching or manual trigger.
    """

    def __init__(
        self,
        config_path: Path = DEFAULT_CONFIG_PATH,
        auto_reload: bool = True,
    ):
        self.config_path = Path(config_path)
        self._running = False
        self._hw = None
        self._curves: dict[str, FanCurve] = {}
        self._cfg: Config | None = None
        self._auto_reload = auto_reload
        self._watcher: ConfigWatcher | None = None
        self._config_error: Exception | None = None

    # ── Setup / teardown ──────────────────────────────────────────────

    def _load_config(self) -> Config:
        logger.info(f"Loading config from {self.config_path}")
        return Config.load(self.config_path)

    def _validate_config(self, cfg: Config) -> list[str]:
        """Validate a config and return a list of error messages.

        Args:
            cfg: Config to validate

        Returns:
            List of error messages (empty if config is valid)
        """
        errors = []

        # Validate fan curve references
        for fan_name, fan in cfg.fans.items():
            try:
                special = parse_curve(fan.curve)
                if special is None and fan.curve not in cfg.curves:
                    errors.append(
                        f"Fan '{fan_name}' references unknown curve '{fan.curve}'"
                    )
            except InvalidCurveError as e:
                errors.append(f"Fan '{fan_name}' has invalid curve '{fan.curve}': {e}")

            # Validate aggregation method
            valid_methods = get_valid_aggregation_methods()
            if fan.aggregation not in valid_methods:
                errors.append(
                    f"Fan '{fan_name}' has invalid aggregation '{fan.aggregation}'. "
                    f"Valid options: {valid_methods}"
                )

            # Validate temperature sensors list
            if not fan.temp_ids:
                errors.append(f"Fan '{fan_name}' has no temperature sensors configured")

        # Validate poll interval
        if cfg.poll_interval <= 0:
            errors.append(f"poll_interval must be positive (got {cfg.poll_interval})")
        if cfg.poll_interval < 0.1:
            errors.append(
                f"poll_interval {cfg.poll_interval}s is too short (minimum 0.1s)"
            )

        return errors

    def reload_config(self) -> bool:
        """Reload and apply new configuration.

        Validates the new config before applying. If validation fails,
        the current configuration is kept and an error is logged.

        Returns:
            True if config was reloaded successfully, False otherwise
        """
        logger.info("Reloading configuration...")

        try:
            new_cfg = self._load_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config_error = e
            return False

        # Validate the new config
        errors = self._validate_config(new_cfg)
        if errors:
            logger.error("Config validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            self._config_error = ValueError("; ".join(errors))
            return False

        # Apply the new config
        try:
            self._cfg = new_cfg
            self._curves = self._build_curves(new_cfg)
            self._config_error = None
            logger.info("Configuration reloaded successfully")
            logger.info(
                f"  Fans: {len(new_cfg.fans)}, "
                f"Curves: {len(new_cfg.curves)}, "
                f"Poll interval: {new_cfg.poll_interval}s"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to apply config: {e}")
            self._config_error = e
            return False

    def _start_watcher(self):
        """Start the config file watcher if auto-reload is enabled."""
        if not self._auto_reload:
            logger.debug("Auto-reload disabled, not starting config watcher")
            return

        if not ConfigWatcher.is_available():
            logger.warning(
                "Live config reloading not available. "
                "Install watchdog: uv pip install watchdog"
            )
            return

        def _on_reload() -> None:
            self.reload_config()
            return None

        self._watcher = ConfigWatcher(
            config_path=self.config_path,
            on_reload=_on_reload,
            on_error=lambda e: logger.error(f"Config watcher error: {e}"),
        )

        if self._watcher.start():
            logger.info("Config auto-reload enabled (edit config.yaml to trigger)")
        else:
            logger.warning("Failed to start config watcher")
            self._watcher = None

    def _stop_watcher(self):
        """Stop the config file watcher."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

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

    def _get_curve(self, curve_name: str) -> FanCurve | StaticCurve | None:
        """Get a curve by name, handling special curves dynamically.

        Special curves ("off", "on", numeric percentages) are resolved
        on-the-fly without requiring config entries.

        Args:
            curve_name: The name of the curve to look up.

        Returns:
            FanCurve or StaticCurve instance, or None if not found.
        """
        # Check if it's a special curve first
        try:
            special = parse_curve(curve_name)
            if special is not None:
                return special
        except InvalidCurveError as e:
            logger.error(f"Invalid curve '{curve_name}': {e}")
            return None

        # Fall back to config curves
        return self._curves.get(curve_name)

    def _run_once(self, cfg: Config) -> dict[str, float]:
        """Perform a single control pass. Returns {fan_name: speed_percent}."""
        applied: dict[str, float] = {}

        temps = self._hw.get_temperatures()

        for fan_name, fan_cfg in cfg.fans.items():
            curve = self._get_curve(fan_cfg.curve)
            if curve is None:
                logger.warning(
                    f"Fan '{fan_name}': curve '{fan_cfg.curve}' not found, skipping."
                )
                continue

            # Aggregate temperatures from multiple sensors
            agg_temp = lookup_and_aggregate(
                fan_cfg.temp_ids, temps, fan_cfg.aggregation
            )

            if agg_temp is None:
                logger.warning(
                    f"Fan '{fan_name}': no temperature readings from sensors {fan_cfg.temp_ids}. "
                    "Is the daemon running as Administrator?"
                )
                continue

            if agg_temp == 0.0:
                # LHM sometimes returns 0.0 for unavailable sensors (not None)
                logger.debug(
                    f"Fan '{fan_name}': aggregated temperature is 0.0°C — skipping this pass."
                )
                continue

            target_pct = curve.evaluate(agg_temp)

            try:
                self._hw.set_fan_speed(fan_cfg.fan_id, target_pct)
                applied[fan_name] = target_pct
                # Log aggregation info for multi-sensor fans
                if len(fan_cfg.temp_ids) > 1:
                    logger.debug(
                        f"Fan '{fan_name}': {len(fan_cfg.temp_ids)} sensors "
                        f"({fan_cfg.aggregation}) = {agg_temp:.1f}°C → {target_pct:.1f}%"
                    )
                else:
                    logger.debug(
                        f"Fan '{fan_name}': {agg_temp:.1f}°C → {target_pct:.1f}%"
                    )
            except Exception as e:
                logger.error(f"Fan '{fan_name}': failed to set speed: {e}")

        return applied

    # ── Public API ────────────────────────────────────────────────────

    def run_once(self) -> dict[str, float]:
        """Perform a single evaluation pass and return applied speeds.

        Opens hardware, runs one control pass, then closes hardware.
        Useful for testing configuration without starting the daemon loop.
        """
        if self._cfg is None:
            if not self.reload_config():
                raise RuntimeError("Failed to load configuration")

        assert self._cfg is not None, "Config should be loaded after reload_config"

        self._hw = self._open_hardware()
        try:
            # Do an initial scan to populate the control map
            self._hw.scan()
            result = self._run_once(self._cfg)
        finally:
            self._hw.restore_defaults()
            self._hw.close()
            self._hw = None
        return result

    def run(self):
        """Start the main fan control loop. Blocks until stopped.

        Restores BIOS fan control on exit in all cases.
        Supports live config reloading via file watcher.
        """
        logger.info("pysysfan daemon starting...")

        # Initial config load
        if not self.reload_config():
            logger.error("Failed to load initial configuration, aborting")
            return

        cfg = self._cfg
        self._check_for_updates(cfg)
        self._register_safety_handlers()
        self._start_watcher()

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
                # Get current config (may have been reloaded)
                current_cfg = self._cfg if self._cfg is not None else cfg

                try:
                    applied = self._run_once(current_cfg)
                    if applied:
                        status = ", ".join(f"{k}={v:.0f}%" for k, v in applied.items())
                        logger.info(f"Applied: {status}")
                except Exception as e:
                    logger.error(f"Control loop error: {e}", exc_info=True)

                time.sleep(current_cfg.poll_interval)

        finally:
            logger.info("Restoring BIOS fan control and shutting down...")
            self._hw.restore_defaults()
            self._hw.close()
            self._hw = None
            logger.info("Daemon stopped.")
