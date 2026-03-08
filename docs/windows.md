# Windows Setup Guide

This guide provides detailed instructions for setting up pysysfan on Windows systems.

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Hardware Support](#hardware-support)
- [Configuration](#configuration)
- [Service Setup](#service-setup)
- [Troubleshooting](#troubleshooting)

## Requirements

### System Requirements
- Windows 10 or Windows 11
- Administrator privileges (required for hardware access)
- .NET Framework 4.7.2 or later (pre-installed on Windows 10/11)

### Required Components

- **LibreHardwareMonitorLib.dll** - Hardware monitoring library
- **PawnIO Driver** - Ring0 driver for SuperIO chip access

## Installation

### Method 1: One-Click Installer (Recommended)

1. Download [`scripts/install-pysysfan.bat`](../scripts/install-pysysfan.bat)
2. Right-click and select "Run as Administrator"
3. The installer will:
   - Install UV (Python package manager)
   - Install pysysfan
   - Download LibreHardwareMonitor
   - Install PawnIO driver
   - Create initial configuration

### Method 2: Manual Installation

#### Step 1: Install UV

Download and install UV from [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)

#### Step 2: Install pysysfan

```powershell
# In Administrator PowerShell
uv tool install pysysfan

# Optional: install the desktop GUI as well
uv tool install pysysfan --extra gui
```

#### Step 3: Download LibreHardwareMonitor

```powershell
pysysfan lhm download
```

#### Step 4: Install PawnIO Driver

```powershell
# Install PawnIO via winget
winget install PawnIO

# Or manually download from GitHub
# https://github.com/namazso/PawnIO.Setup/releases
```

#### Step 5: Verify Installation

```powershell
pysysfan lhm info
pysysfan --help

# Optional desktop helper checks
python -m pysysfan.gui.build check
```

## Hardware Support

### Compatible Hardware

pysysfan on Windows supports motherboards with SuperIO chips accessible via LibreHardwareMonitor:

- **Nuvoton** NCT6775F, NCT6776F, NCT6791D, NCT6792D, NCT6793D, etc.
- **ITE** IT8620E, IT8686E, IT8688E, IT8689E, etc.
- **Fintek** F71882FG, F71889ED, etc.

### Laptops

Most laptops have limited fan control support due to proprietary EC firmware:
- **Lenovo ThinkPad** - Limited support (may need specific EC firmware)
- **Dell** - Limited support
- **HP** - Limited support

For laptops, consider using manufacturer-specific tools first.

### Verifying Compatibility

Run a hardware scan to check if your system is supported:

```powershell
# Must run as Administrator
pysysfan scan
```

Look for "Fan Controls" with `controllable: true` in the output.

## Configuration

### Sensor Identifiers

Windows uses LibreHardwareMonitor identifiers:

**Examples:**
- `/amdcpu/0/temperature/0` - AMD CPU temperature
- `/intelcpu/0/temperature/0` - Intel CPU temperature
- `/motherboard/nct6791d/temperature/0` - Motherboard temperature
- `/motherboard/nct6791d/control/0` - Fan control
- `/motherboard/nct6791d/fan/0` - Fan RPM sensor

### Finding Your Sensors

```powershell
# Scan all sensors
pysysfan scan

# Filter by type
pysysfan scan --type temp
pysysfan scan --type fan
pysysfan scan --type control

# Output as JSON
pysysfan scan --json > sensors.json
```

### Example Configuration

```yaml
general:
  poll_interval: 2

fans:
  cpu_fan:
      fan_id: "/motherboard/nct6791d/control/0"
    curve: balanced
      temp_ids:
         - "/amdcpu/0/temperature/0"
  
  case_fan:
      fan_id: "/motherboard/nct6791d/control/1"
    curve: silent
      temp_ids:
         - "/motherboard/nct6791d/temperature/0"

curves:
  balanced:
    hysteresis: 3
    points:
      - [30, 30]
      - [60, 60]
      - [75, 85]
      - [85, 100]
  
  silent:
    hysteresis: 3
    points:
      - [30, 20]
      - [50, 40]
      - [70, 70]
      - [85, 100]
```

### Configuration Commands

```powershell
# Generate initial config
pysysfan config init

# Show current config
pysysfan config show

# Validate config against hardware
pysysfan config validate

# Edit config directly
notepad $env:USERPROFILE\.pysysfan\config.yaml
```

## Service Setup

### Installing as Windows Service

pysysfan uses Windows Task Scheduler to run at boot:

```powershell
# Must run as Administrator
pysysfan service install

# Check status
pysysfan service status

# Remove service
pysysfan service uninstall
```

The service:
- Runs as SYSTEM account
- Starts automatically at boot
- Has highest privileges for hardware access
- Continues running even when no user is logged in

### Viewing Service Logs

Windows Task Scheduler doesn't have traditional logs, but you can check:

```powershell
# View Task Scheduler history
taskschd.msc

# Check if task is running
schtasks /Query /TN pysysfan /FO LIST
```

### Running Manually

For testing, you can run pysysfan manually:

```powershell
# Run once (good for testing)
pysysfan run --once

# Run continuously (Ctrl+C to stop)
pysysfan run

# Monitor live sensor values
pysysfan monitor

# Launch the optional desktop GUI
pysysfan-gui
```

## Troubleshooting

### "LibreHardwareMonitorLib.dll not found"

**Problem:**
```
FileNotFoundError: LibreHardwareMonitorLib.dll not found
```

**Solution:**
```powershell
# Download the DLL
pysysfan lhm download

# Verify installation
pysysfan lhm info
```

### "Access Denied" or "Permission Denied"

**Problem:**
Hardware access fails with permission errors.

**Solution:**
Run PowerShell as Administrator:
1. Press Win+X
2. Select "Windows PowerShell (Admin)" or "Terminal (Admin)"
3. Run commands from there

Alternatively, on Windows 11 24H2+:
```powershell
sudo pysysfan scan
```

### PawnIO Driver Not Installed

**Problem:**
```
Hardware access failed: PawnIO driver not found
```

**Solution:**
```powershell
# Check if PawnIO service exists
sc query PawnIO

# Install via winget
winget install PawnIO

# Or manually from GitHub
# https://github.com/namazso/PawnIO.Setup/releases
```

### No Controllable Fans Found

**Problem:**
```powershell
pysysfan scan
# Shows 0 controllable outputs
```

**Possible Causes:**
1. Not running as Administrator
2. Motherboard SuperIO chip not supported
3. BIOS has fan control locked

**Solutions:**
1. Run as Administrator
2. Check BIOS settings for "Smart Fan" or "Fan Control Mode"
3. Try disabling "Q-Fan Control" or similar in BIOS
4. Check if motherboard is in [LHM supported list](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor#motherboards)

### Fan Speed Not Changing

**Problem:**
Config appears valid but fan speed doesn't change.

**Possible Causes:**
1. BIOS overriding OS control
2. Wrong control sensor identifier
3. Minimum PWM value too low

**Solutions:**
1. Check BIOS fan settings
2. Verify sensor identifier: `pysysfan scan --type control`
3. Try higher minimum speed in curve (e.g., 30% instead of 20%)

### Configuration Validation Fails

**Problem:**
```powershell
pysysfan config validate
# Shows errors about sensors not found
```

**Solution:**
1. Run hardware scan to get correct identifiers:
   ```powershell
   pysysfan scan --json | ConvertFrom-Json
   ```
2. Update config with correct sensor IDs
3. Re-validate

### Service Won't Start

**Problem:**
Service installed but doesn't start automatically.

**Solution:**
```powershell
# Check task status
schtasks /Query /TN pysysfan

# Recreate task
pysysfan service uninstall
pysysfan service install

# Test manually first
pysysfan run --once
```

### .NET Framework Errors

**Problem:**
```
RuntimeError: Failed to load .NET runtime
```

**Solution:**
Windows 10/11 should have .NET Framework 4.7.2+ pre-installed.
If missing:

1. Download from Microsoft:
   https://dotnet.microsoft.com/download/dotnet-framework

2. Or enable via Windows Features:
   - Open "Turn Windows features on or off"
   - Check ".NET Framework 3.5" and ".NET Framework 4.8 Advanced Services"
   - Click OK

### "pysysfan" Command Not Found

**Problem:**
After installation, `pysysfan` command is not recognized.

**Solution:**
```powershell
# Check if UV tool path is in PATH
$env:PATH -split ";" | Select-String "uv"

# Add to PATH if missing
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:USERPROFILE\.local\bin",
    "User"
)

# Restart PowerShell
```

## Testing Your Setup

### Initial Test

```powershell
# 1. Verify hardware detection
pysysfan scan

# 2. Create config
pysysfan config init

# 3. Validate config
pysysfan config validate

# 4. Test single run
pysysfan run --once

# 5. Monitor live
pysysfan monitor
```

### Stress Testing

Use a stress test tool to verify cooling:

```powershell
# Install Prime95 or similar stress tool
# https://www.mersenne.org/download/

# Run stress test
# In another PowerShell window:
pysysfan monitor

# Watch temperatures and fan speeds
```

## Getting Help

If you encounter issues not covered here:

1. Check [GitHub Issues](https://github.com/anomalyco/pysysfan/issues)
2. Include output of:
   ```powershell
   pysysfan scan --json
   pysysfan lhm info
   pysysfan config show
   ```
3. Check LibreHardwareMonitor compatibility:
   - https://github.com/LibreHardwareMonitor/LibreHardwareMonitor

## Additional Resources

- [LibreHardwareMonitor GitHub](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)
- [PawnIO Driver](https://github.com/namazso/PawnIO)
- [LibreHardwareMonitor Supported Hardware](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor#supported-hardware)
