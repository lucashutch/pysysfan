# pysysfan

`pysysfan` is a Python fan control daemon for Windows and Linux. It controls system fan speeds based on temperature curves using platform-specific hardware monitoring libraries.

- **Windows**: Uses LibreHardwareMonitor and PawnIO driver for SuperIO chip access
- **Linux**: Uses lm-sensors (pysensors) and sysfs hwmon interface

## Platform Support

### Windows
- Windows 10 or 11
- Administrator privileges required
- LibreHardwareMonitor + PawnIO driver

### Linux
- Kernel 5.x+ with hwmon support
- lm-sensors installed
- Root access for fan control (or udev rules)
- **Tested on**: ThinkPad laptops, generic desktops with SuperIO chips

## Installation

### Windows

Use `uv` to install:
```bash
uv tool install pysysfan
```

#### One-Click Installer
Download and double-click [`install-pysysfan.bat`](install-pysysfan.bat) to automatically install everything:
- **UV** (Python package manager)
- **pysysfan** (this tool)
- **LibreHardwareMonitor** (sensor library)
- **PawnIO** (ring0 driver for fan control)

### Linux

#### Quick Install (Recommended)
```bash
# Download and run the installer
curl -sSL https://raw.githubusercontent.com/anomalyco/pysysfan/main/install-pysysfan.sh | bash
```

Or manually:
```bash
# 1. Install pysysfan with Linux dependencies
pip install pysysfan[linux]
# or
uv tool install pysysfan[linux]

# 2. Run the Linux installer for system setup
pysysfan-linux-install
```

#### Manual Setup
If you prefer manual installation:
```bash
# Debian/Ubuntu
sudo apt install lm-sensors libsensors-dev python3 python3-pip

# Fedora/RHEL
sudo dnf install lm_sensors lm_sensors-devel python3 python3-pip

# Arch
sudo pacman -S lm_sensors python python-pip

# Detect and configure sensors
sudo sensors-detect --auto

# For ThinkPads: Enable fan control
sudo modprobe thinkpad_acpi fan_control=1
```

## First Setup

### Windows
1. Open an Administrator PowerShell, or prefix commands with `sudo` (Windows 11 24H2+).
2. Run `sudo pysysfan scan` to see your sensors.
3. Run `pysysfan config init --force` to create a starter configuration file at `~/.pysysfan/config.yaml`.
4. Edit the configuration file to map your fans to the correct sensors and curves.
5. Run `pysysfan config validate` to ensure your configuration is valid.
6. Install the background service: `pysysfan service install`.

### Linux
1. Run `sudo pysysfan scan` to detect your sensors.
2. Run `pysysfan config init --force` to create a starter configuration file.
3. Edit the configuration to map your fans to temperature sensors and curves.
4. Validate the configuration: `pysysfan config validate`.
5. Test the daemon: `sudo pysysfan run --once`.
6. Install the systemd service:
   ```bash
   # System-wide (runs at boot)
   sudo pysysfan service install
   
   # Or user service (runs at login)
   pysysfan service install --user
   ```

## CLI Usage

### Common Commands
- `pysysfan scan` - scan and display all detected hardware sensors
- `pysysfan run` - run the background daemon (use `--once` for single pass)
- `pysysfan monitor` - watch live sensor updates
- `pysysfan status` - show current sensor readings

### Configuration
- `pysysfan config init` - generate initial configuration
- `pysysfan config show` - display current configuration
- `pysysfan config validate` - validate configuration against hardware

### Service Management
- `pysysfan service install` - install startup service
- `pysysfan service uninstall` - remove startup service  
- `pysysfan service status` - check service status

### Platform-Specific Commands

#### Windows
- `pysysfan lhm download` - download LibreHardwareMonitor DLL
- `pysysfan lhm info` - show LHM library information

#### Linux
- `pysysfan-linux-install` - run the Linux installer

## Documentation

- [Linux Setup Guide](docs/linux.md) - Detailed Linux installation and configuration
- [Windows Setup Guide](docs/windows.md) - Windows-specific instructions

## Hardware Compatibility

### Tested Laptops
- **Lenovo ThinkPad P14s Gen 3** (AMD) - Full support via thinkpad_acpi
- **Lenovo ThinkPad T14** (Intel/AMD) - Full support
- **Lenovo ThinkPad X1 Carbon** - Full support

### Tested Desktops
Motherboards with SuperIO chips supported by lm-sensors:
- Nuvoton NCT6775F and variants
- ITE IT87xx series
- Fintek F71882FG

## Configuration Example

```yaml
general:
  poll_interval: 2  # seconds between updates

fans:
  cpu_fan:
    sensor: "/sys/class/hwmon/hwmon0/pwm1"  # Linux example
    curve: balanced
    source: "/sys/class/hwmon/hwmon1/temp1_input"
  
  case_fan:
    sensor: "/motherboard/nct6791d/control/0"  # Windows example
    curve: silent
    source: "/amdcpu/0/temperature/0"

curves:
  silent:
    hysteresis: 3
    points:
      - [30, 20]
      - [50, 40]
      - [70, 70]
      - [85, 100]
  
  balanced:
    hysteresis: 3
    points:
      - [30, 30]
      - [60, 60]
      - [75, 85]
      - [85, 100]
```

## Safety Features

- **Automatic fallback**: On exit/crash, all fan controls are restored to BIOS/firmware automatic mode
- **Hysteresis**: Prevents rapid fan speed oscillations around temperature thresholds
- **Safe temperature limits**: Curves ensure minimum fan speeds for safety
- **Permission checks**: Requires root/admin access for hardware control

## Troubleshooting

### Linux: Permission Denied on Fan Control
```bash
# Option 1: Run as root
sudo pysysfan run

# Option 2: Add udev rules for non-root access
# Create /etc/udev/rules.d/90-pysysfan.rules:
SUBSYSTEM=="hwmon", KERNEL=="hwmon*", ATTR{name}=="nct6775", MODE="0666"

# Reload rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Linux: ThinkPad Fan Control Not Available
```bash
# Check if module is loaded
lsmod | grep thinkpad_acpi

# Load with fan_control enabled
sudo modprobe -r thinkpad_acpi
sudo modprobe thinkpad_acpi fan_control=1

# Make persistent
echo "options thinkpad_acpi fan_control=1" | sudo tee /etc/modprobe.d/thinkpad-pysysfan.conf
```

### Windows: LHM DLL Not Found
```powershell
# Download the required library
pysysfan lhm download
```

## Contributing

Contributions are welcome! Please see the project repository for guidelines.

## License

MIT License - See LICENSE file for details.
