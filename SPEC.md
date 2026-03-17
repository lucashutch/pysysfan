# PySysFan — Technical Specification

## Overview

PySysFan is a Windows-first, Python-based fan control system that drives motherboard and chassis fan headers based on user-defined temperature-response curves. It wraps **LibreHardwareMonitor** (LHM) via `pythonnet` for hardware sensor access, uses **Windows Task Scheduler** for headless startup, and ships an optional **PySide6 + pyqtgraph** desktop GUI for live monitoring and configuration.

### Goals

- Give users precise, curve-based control over fan speeds without BIOS-level restrictions.
- Run invisibly in the background as a windowless scheduled task.
- Provide a native desktop GUI that reads direct file state rather than an embedded HTTP server.
- Stay safe: always restore BIOS auto-control on exit, error, or crash.

### Non-Goals

- Linux / macOS support (currently out of scope; base abstractions exist for future extension).
- Kubernetes, containers, or multi-machine fan management.
- Firmware replacement — PySysFan operates purely in software above the OS HAL.

---

## Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11+ | `match` statements, `slots=True` dataclasses, modern type hints |
| Hardware bridge | `pythonnet` + LHM (net472) | .NET Framework 4.7.2 is pre-installed on Win 10/11; avoids .NET Core runtime dependency |
| Low-level driver | PawnIO | Required by LHM for ring-0 SMBus / Super I/O access |
| CLI framework | Click | Composable command groups, auto-generated help |
| Rich output | `rich` | Coloured tables and panels in the terminal |
| Config format | YAML (`pyyaml`) | Human-readable, supports comments |
| File watching | `watchdog` | Filesystem events for live config reload |
| GUI toolkit | PySide6 (Qt 6) | First-class Windows integration, official LGPL Qt bindings |
| Plotting | `pyqtgraph` | High-performance OpenGL-backed real-time charting |
| Packaging | `uv` + `hatchling` + `hatch-vcs` | Fast installs, VCS-based versioning |
| CI / lint | `ruff`, `pytest` | Single-tool linting + type-aware formatting |

---

## Repository Layout

```
pysysfan/
├── src/pysysfan/          # Main package
│   ├── cli.py             # Click CLI entry point
│   ├── hardware.py        # Re-export shim (WindowsHardwareManager → HardwareManager)
│   ├── config.py          # YAML config loading and dataclasses
│   ├── curves.py          # Fan curve evaluation (linear interpolation + hysteresis)
│   ├── daemon.py          # Fan control loop (FanDaemon)
│   ├── temperature.py     # Multi-sensor aggregation (max/min/avg/median)
│   ├── state_file.py      # Atomic JSON state snapshot (daemon → GUI IPC)
│   ├── history_file.py    # Rolling NDJSON history (daemon → GUI trend data)
│   ├── cache.py           # Hardware scan result cache (~/.pysysfan/hardware_cache.json)
│   ├── notifications.py   # Alert rules and in-process alert history
│   ├── profiles.py        # Multi-profile config management
│   ├── watcher.py         # Config file watcher (watchdog-backed, debounced)
│   ├── updater.py         # GitHub release check + uv tool upgrade
│   ├── service_entry.py   # Windowless gui-script entry point for Task Scheduler
│   ├── install.py         # Standalone LHM / PawnIO installer entry points
│   ├── platforms/
│   │   ├── base.py        # Abstract hardware interface (SensorInfo, ControlInfo, etc.)
│   │   ├── windows.py     # WindowsHardwareManager (LHM via pythonnet)
│   │   └── windows_service.py  # Windows Task Scheduler CRUD (XML task definition)
│   ├── lhm/
│   │   ├── __init__.py    # DLL path resolution + pythonnet/CLR loader
│   │   └── download.py    # GitHub release scraper + ZIP extractor
│   ├── pawnio/
│   │   ├── __init__.py    # Driver detection
│   │   └── download.py    # PawnIO setup.exe downloader
│   └── gui/
│       ├── __init__.py    # Lazy-load shim (avoids importing PySide6 on CLI usage)
│       ├── __main__.py    # python -m pysysfan.gui entry point
│       └── desktop/
│           ├── app.py         # QApplication bootstrap + TrayController
│           ├── main_window.py # MainWindow (tab host, tray integration)
│           ├── dashboard_page.py  # Live monitoring Dashboard tab
│           ├── curves_page.py     # Config / curve editor tab
│           ├── service_page.py    # Service management tab
│           ├── local_backend.py   # File/config/service helpers (no HTTP)
│           ├── plotting.py        # DashboardPlotWidget, CurveEditorPlotWidget
│           ├── theme.py           # Palette-aware QSS stylesheets
│           ├── icons.py           # App icon helpers + Windows AppID
│           └── preferences.py    # Persisted user preferences (minimize-to-tray)
├── tests/                 # pytest suite (≥80% coverage enforced)
├── docs/                  # User-facing documentation
├── scripts/
│   └── install-pysysfan.bat  # One-click Windows installer
├── pyproject.toml
├── AGENTS.md              # AI agent workflow instructions
└── CONTRIBUTING.md
```

---

## Configuration System

### File Location

| Path | Purpose |
|---|---|
| `~/.pysysfan/config.yaml` | Default profile config |
| `~/.pysysfan/profiles/<name>.yaml` | Named profile config |
| `~/.pysysfan/profiles/<name>.meta.yaml` | Profile metadata (display name, description, rules) |
| `~/.pysysfan/active_profile` | Plain-text file recording the active profile name |

### Config Schema

```yaml
general:
  poll_interval: 1.0           # Control loop interval (seconds, minimum 0.1)

fans:
  cpu_fan:
    fan_id: "/lpc/.../fan/0"   # LHM sensor identifier for RPM reading
    curve: my_curve            # Curve name, or "on"/"off" special values
    temp_ids:                  # One or more temperature sensor identifiers
      - "/cpu/0/temperature/0"
    aggregation: max           # max | min | average | median
    header_name: "CPU Fan"     # Optional human label
    allow_fan_off: true        # When false, 0% maps to minimum speed not off

curves:
  my_curve:
    points:
      - [30, 0]                # [temperature °C, fan speed %]
      - [60, 40]
      - [80, 100]
    hysteresis: 2.0            # °C drop required before decreasing speed
```

### Key Design Decisions

- **YAML boolean coercion**: YAML parses `on`/`off` as booleans. The loader normalises these to their string forms before populating the curve/fan dicts, preventing mixed-type key bugs.
- **Backward compatibility**: `temp_id` (string) and `source` (legacy) are both accepted alongside the canonical `temp_ids` (list).
- **Multiple temp inputs per fan**: Any number of temperature sensors can drive a single fan, aggregated with a configurable method.

---

## Profile System

`ProfileManager` (`profiles.py`) provides CRUD over the `~/.pysysfan/profiles/` directory. Profiles are independent YAML configs; the active profile name is stored in `~/.pysysfan/active_profile`.

- When the daemon starts without an explicit `--config` flag it reads the active profile to determine which config YAML to load.
- The GUI `CurvesPage` allows switching profiles without restarting the daemon; the daemon picks up the change on the next config reload cycle.
- Profile metadata (display name, description, rule hooks for future auto-switching) lives in a sidecar `.meta.yaml` file.

---

## Hardware Abstraction Layer

### Class Hierarchy

```
BaseHardwareManager (ABC)
└── WindowsHardwareManager   ← current only implementation
```

`BaseHardwareManager` (`platforms/base.py`) declares the contract:

| Method | Purpose |
|---|---|
| `open()` | Load the driver/library and initialise hardware |
| `close()` | Restore BIOS auto-control and release resources |
| `scan()` | Return `HardwareScanResult` (temperatures, fans, controls) |
| `read_sensors()` | Return a refreshed `HardwareScanResult` without re-opening |
| `set_fan_speed(fan_id, pct)` | Set a controllable fan to a fixed percentage |
| `restore_defaults()` | Return all fan channels to automatic mode |

Context-manager support (`__enter__` / `__exit__`) is provided by the base class; it calls `open()` and `close()` automatically.

### WindowsHardwareManager

`platforms/windows.py` wraps LHM via `pythonnet`:

1. `_ensure_clr()` (in `lhm/__init__.py`) loads the `netfx` runtime before any `import clr` call.
2. `load_lhm()` adds the DLL directory to `sys.path`, adds the CLR reference, and returns the `LibreHardwareMonitor.Hardware` namespace.
3. An LHM `Computer` object is created with motherboard, CPU, GPU, storage, memory, and controller sensors enabled (network, PSU, battery disabled to reduce overhead).
4. `Computer.Open()` starts the LHM session.
5. `_update_all()` calls `hw.Update()` and `sub.Update()` on every hardware node before each sensor read.
6. Fan control is applied via `ISensor.Control.SetSoftware(pct)`. Channels not under soft control are tracked in `_off_mode_fans` so `restore_defaults()` can call `ResetControl()` selectively.

### Hardware Scan Cache

`cache.py` (`HardwareCacheManager`) stores the sensor topology (identifiers and names) to a JSON file (`~/.pysysfan/hardware_cache.json`). A fingerprint hash is computed from the scan result; on subsequent runs the cache is returned immediately if the fingerprint matches, avoiding a full re-scan. The runtime sensor values are never cached — only the topology.

---

## Fan Curve Engine

### FanCurve

`curves.py` implements piecewise-linear interpolation:

- Points are stored sorted by temperature.
- `bisect_right` locates the surrounding segment in O(log n).
- Values outside the range are clamped to the first/last point's speed.

**Hysteresis** prevents flapping when temperature oscillates around a threshold:
- If the new target speed would be *lower* than the last applied speed, the speed is only decreased if `current_temp` has fallen by at least `hysteresis` degrees below the temperature that last drove the speed up.
- `_last_speed` and `_last_temp` are instance state on each `FanCurve` object; they reset when curves are rebuilt on a config reload.

### StaticCurve

A simplified curve subtype that ignores temperature and always returns a fixed speed. Used for the built-in `"off"` (0%) and `"on"` (100%) special curve names, plus any `static:<pct>` expression resolved by `parse_curve()`.

### parse_curve()

`parse_curve(name)` resolves special curve names before looking up user-defined curves in the config, returning a `StaticCurve` for `"off"`, `"on"`, or `"static:<n>"`, or `None` for a name that should be looked up in the config dict.

---

## Daemon Control Loop

`FanDaemon` (`daemon.py`) is the core runtime loop:

```
FanDaemon.run()
  ├── _load_config()           # Read active profile YAML
  ├── _validate_config()       # Check curve references, poll interval, etc.
  ├── HardwareManager.open()   # Start LHM session
  ├── ConfigWatcher.start()    # Optional file-watch for live reload
  └── loop:
        hardware.read_sensors()       # Refresh all LHM sensor values
        lookup_and_aggregate()        # Aggregate temps per fan mapping
        FanCurve.evaluate(temp)       # Interpolate target speed
        hardware.set_fan_speed(...)   # Apply to LHM control
        write_state(...)              # Atomic JSON snapshot → state file
        append_history_sample(...)    # Append NDJSON line → history file
        compact_history() (periodic)  # Trim history file to max-age window
        NotificationManager.check()   # Evaluate alert rules
        sleep(poll_interval)
```

**Safety guarantee**: `atexit.register` and signal handlers for `SIGTERM`/`SIGINT` always call `restore_defaults()` so fans return to BIOS control on any exit path.

### Live Config Reload

`ConfigWatcher` (`watcher.py`) uses `watchdog.Observer` to watch the config file's directory for `FileModifiedEvent`. A 500 ms debounce timer prevents duplicate reloads on rapid successive writes. If `watchdog` is not installed, `ConfigWatcher` degrades gracefully; the daemon still works but live reload is unavailable without a manual trigger.

---

## Inter-Process Communication (IPC)

The GUI communicates with the daemon exclusively through files on disk. There is no embedded HTTP server, no Unix socket, and no Windows named pipe.

| File | Format | Written by | Read by |
|---|---|---|---|
| `~/.pysysfan/daemon_state.json` | Atomic JSON | Daemon (each poll cycle) | GUI, `pysysfan status` |
| `~/.pysysfan/daemon_history.ndjson` | Rolling NDJSON | Daemon (each poll cycle) | GUI dashboard plots |
| `~/.pysysfan/hardware_cache.json` | JSON | Daemon/scan on first run | Daemon startup |
| `~/.pysysfan/config.yaml` | YAML | GUI editor / user | Daemon |
| `~/.pysysfan/active_profile` | Plain text | GUI / CLI | Daemon |

**State file atomicity**: `write_state()` writes to a `.tmp` file in the same directory and uses `os.replace()` to swap it in, ensuring the GUI never reads a partially-written file.

**History compaction**: The daemon periodically calls `compact_history()`, which re-reads the NDJSON file and rewrites it keeping only samples newer than `DEFAULT_HISTORY_MAX_AGE_SECONDS` (15 minutes by default).

---

## Windows Service / Scheduled Task

`platforms/windows_service.py` manages a Windows Task Scheduler task named `pysysfan`:

- The task runs as the installing user with highest available privileges.
- The executable is `pysysfan-service.exe`, a `gui-scripts` entry point that uses the Windows GUI subsystem — no console window is ever created.
- The task definition is rendered as an XML string with `textwrap.dedent` and submitted via `schtasks.exe` or `Import-ScheduledTask` PowerShell.
- A generated launcher script is written to `~/.pysysfan/pysysfan-service.bat` so the task's `/TR` argument stays well under the 261-character Task Scheduler limit.
- `service_entry.py` sets up rotating file logging (`~/.pysysfan/service.log`, 5 MB max, 3 backups) and redirects `stdout`/`stderr` to the log file since there is no console attached.

---

## Desktop GUI Architecture

The GUI is an optional `[gui]` extra (`PySide6 >= 6.8`, `pyqtgraph >= 0.13`). The `pysysfan.gui` package is intentionally minimal — all imports of Qt types are deferred until `launch_gui()` is called, so the CLI never pays the PySide6 import cost.

### Application Bootstrap (`app.py`)

```
launch_gui()
  ├── get_or_create_application()   # QApplication singleton
  ├── MainWindow()
  ├── TrayController(app, window)   # Optional tray icon + context menu
  └── app.exec()
```

`TrayController` shows a system tray icon if available, sets `quitOnLastWindowClosed=False`, and wires up the context menu (Show, Hide, Refresh, Quit).

### MainWindow

`MainWindow` hosts three tabs in a `QTabWidget`:

| Tab | Class | Purpose |
|---|---|---|
| Dashboard | `DashboardPage` | Live sensor readings, fan speeds, trend graphs, daemon status |
| Config | `CurvesPage` | YAML config editor, fan curve editor, profile management |
| Service | `ServicePage` | Task Scheduler install/remove/start/stop, preferences |

The daemon status indicator and alerts badge are mounted as corner widgets in the top-right of the tab bar so they are always visible regardless of the active tab.

Minimize-to-tray behaviour is controlled by a persisted preference (`preferences.py`) and handled in `MainWindow.changeEvent` and `MainWindow.closeEvent`.

### DashboardPage

The Dashboard is the live monitoring hub:

- A 1-second `QTimer` polls the state file and history file while the page is visible; the timer is paused when the page is hidden to reduce background CPU usage.
- **Fan Summary cards**: Cards generated from the active config, each showing the fan name, live RPM, current target %, the driving temperature(s), and the assigned curve.
- **Trend plots** (via `DashboardPlotWidget`): Three stacked `pyqtgraph` plots — Temperature history, Fan RPM history, Fan target % history — sharing a time axis representing elapsed seconds (most recent = right edge).
- A history-window combo box selects the visible time span (60 s / 5 min / 15 min).
- Per-graph series visibility toggles are provided via `QToolButton` + `QMenu` controls, with defaults pre-selected based on the active config.
- A daemon health indicator (coloured dot) and alerts badge widget sit in the corner.

### CurvesPage

The Config/Curves editor:

- Loads the active profile config from disk.
- Left column: Fan assignment table (`QTableWidget`) showing fan name, fan sensor ID, curve, temp sensors, aggregation.
- Right column: Curve management — select a curve, edit its point table, preview the curve shape in a `CurveEditorPlotWidget`.
- `CurveEditorPlotWidget` supports drag/drop of points, crosshair tracking, and live re-interpolation preview using the pre-built `build_curve_preview_series()` helper.
- Saves changes by writing the modified `Config` back to the profile YAML.

### ServicePage

The Service tab:

- Displays task installed/enabled status, last run time, daemon PID, active profile, and config path.
- Buttons: Install Task, Remove Task, Start, Stop.
- Actions that require elevation spawn a re-launch with PowerShell `Start-Process -Verb RunAs` and show a clear UAC prompt message.
- Preference: `[x] Minimize to notification area instead of taskbar`.

### Local Backend (`local_backend.py`)

All GUI data access goes through `local_backend.py`, which provides stateless helper functions rather than a singleton:

| Helper | Description |
|---|---|
| `read_daemon_state()` | Read and deserialise `daemon_state.json` |
| `read_daemon_history()` | Read+filter `daemon_history.ndjson` |
| `load_profile_config()` | Load a named profile's YAML into a `Config` |
| `validate_config_model()` | Run daemon-equivalent validation rules |
| `run_service_command()` | Invoke `pysysfan service <action>` as a subprocess |
| `run_installer_command()` | Invoke `pysysfan-install-lhm` or `pysysfan-install-pawnio` |
| `check_admin()` | ctypes-based admin check |
| `get_profile_names()` | Return profiles sorted with active first |

### Theme System (`theme.py`)

All stylesheets are generated at runtime from the current `QPalette`:

- `desktop_colors()` computes a set of named colour tokens (window, base, muted, border, raised, panel, card, accent, graph) by blending palette roles at fixed ratios.
- Each page has a dedicated stylesheet function (`dashboard_page_stylesheet`, `management_page_stylesheet`, etc.) that interpolates the colour tokens into QSS strings.
- Dark/light mode is detected via `is_dark_palette()` (window lightness < 128).
- The stylesheet is re-applied on palette change events.
- `plot_theme()` returns a colour dict for the `pyqtgraph` plots to match the QSS theme.

---

## Notification / Alert System

`NotificationManager` (`notifications.py`) is embedded in the daemon and evaluates alert rules each poll cycle:

- Rules are defined by `AlertRule`: a sensor identifier, alert type (`high_temp` / `low_temp` / `fan_failure` / `fan_high`), threshold, enabled flag, and cooldown period (default 60 s).
- Triggered alerts are appended to an in-memory history (capped at 100 entries) and serialised into the state file's `recent_alerts` list, making them visible in the GUI without a separate IPC channel.
- Cooldown prevents re-triggering the same rule within its cooldown window.

---

## Update System

`updater.py` queries the GitHub Releases API (`/repos/lucashutch/pysysfan/releases/latest`) and compares the published tag against the running `__version__` using `packaging.version.Version`. If a newer release exists, the daemon logs a notice. The `pysysfan update` CLI command optionally runs `uv tool install --force git+<repo>` to upgrade in place.

Version tagging uses `hatch-vcs`; the package version is derived from the git tag at build time.

---

## CLI Command Reference

```
pysysfan [--verbose] [--version]
  scan [--type all|temp|fan|control] [--json]
  run  [--config PATH] [--no-reload]
  status [--json] [--watch]
  monitor [--interval SECONDS] [--profile NAME]
  config validate [--config PATH]
  config generate
  lhm download [--target DIR]
  lhm info
  service install
  service remove
  service start
  service stop
  service status
  update [--check-only]
```

Standalone installer entry points (separate executables):

```
pysysfan-install-lhm   download | info
pysysfan-install-pawnio
```

---

## Dependency Graph

```
cli.py
  └── hardware.py (scan, status, monitor)
  └── daemon.py (run)
  └── config.py (config validate/generate)
  └── platforms/windows_service.py (service)
  └── updater.py (update)

daemon.py
  ├── config.py
  ├── curves.py
  ├── temperature.py
  ├── hardware.py → platforms/windows.py → lhm/__init__.py
  ├── state_file.py
  ├── history_file.py
  ├── cache.py
  ├── notifications.py
  ├── profiles.py
  └── watcher.py

gui/desktop/app.py
  └── main_window.py
        ├── dashboard_page.py → local_backend.py, plotting.py, theme.py
        ├── curves_page.py    → local_backend.py, plotting.py, theme.py
        └── service_page.py   → local_backend.py, theme.py
```

---

## Testing Strategy

Tests live in `tests/` and are run with `pytest`. Coverage is enforced at ≥ 80% (`fail_under = 80` in `pyproject.toml`).

- **Unit tests** cover all pure-logic modules: `curves.py`, `temperature.py`, `config.py`, `state_file.py`, `history_file.py`, `cache.py`, `notifications.py`, `profiles.py`.
- **Hardware tests** use mocks/stubs for LHM COM objects so they run without actual hardware.
- **GUI tests** use `pytest-qt` with a `QApplication` fixture. Dashboard polling timers are paused when the page is hidden to prevent timer accumulation across tests.
- **Service tests** mock `subprocess` calls to avoid modifying the Task Scheduler.
- All async tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- A global `timeout = 10` (thread-based) prevents stalled tests from blocking CI.

---

## Security Considerations

- Hardware access (LHM + PawnIO) requires Administrator privileges. PySysFan checks for elevation at CLI entry and warns clearly if missing.
- The scheduled task runs at highest available privileges for the installing user — it does not use SYSTEM or a service account.
- File-based IPC means no network listener is exposed by the daemon.
- The `pysysfan-service` executable is resolved from the UV tool venv rather than blindly from PATH; Windows Store app execution alias stubs are explicitly detected and rejected.
- All GitHub API requests use `requests` with a 30 s timeout; download requests use 120 s with `stream=True` for large assets.
- State and history files are written atomically via `tempfile` + `os.replace()` so readers never see partial writes.

---

## Known Limitations

- Windows-only at runtime (pythonnet + LHM + PawnIO are Windows-specific).
- Laptop fan control: most laptops expose temperature sensors but not writable fan control channels in LHM.
- LHM occasionally reports stale sensor values; the daemon has no built-in sensor sanity check.
- The history file grows without bound between compaction intervals; very short poll intervals can generate large files quickly.
- Fan curve hysteresis state is reset whenever the daemon rebuilds curves from a config reload.
