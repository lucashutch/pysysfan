# Configuration Schema

This document defines the canonical configuration schema for pysysfan.

## Canonical Schema

The canonical schema is the format that pysysfan writes to disk. All legacy
formats are converted to this format on load.

### Complete Example

```yaml
general:
  poll_interval: 2.0

fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    curve: "balanced"
    temp_ids:
      - "/amdcpu/0/temperature/0"
    aggregation: "max"
    header_name: "CPU Fan 1"
    allow_fan_off: true

  gpu_fan:
    fan_id: "/gpu/nvidia/control/0"
    curve: "silent"
    temp_ids:
      - "/gpu/nvidia/temperature/0"
    aggregation: "max"
    header_name: "GPU Fan"
    allow_fan_off: false

curves:
  silent:
    points:
      - [30, 20]
      - [50, 40]
      - [70, 70]
      - [85, 100]
    hysteresis: 2.0

  balanced:
    points:
      - [30, 30]
      - [60, 60]
      - [75, 85]
      - [85, 100]
    hysteresis: 2.0

  performance:
    points:
      - [30, 50]
      - [50, 70]
      - [65, 90]
      - [75, 100]
    hysteresis: 1.0

update:
  auto_check: true
  notify_only: true
```

## Field Definitions

### General Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `poll_interval` | float | 2.0 | Seconds between temperature checks |

### Fan Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `fan_id` | string | Yes | - | LibreHardwareMonitor identifier for control sensor |
| `curve` | string | Yes | - | Name of curve to use, or special value |
| `temp_ids` | list[str] | Yes | - | List of temperature sensor identifiers |
| `aggregation` | string | No | "max" | How to aggregate multiple temps: "max", "min", "avg" |
| `header_name` | string | No | None | Human-readable fan header name |
| `allow_fan_off` | bool | No | true | Allow 0% speed (off), or use minimum speed |

### Curve Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `points` | list[[float, float]] | Yes | - | List of [temperature, percentage] pairs |
| `hysteresis` | float | No | 2.0 | Temperature hysteresis in °C |

### Update Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `auto_check` | bool | true | Check for pysysfan updates on startup |
| `notify_only` | bool | true | Log update availability without auto-updating |

## Special Curve Values

The `curve` field in fan configuration can reference a named curve from the
`curves` section, or use these special values:

| Value | Meaning |
|-------|---------|
| `"off"` | Always 0% (fan off) |
| `"on"` | Always 100% (fan max) |
| `"50"` | Always 50% (any numeric string) |

## Legacy Compatibility

pysysfan maintains backward compatibility with older config formats. Legacy
keys are automatically converted to canonical format on load.

### Fan Configuration Legacy Keys

| Legacy Key | Canonical Key | Notes |
|------------|---------------|-------|
| `sensor` | `fan_id` | Deprecated, will be removed in future version |
| `temp_id` | `temp_ids` | Single temp converted to list |
| `source` | `temp_ids` | Very old legacy key |
| `header` | `header_name` | Both accepted on read, `header_name` written |

### Migration Example

**Legacy format (still supported):**

```yaml
fans:
  cpu_fan:
    sensor: "/motherboard/nct6791d/control/0"
    curve: "balanced"
    temp_id: "/amdcpu/0/temperature/0"
    header: "CPU Fan 1"
```

**Canonical format (written by pysysfan):**

```yaml
fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    curve: "balanced"
    temp_ids:
      - "/amdcpu/0/temperature/0"
    header_name: "CPU Fan 1"
```

## Validation Rules

### Fan Configuration

1. `fan_id` must be a valid LibreHardwareMonitor control identifier
2. `curve` must reference an existing curve name or be a special value
3. `temp_ids` must contain at least one valid temperature identifier
4. `aggregation` must be one of: "max", "min", "avg"
5. `poll_interval` must be positive and >= 0.1 seconds

### Curve Configuration

1. `points` must contain at least 2 points
2. Points must be sorted by temperature (ascending)
3. Temperature values should be in °C (typically 20-100)
4. Percentage values must be in range [0, 100]

## Deprecation Timeline

| Version | Status |
|---------|--------|
| Current | Legacy keys supported with deprecation warnings |
| v2.0 | Legacy keys still supported |
| v3.0 | Legacy keys removed (planned) |

## Implementation Notes

- Config loading is implemented in `src/pysysfan/config.py`
- The `Config.load()` method handles legacy key conversion
- The `Config.save()` method always writes canonical format
- Validation is performed by `FanDaemon._validate_config()`
