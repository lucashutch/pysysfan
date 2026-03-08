# Configuration Guide

This guide covers the pysysfan configuration file format and all available options.

## Configuration File Location

The configuration file is stored at:
- **Windows**: `%USERPROFILE%\.pysysfan\config.yaml`

## Basic Structure

```yaml
general:
  poll_interval: 2  # seconds between temperature checks

fans:
  # Fan definitions here

curves:
  # Custom curve definitions here
```

## Fan Configuration

Each fan entry maps a controllable fan to one or more temperature sources and a speed curve:

```yaml
fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"  # Hardware control path
    temp_ids:                                   # One or more temperature sensors
      - "/amdcpu/0/temperature/0"
    curve: "balanced"                           # Speed curve to use
    aggregation: "max"                          # max, min, or avg when using multiple sensors
    header_name: "CPU Fan 1"                    # Human-readable name (optional)
    allow_fan_off: true                         # Whether 0% is allowed
```

### Finding Hardware IDs

Use `pysysfan scan` to discover available sensors and controls (run as Administrator):

```powershell
pysysfan scan
```

This will show all available:
- Temperature sensors (for `temp_ids`)
- Fan controls (for `fan_id`)

## Curve Types

pysysfan supports three types of curves:

### 1. Built-in Curves (Pre-configured)

These curves are automatically available without configuration:

- **`silent`** - Low noise priority: `[(30, 20), (50, 40), (70, 70), (85, 100)]`
- **`balanced`** - Balanced performance: `[(30, 30), (60, 60), (75, 85), (85, 100)]`
- **`performance`** - Cooling priority: `[(30, 50), (50, 70), (65, 90), (75, 100)]`

### 2. Special Static Curves

These provide fixed speeds without requiring configuration:

- **`off`** or **`OFF`** - Fan always stopped (0%)
- **`on`** or **`ON`** - Fan always at maximum (100%)
- **Numeric values** - Fixed percentage, e.g., `50` or `50%`

Examples:

```yaml
fans:
  # Fan always off
  exhaust_fan:
    fan_id: "/motherboard/nct6791d/control/1"
    temp_ids:
      - "/amdcpu/0/temperature/0"
    curve: "off"

  # Fan always at 100%
  case_fan:
    fan_id: "/motherboard/nct6791d/control/2"
    temp_ids:
      - "/amdcpu/0/temperature/0"
    curve: "on"

  # Fan fixed at 50%
  gpu_fan:
    fan_id: "/motherboard/nct6791d/control/3"
    temp_ids:
      - "/gpu/0/temperature/0"
    curve: "50"
    # or: curve: "50%"
```

**Notes:**
- Case insensitive (`off`, `OFF`, `Off` all work)
- Numeric values must be between 0 and 100 (inclusive)
- These curves don't require entries in the `curves:` section

### 3. Custom Curves

Define your own curves with temperature-speed points:

```yaml
curves:
  my_custom_curve:
    hysteresis: 2.0  # Degrees Celsius (optional, default: 2.0)
    points:
      - [30, 20]   # At 30°C, run at 20%
      - [50, 40]   # At 50°C, run at 40%
      - [70, 70]   # At 70°C, run at 70%
      - [85, 100]  # At 85°C, run at 100%
```

#### Points Format

Each point is `[temperature, speed_percent]`:
- **Temperature**: The trigger temperature in Celsius
- **Speed**: The fan speed percentage (0-100)

Points must be ordered by temperature (low to high).

#### Hysteresis

Hysteresis prevents rapid fan speed fluctuations:

- **Default**: 2.0°C
- **Behavior**: When temperature drops, the fan stays at the higher speed until temperature drops by at least the hysteresis value
- **Disable**: Set to `0` to disable hysteresis

Example behavior with 2°C hysteresis:
1. Temp rises to 70°C → fan speeds up to 80%
2. Temp drops to 69°C → fan stays at 80%
3. Temp drops to 68°C → fan finally decreases to 60%

This prevents annoying rapid fan cycling when temperature fluctuates around thresholds.

## Complete Example

```yaml
general:
  poll_interval: 2

fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    temp_ids:
      - "/amdcpu/0/temperature/0"
    curve: "performance"
    aggregation: "max"
    header_name: "CPU Fan"

  case_fan:
    fan_id: "/motherboard/nct6791d/control/1"
    temp_ids:
      - "/motherboard/nct6791d/temperature/0"
    curve: "silent"
    aggregation: "max"
    header_name: "Case Fan"

  gpu_fan:
    fan_id: "/motherboard/nct6791d/control/2"
    temp_ids:
      - "/gpu/0/temperature/0"
    curve: "50%"
    aggregation: "max"
    header_name: "GPU Fan"

  exhaust_fan:
    fan_id: "/motherboard/nct6791d/control/3"
    temp_ids:
      - "/amdcpu/0/temperature/0"
    curve: "off"
    aggregation: "max"
    header_name: "Exhaust Fan"

curves:
  # Override the default silent curve with custom values
  silent:
    hysteresis: 3
    points:
      - [30, 15]
      - [50, 35]
      - [70, 65]
      - [85, 100]

  # Aggressive gaming curve
  gaming:
    hysteresis: 1
    points:
      - [30, 40]
      - [50, 70]
      - [65, 90]
      - [75, 100]
```

## Desktop Workflow

After generating a config, you can keep editing it directly or use the optional PySide6 desktop client:

```powershell
# Install the optional desktop GUI
uv tool install pysysfan --extra gui

# Launch the desktop client
pysysfan-gui
```

The Dashboard tab shows daemon health, live sensors, the active profile, and recent alerts. The Curves tab edits named curves and assigns them to configured fans. The Service tab manages the scheduled task and recent daemon logs.

## Validation

Validate your configuration before running:

```powershell
pysysfan config validate
```

This checks:
- YAML syntax is valid
- All curve references exist or are valid special curves
- Sensor IDs are present on the current hardware (when run with Administrator privileges)

## Hardware IDs

Fan and temperature IDs use LibreHardwareMonitor paths:

```yaml
fan_id: "/motherboard/nct6791d/control/0"
temp_ids:
  - "/amdcpu/0/temperature/0"
```

Common prefixes:
- `/amdcpu/` - AMD CPU sensors
- `/intelcpu/` - Intel CPU sensors
- `/gpu/` - GPU sensors
- `/motherboard/` - Motherboard sensors and controls

Use `pysysfan scan` to discover the correct IDs for your hardware.

## Safety Features

- **Automatic fallback**: On exit/crash, all fans are restored to BIOS automatic mode
- **Range validation**: Speed values outside 0-100 will cause validation errors
- **Missing sensor detection**: The daemon skips updates if temperature sensors return 0°C

## Troubleshooting

### "Curve not found" error

If you see errors like `Fan 'xxx' references unknown curve 'yyy'`:
1. Check the curve name spelling
2. Ensure custom curves are defined in the `curves:` section
3. Use `pysysfan config validate` to check all references

### Fan not responding

1. Verify you're running as Administrator
2. Check that the `fan_id` is correct using `pysysfan scan`
3. Some motherboards require BIOS settings to enable manual fan control

### Temperature showing 0°C

The daemon skips updates when sensors return 0°C (indicates sensor unavailable). Check:
1. The `temp_ids` entries are correct
2. The sensor driver is loaded
