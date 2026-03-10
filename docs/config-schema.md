# Configuration Schema Reference

This document describes the canonical PySysFan configuration schema as it exists today.

The same schema is used for:

- the main `config.yaml`
- profile configs stored under `%USERPROFILE%\.pysysfan\profiles\`

## Canonical example

```yaml
general:
  poll_interval: 2.0

fans:
  cpu_fan:
    fan_id: "/motherboard/nct6791d/control/0"
    curve: "balanced"
    temp_ids:
      - "/amdcpu/0/temperature/0"
      - "/amdcpu/0/temperature/1"
    aggregation: "max"
    header: "CPU Fan"
    allow_fan_off: true

  case_fan:
    fan_id: "/motherboard/nct6791d/control/1"
    curve: "silent"
    temp_ids:
      - "/motherboard/nct6791d/temperature/0"
    aggregation: "average"
    header: "Case Fan"

curves:
  silent:
    hysteresis: 2.0
    points:
      - [30, 20]
      - [50, 40]
      - [70, 70]
      - [85, 100]

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

## Top-level sections

| Section | Type | Required | Notes |
|---|---|---:|---|
| `general` | mapping | No | Defaults are applied when omitted |
| `fans` | mapping | No | Fan definitions keyed by config name |
| `curves` | mapping | No | Custom named curves |
| `update` | mapping | No | Update-check preferences |

## `general`

| Field | Type | Default | Description |
|---|---|---:|---|
| `poll_interval` | float | `1.0` | Seconds between control loop iterations |

## `fans.<name>`

| Field | Type | Required | Default | Description |
|---|---|---:|---:|---|
| `fan_id` | string | Yes | - | LibreHardwareMonitor control identifier |
| `curve` | string | Yes | - | Named curve or static curve shortcut |
| `temp_ids` | list[string] | Yes | - | One or more temperature identifiers |
| `aggregation` | string | No | `max` | `max`, `min`, `average`, or `median` |
| `header` | string | No | omitted | Human-readable label |
| `allow_fan_off` | bool | No | `true` | When `false`, avoid explicit off behavior |

## `curves.<name>`

| Field | Type | Required | Default | Description |
|---|---|---:|---:|---|
| `points` | list[list[float, float]] | Yes | - | `[temperature_c, speed_percent]` pairs |
| `hysteresis` | float | No | `2.0` | Downward temperature hysteresis in °C |

## `update`

| Field | Type | Default | Description |
|---|---|---:|---|
| `auto_check` | bool | `true` | Check for updates automatically |
| `notify_only` | bool | `true` | Report available updates without applying them automatically |

## Special `curve` values

The `curve` field supports named curve references and built-in static shortcuts.

| Value | Meaning |
|---|---|
| `off` | Always target `0%` |
| `on` | Always target `100%` |
| `50` | Always target `50%` |
| `75%` | Always target `75%` |

## Built-in preset names

PySysFan makes these preset names available even when they are not explicitly declared in `curves:`:

- `silent`
- `balanced`
- `performance`

## Legacy compatibility accepted on read

PySysFan still accepts several older keys when loading config files.

| Legacy key | Canonical key | Notes |
|---|---|---|
| `sensor` | `fan_id` | Older fan control field |
| `temp_id` | `temp_ids` | Single sensor is promoted to a list |
| `source` | `temp_ids` | Older single-source field |
| `header_name` | `header` | Accepted on read for compatibility |

PySysFan writes `header` when saving config files.

## Validation expectations

### Fan entries

- `fan_id` should point to a writable control when fan control is expected
- `temp_ids` should contain at least one usable temperature sensor
- `aggregation` should be one of `max`, `min`, `average`, or `median`
- `curve` should reference an existing curve name or a supported static shortcut

### Curves

- points should be ordered by increasing temperature
- temperatures should be realistic for your hardware
- speed percentages should stay within `0..100`
- hysteresis should be non-negative

## Notes

- PySysFan stores user-friendly labels in `header`
- profile YAML files reuse the same schema as the main config
- the canonical write path is implemented in `src/pysysfan/config.py`
