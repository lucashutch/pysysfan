# TODO

## New Features

- **[!] Minimum fan PWM** - Add `min_pwm` to `FanConfig`, applied whenever the curve output is above 0%. Add a CLI command that ramps PWM from 0% upward to detect each fan's spin-up threshold and surface this in the GUI curve configuration flow.
- **Windows toast notifications for alerts** - Emit a native Windows toast via `winrt`/`winsdk` when a `high_temp` or `fan_failure` alert fires, wired into `NotificationManager` as an optional output channel alongside the existing in-process history.
- **Auto-profile switching on power state** - Extend `ProfileMetadata.rules` to support `on_battery`, `plugged_in`, and time-of-day conditions. Add a background watcher in the daemon that activates the matching profile and logs the switch to the state file.
- **Sensor sanity checks and dead-sensor detection** - Add `sensor_timeout_seconds` to `FanConfig`. If a sensor returns `None` or an impossible value (e.g. 0 C or > 110 C) beyond the timeout, log a warning, optionally raise an alert, and fall back to a configured safe speed.
- **Config import/export wizard in the GUI** - Add Import/Export buttons to `CurvesPage`. The import flow validates the incoming YAML against daemon rules and shows a human-readable diff before writing to disk.
- **Per-fan speed ramping rate limits** - Add `ramp_up_rate` and `ramp_down_rate` (percent/second) to `FanConfig` so speed transitions are audibly smoother when hysteresis alone is insufficient.

## UI Redesign
- **[x] Config tab color/styling** - Phase 1 (preview accent + tooltip card styling)
- **[x] Config tab color/styling** - Phase 2 (accordion cards)
- **[x] Config tab color/styling** - Phase 3 (points table)

## UI Redesign Follow-ups
- **[x] Desktop font switchover** - Updated the native GUI to prefer IBM Plex Mono with Inter as fallback and added IBM Plex Mono provisioning to the Windows installer.
- **[x] Config tab behavior + polish** - Fix accordion initial state, integer table + labeling, hover tooltip follows cursor, dropdown border removal, and save/delete button accents.
- **[x] Config tab dropdown arrow polish** - Match the arrow background to the combo box and switch to a larger SVG chevron for clearer affordance.
- **[x] Dashboard hierarchy + label polish** - Improve desktop typography, split dashboard sensor names and values into separate columns, humanize sensor/fan labels, add raw-name tooltips, and align curve/actual accents with the redesign mockup.
- **[x] Sidebar compact tuning** - Reduce sidebar text sizes, enlarge the running line, move notifications to the footer, flatten the alerts button, and keep the left rail visually compact.

- **[x] Config tab curve points accordion clipping fix** - Set points table/accordion minimum height to prevent the table from collapsing when other accordions are expanded.
