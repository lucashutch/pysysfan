# Configuration Guide

This guide documents the YAML format used by PySysFan for `config.yaml` and profile config files.

## Config file locations

Primary config:

- **Windows**: `%USERPROFILE%\.pysysfan\config.yaml`

Related profile files:

- `%USERPROFILE%\.pysysfan\profiles\*.yaml`
- `%USERPROFILE%\.pysysfan\active_profile`

## High-level structure

```yaml
general:
  poll_interval: 2.0

fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    temp_ids:
      - "/amdcpu/0/temperature/0"
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

update:
  auto_check: true
  notify_only: true
```

## General settings

### `general.poll_interval`

How often PySysFan reads temperatures and updates targets.

- Type: `float`
- Units: seconds
- Typical values: `1.0` to `5.0`
- Minimum practical value: `0.1`

## Fan entries

Each item under `fans:` defines one controllable fan target.

```yaml
fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    temp_ids:
      - "/amdcpu/0/temperature/0"
      - "/amdcpu/0/temperature/1"
    aggregation: "max"
    curve: "balanced"
    header: "CPU Fan"
    allow_fan_off: true
```

### Fields

#### `fan_id`
LibreHardwareMonitor control identifier for the writable fan control.

#### `temp_ids`
One or more LibreHardwareMonitor temperature sensor identifiers.

#### `aggregation`
How multiple temperature inputs are combined.

Supported values:

- `max`
- `min`
- `average`
- `median`

#### `curve`
Curve name or static speed.

Supported values:

- built-in presets such as `silent`, `balanced`, `performance`
- custom curve names from the `curves:` section
- static shortcuts such as `off`, `on`, `50`, or `75%`

#### `header`
Optional human-readable label for the fan.

#### `allow_fan_off`
Whether a `0%` target should be sent as an explicit off value.

- `true`: allow explicit 0% control where supported
- `false`: prefer the platform minimum / default behavior instead of explicit off

## Built-in presets

These preset names are always available even if you do not declare them yourself.

### `silent`

```yaml
silent:
  hysteresis: 2.0
  points:
    - [30, 20]
    - [50, 40]
    - [70, 70]
    - [85, 100]
```

### `balanced`

```yaml
balanced:
  hysteresis: 2.0
  points:
    - [30, 30]
    - [60, 60]
    - [75, 85]
    - [85, 100]
```

### `performance`

```yaml
performance:
  hysteresis: 2.0
  points:
    - [30, 50]
    - [50, 70]
    - [65, 90]
    - [75, 100]
```

## Custom curves

You can define any number of named curves.

```yaml
curves:
  gaming:
    hysteresis: 1.5
    points:
      - [30, 35]
      - [55, 65]
      - [70, 90]
      - [80, 100]
```

### Curve rules

- points are `[temperature_c, speed_percent]`
- temperatures should be in ascending order
- percentage values should stay between `0` and `100`
- hysteresis is measured in °C

## Static curve shortcuts

These do not require entries under `curves:`.

- `off` → `0%`
- `on` → `100%`
- `50` → `50%`
- `75%` → `75%`

## Finding fan and sensor IDs

Run a scan in an elevated PowerShell session:

```powershell
pysysfan scan
```

Useful filters:

```powershell
pysysfan scan --type temp
pysysfan scan --type control
pysysfan scan --json
```

PySysFan also writes the latest scan snapshot to `%USERPROFILE%\.pysysfan\scan.json`.

## Desktop GUI workflow

If you install the optional GUI, you can manage most configuration without editing YAML manually.

```powershell
pysysfan-gui
```

The desktop app lets you:

- review live temperatures and fan targets
- edit named curves
- assign sensors to configured fans
- switch between profiles
- manage the startup service

The GUI still writes normal YAML config files, so CLI and GUI workflows stay compatible.

## Validation

Always validate after editing config files manually:

```powershell
pysysfan config validate
```

This checks, among other things:

- YAML parsing
- curve references
- structural config issues
- hardware identifier availability when hardware access is possible

## Troubleshooting

### Validation says a sensor is missing

Run a fresh scan and update the identifiers in the config.

### A fan does not react

Common causes:

1. not running as Administrator
2. wrong `fan_id`
3. BIOS/firmware still owns the header
4. hardware does not support software fan control

### A temperature source reads `0°C`

PySysFan treats obviously invalid readings conservatively. Re-scan hardware and verify the matching sensor path.

## Related docs

- [Configuration schema reference](config-schema.md)
- [Windows setup guide](windows.md)
