# TODO

## Completed

- [x] Desktop UI phase: graph hover summaries, column-major graph legend flow, accordion affordance, and colored service action buttons.

## Bug Fixes

- rework the config ui to more closely match the flat square aesthetic of the rest of the dashboard or service page
- pawnio version is incorrectly being obtained. i have 2.2 installed but the ui is showing 1.2
- fix alignment fo diagnostic logs. it should be the same as the serivce running indicator in the left panel.

---

## New Features

- **[!] Minimum fan PWM** - Add `min_pwm` to `FanConfig`, applied whenever the curve output is above 0%. Add a CLI command that ramps PWM from 0% upward to detect each fan's spin-up threshold and surface this in the GUI curve configuration flow.
- **Windows toast notifications for alerts** - Emit a native Windows toast via `winrt`/`winsdk` when a `high_temp` or `fan_failure` alert fires, wired into `NotificationManager` as an optional output channel alongside the existing in-process history.
- **Auto-profile switching on power state** - Extend `ProfileMetadata.rules` to support `on_battery`, `plugged_in`, and time-of-day conditions. Add a background watcher in the daemon that activates the matching profile and logs the switch to the state file.
- **Sensor sanity checks and dead-sensor detection** - Add `sensor_timeout_seconds` to `FanConfig`. If a sensor returns `None` or an impossible value (e.g. 0 C or > 110 C) beyond the timeout, log a warning, optionally raise an alert, and fall back to a configured safe speed.
- **Config import/export wizard in the GUI** - Add Import/Export buttons to `CurvesPage`. The import flow validates the incoming YAML against daemon rules and shows a human-readable diff before writing to disk.
- **Per-fan speed ramping rate limits** - Add `ramp_up_rate` and `ramp_down_rate` (percent/second) to `FanConfig` so speed transitions are audibly smoother when hysteresis alone is insufficient.
=======
# TODO

## Bug Fixes

- [x] **Temperature graph stops working** — Fixed by eliminating per-refresh theme application and implementing PlotDataItem reuse via `update_series()`/`setData()` pattern.

---

## Performance Enhancements

- [x] **Lazy CLR runtime initialisation** — `lhm/__init__.py` now performs CLR and assembly initialization only on the first `load_lhm()` call and caches the loaded hardware namespace for reuse.

- [x] **Skip state file write when nothing has changed** — The daemon now hashes a normalized snapshot payload and skips `write_state()` when only volatile fields (timestamp/uptime) changed.

- [x] **Selective LHM hardware `Update()` per poll cycle** — The daemon now passes configured sensor/control IDs to `WindowsHardwareManager`, which updates only matching hardware nodes each poll cycle.

- [x] **Dashboard diff-read for state and history files** — The desktop local backend now caches file `mtime` and reuses parsed state/history payloads when unchanged.

- [x] **Pre-sort and cache temp sensor lookup index** — The daemon now builds a per-cycle `identifier → SensorInfo` map once and passes it into `lookup_and_aggregate()` for O(1) lookups.

- [x] **Reduce GUI idle polling** — Dashboard polling remains disabled while hidden and now scales refresh intervals dynamically for active, idle/unchanged, and offline states.

---

## New Features

- [x] **Dashboard UI rework** — Redesigned dashboard with V2 row-based layout (header bar, health summary, table rows with accent bars), G5 tabbed-focus graphs page (interactive legend, Temperature/Fan RPM tabs, plot item reuse), and shared DashboardDataProvider.

- [ ] **Flatten the rest of the UI** — Rework the remaining desktop pages and shared chrome to match the flatter dashboard aesthetic.

- **[!] Minimum fan PWM** — Add `min_pwm` to `FanConfig`, applied whenever the curve output is above 0%. Add a CLI command that ramps PWM from 0% upward to detect each fan's spin-up threshold and surface this in the GUI curve configuration flow.

- **Windows toast notifications for alerts** — Emit a native Windows toast via `winrt`/`winsdk` when a `high_temp` or `fan_failure` alert fires, wired into `NotificationManager` as an optional output channel alongside the existing in-process history.

- **Auto-profile switching on power state** — Extend `ProfileMetadata.rules` to support `on_battery`, `plugged_in`, and time-of-day conditions. Add a background watcher in the daemon that activates the matching profile and logs the switch to the state file.

- **Sensor sanity checks and dead-sensor detection** — Add `sensor_timeout_seconds` to `FanConfig`. If a sensor returns `None` or an impossible value (e.g. 0 °C or > 110 °C) beyond the timeout, log a warning, optionally raise an alert, and fall back to a configured safe speed.

- **Config import/export wizard in the GUI** — Add Import/Export buttons to `CurvesPage`. The import flow validates the incoming YAML against daemon rules and shows a human-readable diff before writing to disk.

- **Per-fan speed ramping rate limits** — Add `ramp_up_rate` and `ramp_down_rate` (percent/second) to `FanConfig` so speed transitions are audibly smoother when hysteresis alone is insufficient.
>>>>>>> 742ebe7 (test(gui): cleanup dead code and update TODO)
