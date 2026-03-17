# TODO

## Bug Fixes

- **[!] `config.py` — silent curve loss on boolean/string key collision** — If a YAML file contains both `on: ...` (parsed as `True`) and `"on": ...`, the normalisation loop silently renames one, making it inaccessible to any fan referencing it. Detect and raise a `ValueError` listing the conflicting keys instead.

- **[!] `curves.py` — hysteresis `_last_temp` not reset on speed increases** — When temperature holds steady at a new peak, `_last_speed` updates but `_last_temp` does not advance, silently shifting the hysteresis band down each call. Reset `_last_temp` whenever `target_speed >= _last_speed`.

- **`service_entry.py` — file handle leak on log redirect** — `_redirect_stdio()` opens the log file with a bare `open()` call without ever closing it on error paths before the daemon loop. Replace with a context manager or `atexit` cleanup.

- **`platforms/windows_service.py` — `subprocess.os.name` undefined** — The guard `if subprocess.os.name != "nt"` relies on an undocumented internal attribute. Replace with `import os; if os.name != "nt"`.

- **`lhm/download.py` — full asset loaded into memory before ZIP extraction** — `resp.content` reads the entire download (often 10+ MB) into one `bytes` object before extracting. Stream via `iter_content` into a `BytesIO` or temp file instead to avoid the memory spike.

- **`history_file.py` — history file grows unboundedly between compaction runs** — At a 0.1 s poll interval the file can grow ~50 KB/min before compaction fires. Enforce a max file size or line count in `append_history_sample` and compact if history is too large.

- **`daemon.py` — `_unconfigured_fans` not cleared on config reload** — After a hot-reload that removes a fan, its identifier remains in `_unconfigured_fans` forever, causing spurious warnings. Clear the set inside `reload_config()` before rebuilding curves.

- **`local_backend.py` — `_hidden_process_kwargs` duplicated from `windows_service.py`** — Extract the shared helper to `platforms/_process.py` to avoid divergence.

- **`cache.py` — cache fingerprint missing LHM version** — If the LHM DLL is replaced but the hardware layout is identical, stale cached data is served. Include the DLL modification timestamp or `.lhm_version` in the fingerprint.

- **`notifications.py` — alert history exceeds `_max_history` on multi-rule fire** — The history trim runs after each individual append inside a loop. Move it to after the loop so it runs exactly once per `check()` call.

---

## Performance Enhancements

- **[!] Lazy CLR runtime initialisation** — `lhm/__init__.py` calls `_ensure_clr()` at import time, adding ~200 ms to any CLI subcommand that touches `pysysfan.hardware`. Defer until the first `load_lhm()` call inside `WindowsHardwareManager.open()`.

- **Skip state file write when nothing has changed** — The daemon calls `write_state()` every poll cycle. Add an equality check against the last written snapshot and skip the atomic write when the payload is unchanged.

- **Selective LHM hardware `Update()` per poll cycle** — Build a set of required hardware nodes from the active config at load time and only call `Update()` on those nodes each cycle, skipping unused hardware.

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