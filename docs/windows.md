# Windows Setup Guide

This guide covers installation, hardware prerequisites, service setup, and the optional desktop GUI on Windows.

## Supported platforms

- Windows 10
- Windows 11

Administrator privileges are strongly recommended for setup and usually required for hardware access.

## What PySysFan needs on Windows

PySysFan depends on these pieces:

- **PySysFan** itself
- **LibreHardwareMonitor** for sensor and control access
- **PawnIO** for low-level hardware/driver support on supported boards

## Installation paths

### Recommended: one-click installer

Run [../scripts/install-pysysfan.bat](../scripts/install-pysysfan.bat) as Administrator.

It is intended to:

1. install `uv` if needed
2. ask whether to install daemon-only or daemon + GUI
3. download LibreHardwareMonitor
4. launch the PawnIO installer flow

If you include the GUI, the installer also creates a **PySysFan** Start Menu app that uses the project icon and launches without a console window.

### Manual installation with `uv`

```powershell
uv tool install pysysfan
```

Optional GUI:

```powershell
uv tool install "pysysfan[gui]"
```

Then complete the Windows-specific setup:

```powershell
pysysfan lhm download
pysysfan-install-pawnio
```

## Verify the install

```powershell
pysysfan --help
pysysfan lhm info
pysysfan scan
```

Optional desktop GUI checks from a source checkout:

```powershell
uv run python -m pysysfan.gui.build check
uv run pysysfan-gui
```

The desktop GUI uses the project icon in the window title bar, taskbar, and notification area.
Installer-created GUI shortcuts also use the PySysFan icon in the Start Menu.

## Hardware compatibility

PySysFan works best when LibreHardwareMonitor exposes writable fan controls.

Typical supported desktop hardware includes boards using common Super I/O families such as:

- Nuvoton
- ITE
- Fintek

### Important laptop note

Many laptops expose temperatures but **do not expose writable fan controls** through generic motherboard interfaces. On those systems, PySysFan may monitor successfully while fan control remains unavailable.

## Discover your sensors

Run a hardware scan from an elevated PowerShell session:

```powershell
pysysfan scan
```

Useful variants:

```powershell
pysysfan scan --type temp
pysysfan scan --type control
pysysfan scan --json
```

Look for control entries that are actually writable.

## First-time configuration

```powershell
pysysfan config init
pysysfan config validate
pysysfan run --once
```

You can then either:

- edit `%USERPROFILE%\.pysysfan\config.yaml` manually, or
- launch `pysysfan-gui` and use the native desktop editor

Example fan entry:

```yaml
fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    temp_ids:
      - "/amdcpu/0/temperature/0"
    aggregation: "max"
    curve: "balanced"
    header: "CPU Fan"
```

For the full schema, see [config.md](config.md) and [config-schema.md](config-schema.md).

## Running the daemon manually

```powershell
pysysfan run --once
pysysfan run
pysysfan status
pysysfan monitor
```

Use `--once` first when validating new config changes.

## Installing the startup service

PySysFan uses **Windows Task Scheduler**, not the Windows Services MMC stack.

Install it from an elevated shell:

```powershell
pysysfan service install
```

Useful follow-up commands:

```powershell
pysysfan service status
pysysfan service start
pysysfan service stop
pysysfan service restart
pysysfan service disable
pysysfan service enable
pysysfan service uninstall
```

The scheduled task is created to run at startup with high privileges so the daemon can access sensors before user login.

## Optional desktop GUI

Launch the native GUI with:

```powershell
pysysfan-gui
```

Main areas:

- **Dashboard** for daemon health, sensor values, alerts, and recent history
- **Config** for curves, fan assignments, and profile-oriented edits
- **Service** for scheduled-task management and diagnostics

When the Windows notification area is available, closing the window minimizes the app to the tray instead of fully exiting it.
The Service page also exposes a preference that lets the title-bar minimize button send the GUI to the tray instead of leaving it minimized on the taskbar.

## Troubleshooting

### `LibreHardwareMonitorLib.dll not found`

```powershell
pysysfan lhm download
pysysfan lhm info
```

### Access denied / permission errors

Run PowerShell as Administrator.

On newer Windows builds you may also use:

```powershell
sudo pysysfan scan
```

### PawnIO not installed or not available

Try the upstream install flow again:

```powershell
pysysfan-install-pawnio
```

If needed, inspect the upstream project:

- https://github.com/namazso/PawnIO.Setup

### No controllable fan headers found

Common causes:

1. not elevated
2. unsupported motherboard or EC path
3. BIOS/firmware fan policy still owns the header
4. laptop hardware does not expose writable fan controls

### Service installed but not running correctly

Check the task status first:

```powershell
pysysfan service status
schtasks /Query /TN pysysfan /FO LIST /V
```

Then validate the config and test a manual single run:

```powershell
pysysfan config validate
pysysfan run --once
```

## Related docs

- [Configuration guide](config.md)
- [Configuration schema reference](config-schema.md)
- [README](../README.md)
