# pysysfan

Windows fan control daemon. Set custom fan curves based on temperature sensors with automatic fallback for safety.

> **Note:** Linux support was previously experimental but has been removed due to limited hardware compatibility. Linux support may be revisited in the future for systems with proper fan control interfaces.

## Features

- **Temperature-based fan curves** - Control fans based on CPU, GPU, or motherboard sensors
- **Built-in presets** - Silent, balanced, and performance curves included
- **Static speeds** - Set fans to fixed speeds: `off`, `on`, or any percentage
- **Safety first** - Automatic BIOS fallback on exit or crash
- **Windows-native** - Uses LibreHardwareMonitor for broad hardware support

## Quick Start

### Windows

```powershell
# Install
uv tool install pysysfan

# Or use the one-click installer
# Download: scripts/install-pysysfan.bat
```

### Optional Desktop GUI

```powershell
# Install GUI dependencies into the uv-managed environment
uv sync --extra gui

# Launch the desktop client inside the uv-managed venv
uv run pysysfan-gui
```

For a source checkout, install the GUI dependencies with `uv sync --extra gui`, then run `python -m pysysfan.gui.build check` to validate the desktop prerequisites before launching the GUI.

Note: run the `check` and `launch` commands through `uv run` so they execute in the same uv-managed virtual environment where dependencies were installed. For example:

```powershell
uv run python -m pysysfan.gui.build check
uv run python -m pysysfan.gui.build launch
```

The PySide6 desktop client currently provides:
- Dashboard: daemon status, live sensors, active profile, and recent alerts
- Curves: curve editing and fan assignment
- Service: install/start/stop/restart and log inspection

## First Setup

```powershell
# 1. Scan for hardware sensors (requires Administrator)
pysysfan scan

# 2. Generate initial config
pysysfan config init

# 3. Edit ~/.pysysfan/config.yaml or launch the desktop GUI

# Optional: launch the PySide6 desktop client
pysysfan-gui

# 4. Validate config
pysysfan config validate

# 5. Install as a service
pysysfan service install
```

## Configuration Example

```yaml
general:
  poll_interval: 2

fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    temp_ids: ["/amdcpu/0/temperature/0"]
    curve: "balanced"

curves:
  silent:
    points:
      - [30, 20]
      - [50, 40]
      - [70, 70]
      - [85, 100]
```

**Curve options:**
- Built-in: `silent`, `balanced`, `performance`
- Static: `off` (0%), `on` (100%), `50` (50%), `75%` (75%)
- Custom: Define your own temperature-speed points

📖 **[Full Configuration Guide](docs/config.md)**

## CLI Commands

```powershell
pysysfan scan              # Show all sensors
pysysfan run --once        # Test config (single pass)
pysysfan monitor           # Watch live sensor readings
pysysfan service install   # Install startup service
```

## Desktop Helper

```powershell
# Validate optional desktop dependencies
python -m pysysfan.gui.build check

# Launch the PySide6 GUI from a source checkout
python -m pysysfan.gui.build launch
```

Use the Dashboard tab to confirm the daemon is reachable, the Curves tab to edit and assign curves, and the Service tab to manage the Windows scheduled task.

## Platform Support

**Windows**: Windows 10/11 with Administrator privileges

See [Windows Setup](docs/windows.md)

## Safety Features

- Automatic BIOS fallback on exit/crash
- Hysteresis prevents rapid fan cycling
- Validates all configuration before applying

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## License

MIT License - See [LICENSE](LICENSE) file.
