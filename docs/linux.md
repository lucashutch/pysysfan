# Linux Setup Guide

This guide provides detailed instructions for setting up pysysfan on Linux systems.

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Hardware Support](#hardware-support)
- [Configuration](#configuration)
- [Service Setup](#service-setup)
- [Troubleshooting](#troubleshooting)

## Requirements

### System Requirements
- Linux kernel 5.x or later
- Python 3.8 or later
- Root access (or udev rules) for fan control

### Supported Distributions

- **Debian-based**: Ubuntu, Debian, Linux Mint, Pop!_OS, Elementary OS
- **RHEL-based**: Fedora, RHEL, CentOS, Rocky Linux, AlmaLinux
- **Arch-based**: Arch Linux, Manjaro, EndeavourOS
- **SUSE**: openSUSE Tumbleweed, openSUSE Leap

## Installation

### Method 1: One-Line Installer (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/anomalyco/pysysfan/main/install-pysysfan.sh | bash
```

This will:
1. Detect your distribution
2. Install system dependencies (lm-sensors)
3. Run sensors-detect to discover hardware
4. Detect ThinkPad and enable fan_control if applicable
5. Install pysysfan Python package
6. Generate initial configuration
7. Optionally install systemd service

### Method 2: Manual Installation

#### Step 1: Install System Dependencies

**Debian/Ubuntu:**
```bash
sudo apt update
sudo apt install lm-sensors libsensors-dev python3 python3-pip
```

**Fedora/RHEL:**
```bash
sudo dnf install lm_sensors lm_sensors-devel python3 python3-pip
```

**Arch Linux:**
```bash
sudo pacman -S lm_sensors python python-pip
```

**openSUSE:**
```bash
sudo zypper install sensors libsensors4-devel python3 python3-pip
```

#### Step 2: Configure Hardware Sensors

```bash
# Detect and configure sensors
sudo sensors-detect --auto

# Load detected kernel modules
sudo sensors
```

#### Step 3: Install pysysfan

```bash
# Using pip
pip install --user pysysfan[linux]

# Or using uv (recommended)
uv tool install pysysfan[linux]
```

#### Step 4: Generate Configuration

```bash
pysysfan config init
```

## Hardware Support

### ThinkPad Laptops

ThinkPad laptops use the `thinkpad_acpi` kernel module for fan control.

#### Enable Fan Control

The pysysfan installer automatically enables this, but you can do it manually:

```bash
# Check if already enabled
cat /proc/acpi/ibm/fan

# If "level:" is not shown, enable it:
sudo modprobe -r thinkpad_acpi
sudo modprobe thinkpad_acpi fan_control=1

# Make persistent
sudo tee /etc/modprobe.d/thinkpad-pysysfan.conf << EOF
options thinkpad_acpi fan_control=1
EOF
```

#### ThinkPad Fan Levels

Unlike PWM control (0-255), ThinkPad uses discrete levels:

| Level | Description |
|-------|-------------|
| 0 | Off (if supported) |
| 1-7 | Increasing speed |
| auto | Automatic control by firmware |
| disengaged | Maximum speed (bypass controller) |

pysysfan maps percentages to appropriate levels:
- 0% → level 0
- 1-14% → level 1
- 15-28% → level 2
- ...
- 85-100% → level 7

### Generic Desktops

Desktop motherboards typically use SuperIO chips controlled via hwmon:

#### Supported Chips

- **Nuvoton NCT6775F** and variants
- **ITE IT87xx** series (IT8613E, IT8620E, IT8625E, etc.)
- **Fintek F71882FG/F71889FG**

#### Loading Kernel Modules

If sensors are not auto-detected, manually load the driver:

```bash
# For Nuvoton chips
sudo modprobe nct6775

# For ITE chips
sudo modprobe it87

# For Fintek chips
sudo modprobe f71882fg
```

#### Verify Detection

```bash
# List hwmon devices
ls /sys/class/hwmon/

# Check each device
cat /sys/class/hwmon/hwmon*/name

# View temperature sensors
cat /sys/class/hwmon/hwmon*/temp*_input

# View fan sensors
cat /sys/class/hwmon/hwmon*/fan*_input

# Check for PWM controls
ls /sys/class/hwmon/hwmon*/pwm*
```

## Configuration

### Sensor Identifiers

Linux uses sysfs paths as sensor identifiers:

**Temperatures:**
- `/sys/class/hwmon/hwmon0/temp1_input`
- `/sys/class/hwmon/hwmon1/temp2_input`

**Fan Controls (PWM):**
- `/sys/class/hwmon/hwmon0/pwm1`
- `/sys/class/hwmon/hwmon0/pwm2`

**ThinkPad Fan:**
- `thinkpad/fan` (special identifier)

### Example Configuration

```yaml
general:
  poll_interval: 2

fans:
  cpu_fan:
    sensor: "/sys/class/hwmon/hwmon0/pwm1"
    curve: balanced
    source: "/sys/class/hwmon/hwmon1/temp1_input"
  
  gpu_fan:
    sensor: "/sys/class/hwmon/hwmon0/pwm2"
    curve: performance
    source: "/sys/class/hwmon/hwmon2/temp1_input"

curves:
  balanced:
    hysteresis: 3
    points:
      - [30, 30]
      - [60, 50]
      - [75, 80]
      - [85, 100]
  
  performance:
    hysteresis: 2
    points:
      - [30, 40]
      - [50, 70]
      - [65, 90]
      - [75, 100]
```

### Finding Your Sensors

```bash
# Scan all sensors
sudo pysysfan scan

# Filter by type
sudo pysysfan scan --type temp
sudo pysysfan scan --type fan
sudo pysysfan scan --type control

# Output as JSON
sudo pysysfan scan --json
```

## Service Setup

### System-Wide Service (Recommended)

Runs as root at system boot:

```bash
# Install service
sudo pysysfan service install

# Start immediately
sudo systemctl start pysysfan

# Check status
pysysfan service status

# View logs
sudo journalctl -u pysysfan -f
```

### User Service

Runs as your user at login:

```bash
# Install user service
pysysfan service install --user

# Start immediately
systemctl --user start pysysfan

# Enable at login
systemctl --user enable pysysfan

# Check status
pysysfan service status --user
```

**Note:** User services may not have permission to control fans depending on your udev rules.

### Service Management Commands

```bash
# Start/stop/restart
sudo systemctl start pysysfan
sudo systemctl stop pysysfan
sudo systemctl restart pysysfan

# Check if running
sudo systemctl is-active pysysfan

# View service logs
sudo journalctl -u pysysfan -n 100
sudo journalctl -u pysysfan -f  # Follow mode

# Remove service
sudo pysysfan service uninstall
```

## Troubleshooting

### Permission Denied

**Problem:**
```
PermissionError: Cannot set fan speed: permission denied
```

**Solution 1 - Run as root:**
```bash
sudo pysysfan run
```

**Solution 2 - Add udev rules:**
```bash
# Find your hwmon chip name
cat /sys/class/hwmon/hwmon*/name

# Create udev rule
sudo tee /etc/udev/rules.d/90-pysysfan.rules << EOF
SUBSYSTEM=="hwmon", KERNEL=="hwmon*", ATTR{name}=="nct6775", MODE="0666"
SUBSYSTEM=="hwmon", KERNEL=="hwmon*", ATTR{name}=="coretemp", MODE="0666"
EOF

# Reload rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### No Sensors Found

**Problem:**
```
No temperature sensors found
```

**Solution:**
```bash
# Run sensors-detect
sudo sensors-detect --auto

# Load detected modules
sudo sensors

# Check if modules are loaded
lsmod | grep -E "(coretemp|k10temp|nct6775|it87)"

# If not loaded, try manually
sudo modprobe coretemp  # Intel CPUs
sudo modprobe k10temp   # AMD CPUs
```

### ThinkPad Fan Control Not Available

**Problem:**
```
/proc/acpi/ibm/fan not found
```

**Solution:**
```bash
# Check if thinkpad_acpi is loaded
lsmod | grep thinkpad_acpi

# Load with fan_control
sudo modprobe -r thinkpad_acpi
sudo modprobe thinkpad_acpi fan_control=1

# Verify
cat /proc/acpi/ibm/fan
```

### PWM Control Not Working

**Problem:**
Fan speed doesn't change when setting PWM values.

**Solution:**
Check if BIOS has "fan control" enabled:
1. Enter BIOS setup
2. Look for "Fan Control Mode" or "Smart Fan"
3. Set to "Manual" or "OS Controlled" if available

Verify PWM enable:
```bash
# Check current mode
cat /sys/class/hwmon/hwmon*/pwm*_enable

# 0 = BIOS control, 1 = manual control
# Enable manual control
echo 1 | sudo tee /sys/class/hwmon/hwmon*/pwm*_enable
```

### Service Fails to Start

**Problem:**
```
Failed to start pysysfan.service
```

**Solution:**
```bash
# Check service status
sudo systemctl status pysysfan

# View detailed logs
sudo journalctl -u pysysfan -n 50

# Test config manually
sudo pysysfan config validate

# Run once to see errors
sudo pysysfan run --once
```

### pysysfan Command Not Found

**Problem:**
```
command not found: pysysfan
```

**Solution:**
```bash
# If installed with pip --user
export PATH="$HOME/.local/bin:$PATH"

# If installed with uv
export PATH="$HOME/.cargo/bin:$PATH"

# Add to ~/.bashrc or ~/.zshrc for persistence
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

## Testing Your Setup

### Manual Test

```bash
# Run daemon once (good for testing)
sudo pysysfan run --once

# Monitor live sensor values
sudo pysysfan monitor

# Watch specific sensor
watch -n 1 cat /sys/class/hwmon/hwmon*/temp1_input
```

### Stress Test

Install stress testing tools to verify cooling:

```bash
# Debian/Ubuntu
sudo apt install stress

# Run CPU stress test
stress --cpu $(nproc) --timeout 60

# In another terminal, watch temperatures
sudo pysysfan monitor
```

## Getting Help

If you encounter issues not covered here:

1. Check the [GitHub Issues](https://github.com/anomalyco/pysysfan/issues)
2. Run with verbose logging: `sudo pysysfan run --verbose`
3. Include output of `sudo pysysfan scan --json` in bug reports

## Additional Resources

- [lm-sensors documentation](https://hwmon.wiki.kernel.org/)
- [ThinkPad ACPI documentation](https://www.kernel.org/doc/html/latest/admin-guide/laptops/thinkpad-acpi.html)
- [hwmon kernel documentation](https://www.kernel.org/doc/html/latest/hwmon/)
