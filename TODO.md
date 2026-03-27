# TODO
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
