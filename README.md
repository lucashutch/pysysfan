<div align="center">
  <img src="icons/pysysfan.svg" alt="PySysFan icon" width="120" height="120">
  <h1>PySysFan</h1>
  <p><strong>Windows-first fan control with a CLI, background daemon, and optional native desktop GUI.</strong></p>
  <p>Safer, more transparent control over motherboard fan headers using LibreHardwareMonitor and Windows Task Scheduler.</p>

  ![Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011-0078D6)
  ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)
  ![License](https://img.shields.io/badge/license-MIT-2ea043)

  <p>
    <a href="docs/windows.md"><strong>Windows setup</strong></a>
    ·
    <a href="docs/config.md"><strong>Configuration guide</strong></a>
    ·
    <a href="docs/config-schema.md"><strong>Schema reference</strong></a>
  </p>
</div>

---

PySysFan combines:

- a CLI for setup, scanning, validation, and service management
- a background daemon that applies your fan curves continuously
- an optional native PySide6 desktop app for live monitoring and editing

PySysFan is designed around LibreHardwareMonitor sensor data and Windows Task Scheduler startup automation.

## Why use PySysFan?

- **Custom temperature-based fan curves** for CPU, GPU, and motherboard sensors
- **Multiple temperature inputs per fan** with `max`, `min`, `average`, or `median` aggregation
- **Safe fallbacks** that return control to BIOS/firmware on exit or failure
- **Windows startup integration** using a high-privilege scheduled task
- **Native desktop GUI** with a Dashboard, Config editor, Service management page, and system tray presence
- **Readable YAML config** that stays usable even if you prefer the CLI over the GUI

## Before you install

PySysFan currently targets **Windows 10/11**.

Best results are on desktops and boards with controllable Super I/O fan headers exposed through LibreHardwareMonitor. Many laptops expose temperatures but do **not** expose writable fan controls.

You will typically need:

- Administrator privileges
- LibreHardwareMonitor
- the PawnIO driver for low-level hardware access

## Installation

### Option 1: One-click installer

Download and run [scripts/install-pysysfan.bat](scripts/install-pysysfan.bat) as Administrator.

The installer now asks whether you want:

- **Daemon + CLI only**, or
- **Daemon + CLI + desktop GUI**

If you select the desktop GUI, the installer also creates a **PySysFan Start Menu app** that uses the project icon and launches without opening a background terminal window.

It also downloads LibreHardwareMonitor and starts the PawnIO installer flow.

### Option 2: Install from Python packaging tools

```powershell
uv tool install pysysfan
```

### Optional desktop GUI

```powershell
uv tool install "pysysfan[gui]"
```

If you are working from a source checkout instead of an installed tool:

```powershell
uv sync --extra gui --group dev
uv run python -m pysysfan.gui.build check
uv run pysysfan-gui
```

The desktop app now uses the project icon in the **title bar**, **taskbar**, and **Windows notification area**.
When installed through the Windows installer, it also gets a Start Menu entry for app-style launching.

## Quick start

```powershell
# 1. Scan hardware (run in Administrator PowerShell)
pysysfan scan

# 2. Create an initial config
pysysfan config init

# 3. Validate the config
pysysfan config validate

# 4. Test one pass without staying resident
pysysfan run --once

# 5. Install the startup service once you're happy
pysysfan service install
```

If you installed the GUI:

```powershell
pysysfan-gui
```

Use the GUI to review live temperatures, edit curves, assign sensors, manage the startup service, and optionally minimize the app to the Windows notification area from the Service page.

## Example configuration

```yaml
general:
  poll_interval: 2

fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    temp_ids:
      - "/amdcpu/0/temperature/0"
      - "/amdcpu/0/temperature/1"
    aggregation: "max"
    curve: "balanced"
    header: "CPU Fan"

curves:
  balanced:
    hysteresis: 2.0
    points:
      - [30, 30]
      - [60, 60]
      - [75, 85]
      - [85, 100]
```

Built-in presets are always available:

- `silent`
- `balanced`
- `performance`

Static curves are also supported:

- `off`
- `on`
- `50`
- `75%`

## Common commands

```powershell
pysysfan scan
pysysfan status
pysysfan monitor
pysysfan run --once
pysysfan service status
pysysfan service install
pysysfan service restart
pysysfan update check
```

## Desktop GUI overview

The optional desktop app provides three core pages:

- **Dashboard** — daemon health, active profile, live readings, recent alerts, and history charts
- **Config** — fan assignments, curve editing, and profile-aware configuration changes
- **Service** — install, enable, disable, start, stop, restart, and inspect service state

Closing the desktop window minimizes it to the notification area when the system tray is available.
The Service page also includes an option to make the title-bar minimize button send the GUI to the tray instead of the taskbar.

## Documentation

- [Windows setup guide](docs/windows.md)
- [Configuration guide](docs/config.md)
- [Configuration schema reference](docs/config-schema.md)
- [Third-party licenses](THIRD_PARTY_LICENSES.md)

## Safety notes

PySysFan is intentionally conservative:

- it validates configuration before applying updates
- it supports hysteresis to reduce rapid fan oscillation
- it returns fans to firmware control when the daemon exits cleanly
- it refuses hardware operations when required components are unavailable

That said, hardware fan control is motherboard-specific. Always validate your sensor IDs and start with conservative curves.

## Contributing

Development setup, validation commands, and workflow rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

PySysFan is released under the [MIT License](LICENSE).
