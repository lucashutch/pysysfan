# pysysfan

Cross-platform fan control for Windows and Linux. Set custom fan curves based on temperature sensors with automatic fallback for safety.

## Features

- **Temperature-based fan curves** - Control fans based on CPU, GPU, or motherboard sensors
- **Built-in presets** - Silent, balanced, and performance curves included
- **Static speeds** - Set fans to fixed speeds: `off`, `on`, or any percentage
- **Safety first** - Automatic BIOS fallback on exit or crash
- **Cross-platform** - Windows (LibreHardwareMonitor) and Linux (lm-sensors)

## Quick Start

### Windows

```powershell
# Install
uv tool install pysysfan

# Or use the one-click installer
# Download: install-pysysfan.bat
```

### Linux

```bash
# Install
curl -sSL https://raw.githubusercontent.com/anomalyco/pysysfan/main/install-pysysfan.sh | bash

# Or manually
pip install pysysfan[linux]
pysysfan-linux-install
```

## First Setup

```bash
# 1. Scan for hardware sensors
sudo pysysfan scan

# 2. Generate initial config
pysysfan config init

# 3. Edit ~/.pysysfan/config.yaml

# 4. Validate config
pysysfan config validate

# 5. Install as a service
sudo pysysfan service install
```

## Configuration Example

```yaml
general:
  poll_interval: 2

fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    temp_id: "/amdcpu/0/temperature/0"
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

```bash
pysysfan scan              # Show all sensors
pysysfan run --once        # Test config (single pass)
pysysfan monitor           # Watch live sensor readings
pysysfan service install   # Install startup service
```

## Platform Support

**Windows**: Windows 10/11 with Administrator privileges  
**Linux**: Kernel 5.x+ with lm-sensors, tested on ThinkPads and desktops

See [Windows Setup](docs/windows.md) | [Linux Setup](docs/linux.md)

## Safety Features

- Automatic BIOS fallback on exit/crash
- Hysteresis prevents rapid fan cycling
- Validates all configuration before applying

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## License

MIT License - See [LICENSE](LICENSE) file.
