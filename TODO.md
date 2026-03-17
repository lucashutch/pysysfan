# TODO

## Bug Fixes


---

## Performance Enhancements

- [x] **Lazy CLR runtime initialisation** — `lhm/__init__.py` now performs CLR and assembly initialization only on the first `load_lhm()` call and caches the loaded hardware namespace for reuse.

- [x] **Skip state file write when nothing has changed** — The daemon now hashes a normalized snapshot payload and skips `write_state()` when only volatile fields (timestamp/uptime) changed.

- [x] **Selective LHM hardware `Update()` per poll cycle** — The daemon now passes configured sensor/control IDs to `WindowsHardwareManager`, which updates only matching hardware nodes each poll cycle.

- **Dashboard diff-read for state and history files** — Cache each file's `mtime` and skip full deserialisation when the file has not changed, halving file I/O on the GUI process during idle.

- **Pre-sort and cache temp sensor lookup index** — `lookup_and_aggregate()` does a linear scan over all sensors every poll cycle. Build an `identifier → SensorInfo` dict once per `read_sensors()` call for O(1) lookups.

- **Reduce GUI idle polling** — Ensure the dashboard does not refresh or poll the daemon state when the window is not visible or the daemon is idle. Consider dynamic poll-interval scaling based on system activity.

---

## New Features

- **[!] Dashboard UI rework** — Redesign the dashboard with a compact header bar (daemon status, active profile, uptime, fan count), a responsive fan card grid, collapsible temperature/fan sections, an at-a-glance system health row (highest temp, highest fan speed vs. thresholds), and an improved graph with axis labels, per-series colour legends, and a visible time-range control.

- **[!] Minimum fan PWM** — Add `min_pwm` to `FanConfig`, applied whenever the curve output is above 0%. Add a CLI command that ramps PWM from 0% upward to detect each fan's spin-up threshold and surface this in the GUI curve configuration flow.

- **Windows toast notifications for alerts** — Emit a native Windows toast via `winrt`/`winsdk` when a `high_temp` or `fan_failure` alert fires, wired into `NotificationManager` as an optional output channel alongside the existing in-process history.

- **Auto-profile switching on power state** — Extend `ProfileMetadata.rules` to support `on_battery`, `plugged_in`, and time-of-day conditions. Add a background watcher in the daemon that activates the matching profile and logs the switch to the state file.

- **Sensor sanity checks and dead-sensor detection** — Add `sensor_timeout_seconds` to `FanConfig`. If a sensor returns `None` or an impossible value (e.g. 0 °C or > 110 °C) beyond the timeout, log a warning, optionally raise an alert, and fall back to a configured safe speed.

- **Config import/export wizard in the GUI** — Add Import/Export buttons to `CurvesPage`. The import flow validates the incoming YAML against daemon rules and shows a human-readable diff before writing to disk.

- **Per-fan speed ramping rate limits** — Add `ramp_up_rate` and `ramp_down_rate` (percent/second) to `FanConfig` so speed transitions are audibly smoother when hysteresis alone is insufficient.