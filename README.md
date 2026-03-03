# pysysfan

`pysysfan` is a Python fan control daemon for Windows. It controls system fan speeds based on temperature curves using LibreHardwareMonitor and the FanControl PawnIO ring0 driver.

## Requirements
- Windows 10 or 11
- Administrator privileges (for motherboard sensor access)
- `FanControl.PawnIO` driver to control motherboard fans via SuperIO chips.

## Installation
Use `uv` to install:
```bash
uv tool install .
```

You can also run it directly inside the repository:
```bash
uv run pysysfan --help
```

## First Setup
1. Open an Administrator PowerShell.
2. Run `pysysfan scan` to see your sensors.
3. Run `pysysfan config init --force` to create a starter configuration file at `~/.pysysfan/config.yaml`.
4. Edit the configuration file to map your fans to the correct sensors and curves.
5. Run `pysysfan config validate` to ensure your configuration is valid.
6. Install the background service: `pysysfan service install`.

## CLI Usage
- `pysysfan run` - run the background daemon
- `pysysfan monitor` - watch live sensor updates
- `pysysfan lhm download` - download the required LibreHardwareMonitor DLL
