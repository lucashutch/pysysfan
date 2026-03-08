"""Fan control daemon — the main control loop."""

from __future__ import annotations

import atexit
import logging
import os
import signal
import threading
import time
from pathlib import Path

from pysysfan.api.auth import get_or_create_token
from pysysfan.api.state import StateManager
from pysysfan.cache import HardwareCacheManager, get_default_cache_manager
from pysysfan.config import Config, DEFAULT_CONFIG_PATH
from pysysfan.curves import FanCurve, StaticCurve, parse_curve, InvalidCurveError
from pysysfan.notifications import NotificationManager
from pysysfan.profiles import ProfileManager, DEFAULT_PROFILE_NAME
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
        cache_manager: HardwareCacheManager | None = None,
        api_enabled: bool = True,
        api_host: str = "127.0.0.1",
        api_port: int = 8765,
    ):
        # Use active profile if no explicit config_path provided
        config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        if config_path == DEFAULT_CONFIG_PATH:
            # Check for active profile
            pm = ProfileManager()
            active_profile = pm.get_active_profile()
            config_path = pm.get_profile_config_path(active_profile)

        self.config_path = config_path
        self._running = False
        self._hw = None
        self._curves: dict[str, FanCurve] = {}
        self._cfg: Config | None = None
        self._auto_reload = auto_reload
        self._watcher: ConfigWatcher | None = None
        self._config_error: Exception | None = None
        self._cache_manager = cache_manager or get_default_cache_manager()
        self._unconfigured_fans: set[str] = set()
        self._update_thread: threading.Thread | None = None

        # API server settings
        self._api_enabled = api_enabled
        self._api_host = api_host
        self._api_port = api_port
        self._api_server = None
        self._api_thread: threading.Thread | None = None
        self._state_manager = StateManager()
        self._start_time: float = 0.0

        # Notification manager
        self._notification_manager = NotificationManager()

    def stop(self) -> None:
        """Stop the daemon gracefully.

        This method sets the running flag to False, which will cause
        the main loop to exit and cleanup to occur.
        """
        logger.info("Stopping daemon via API request...")
        self._running = False

    @property
    def notification_manager(self) -> NotificationManager:
        """Get the notification manager instance."""
        return self._notification_manager

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
        import time as time_module

        t0 = time_module.perf_counter()
        from pysysfan.hardware import HardwareManager

        t1 = time_module.perf_counter()
        logger.debug(f"[TIMING] Import HardwareManager: {t1 - t0:.3f}s")

        hw = HardwareManager()
        hw.open()
        t2 = time_module.perf_counter()
        logger.debug(f"[TIMING] hw.open(): {t2 - t0:.3f}s")

        return hw

    def _use_cached_scan(self):
        """Use cached scan results if available, otherwise perform a new scan."""
        import time as time_module

        t0 = time_module.perf_counter()

        self._cache_manager.load()
        fingerprint = self._hw.get_hardware_fingerprint()
        t1 = time_module.perf_counter()
        logger.debug(f"[TIMING] get_hardware_fingerprint(): {t1 - t0:.3f}s")
        logger.debug(f"Hardware fingerprint: {fingerprint[:16]}...")

        if self._cache_manager.is_valid(fingerprint):
            cached_result = self._cache_manager.get_cached_scan_result()
            if cached_result:
                t2 = time_module.perf_counter()
                logger.debug(f"[TIMING] Cache hit: {t2 - t0:.3f}s")
                logger.info("Using cached hardware scan results")
                return cached_result

        t2 = time_module.perf_counter()
        logger.debug(f"[TIMING] Cache miss check: {t2 - t0:.3f}s")
        logger.info("Performing full hardware scan...")
        scan_result = self._hw.scan()
        t3 = time_module.perf_counter()
        logger.debug(f"[TIMING] hw.scan(): {t3 - t0:.3f}s")

        from pysysfan.cache import HardwareCache

        cache = HardwareCache.from_scan_result(fingerprint, scan_result)
        self._cache_manager.save(cache)
        logger.info("Hardware scan results cached")

        return scan_result

    def _initialize_unconfigured_fans(self, scan_result) -> None:
        """Set all unconfigured fans to 0% to prevent unintended behavior.

        Fans that are controllable but not configured in the config file
        are set to 0% (off) by default. This ensures no unexpected fan
        behavior from hardware left in BIOS-controlled mode.
        """
        if self._cfg is None:
            return

        configured_fan_ids = {fan.fan_id for fan in self._cfg.fans.values()}

        unconfigured = [
            ctrl.identifier
            for ctrl in scan_result.controls
            if ctrl.has_control and ctrl.identifier not in configured_fan_ids
        ]

        if not unconfigured:
            return

        logger.info(f"Setting {len(unconfigured)} unconfigured fan(s) to 0%")
        self._unconfigured_fans.clear()

        for fan_id in unconfigured:
            try:
                self._hw.set_fan_speed(fan_id, 0.0)
                self._unconfigured_fans.add(fan_id)
                logger.debug(f"Unconfigured fan '{fan_id}' set to 0%")
            except Exception as e:
                logger.warning(f"Failed to set unconfigured fan '{fan_id}' to 0%: {e}")

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
        """Check for a newer pysysfan release (runs in background thread).

        This method is designed to run in a background thread during startup
        to avoid blocking hardware initialization.
        """
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
                    "Auto-updating pysysfan: %s → %s",
                    info.current_version,
                    info.latest_version,
                )
                perform_update(info.latest_version)
        except Exception as exc:
            logger.debug("Update check failed (non-fatal): %s", exc)

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

    def _check_notifications(self, temps: list) -> None:
        """Check alert rules against current temperature readings."""
        sensor_readings: dict[str, float] = {}
        for sensor in temps:
            sensor_readings[sensor.identifier] = sensor.value

        alerts = self._notification_manager.check(sensor_readings)
        for alert in alerts:
            logger.warning(f"ALERT: {alert.message}")

    def _run_once(self, cfg: Config) -> dict[str, float]:
        """Perform a single control pass. Returns {fan_name: speed_percent}."""
        applied: dict[str, float] = {}

        temps = self._hw.get_temperatures()

        self._check_notifications(temps)

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

            # Handle allow_fan_off setting
            if target_pct <= 0 and not fan_cfg.allow_fan_off:
                # When fan off is disabled, use minimum speed instead
                target_pct = 1.0  # Minimum non-zero speed

            try:
                self._hw.set_fan_speed(fan_cfg.fan_id, target_pct)
                applied[fan_name] = target_pct

                # Log fan state change with special handling for off mode
                if target_pct <= 0:
                    logger.debug(f"Fan '{fan_name}': turned OFF (0% target)")
                elif len(fan_cfg.temp_ids) > 1:
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

    # ── API Server ────────────────────────────────────────────────────

    def _start_api_server(self) -> None:
        """Start FastAPI server in background thread."""
        if not self._api_enabled:
            return

        # Initialize API token
        token = get_or_create_token()
        logger.info(f"API token: {token[:8]}...{token[-8:]}")

        from pysysfan.api.server import create_app
        import uvicorn

        app = create_app(daemon=self, state=self._state_manager)

        config = uvicorn.Config(
            app,
            host=self._api_host,
            port=self._api_port,
            log_level="warning",
            access_log=False,
        )

        self._api_server = uvicorn.Server(config)
        self._api_thread = threading.Thread(
            target=self._api_server.run,
            daemon=True,
            name="APIServer",
        )
        self._api_thread.start()

        logger.info(f"API server started on http://{self._api_host}:{self._api_port}")

    def _stop_api_server(self) -> None:
        """Stop the API server."""
        if self._api_server is not None:
            logger.info("Stopping API server...")
            self._api_server.should_exit = True
            if self._api_thread and self._api_thread.is_alive():
                self._api_thread.join(timeout=5.0)
            self._api_server = None
            self._api_thread = None

    def _update_state(self) -> None:
        """Update state manager with current daemon state."""
        # Get active profile name
        try:
            pm = ProfileManager()
            active_profile = pm.get_active_profile()
        except Exception:
            active_profile = DEFAULT_PROFILE_NAME

        self._state_manager.update_state(
            pid=os.getpid(),
            config_path=str(self.config_path),
            started_at=self._start_time,
            running=self._running,
            uptime_seconds=time.time() - self._start_time,
            last_poll_time=time.time(),
            last_error=str(self._config_error) if self._config_error else None,
            poll_interval=self._cfg.poll_interval if self._cfg else 2.0,
            fans_configured=len(self._cfg.fans) if self._cfg else 0,
            curves_configured=len(self._cfg.curves) if self._cfg else 0,
            active_profile=active_profile,
            current_temps={},  # Populated in _run_once
            current_fan_speeds={},
            current_targets={},
            auto_reload_enabled=self._auto_reload,
            api_enabled=self._api_enabled,
            api_port=self._api_port,
        )

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
            scan_result = self._use_cached_scan()
            self._initialize_unconfigured_fans(scan_result)
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

        startup_t0 = time.perf_counter()
        self._start_time = time.time()

        # Initial config load
        if not self.reload_config():
            logger.error("Failed to load initial configuration, aborting")
            return

        cfg = self._cfg

        # Start update check in background thread (non-blocking)
        if cfg and cfg.update.auto_check:
            self._update_thread = threading.Thread(
                target=self._check_for_updates,
                args=(cfg,),
                name="UpdateChecker",
                daemon=True,
            )
            self._update_thread.start()
            logger.debug("Started update check in background thread")

        self._register_safety_handlers()

        # Initialize hardware (runs in parallel with update check)
        self._hw = self._open_hardware()

        # Start API server
        self._start_api_server()

        try:
            scan_result = self._use_cached_scan()
            logger.info(
                f"Hardware scan found: {len(scan_result.temperatures)} temps, "
                f"{len(scan_result.fans)} fans, "
                f"{sum(1 for c in scan_result.controls if c.has_control)} controllable outputs"
            )

            self._initialize_unconfigured_fans(scan_result)

            # Start config watcher after hardware is ready
            self._start_watcher()

            # Wait for update check to complete (with timeout)
            if self._update_thread and self._update_thread.is_alive():
                logger.debug("Waiting for update check to complete...")
                self._update_thread.join(timeout=5.0)
                if self._update_thread.is_alive():
                    logger.debug("Update check still running, continuing anyway")

            self._running = True
            startup_duration = time.perf_counter() - startup_t0
            logger.info(f"Startup completed in {startup_duration:.1f}s")
            logger.info(f"Control loop started (poll interval: {cfg.poll_interval}s)")

            while self._running:
                # Update daemon state for API
                self._update_state()
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
            self._stop_api_server()
            logger.info("Daemon stopped.")
