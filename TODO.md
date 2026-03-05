# pysysfan Roadmap

## Graphical User Interface (GUI)
- Optional standalone GUI application
- Built using PySide6 (Qt) or a local web interface (FastAPI + React)
- Features:
  - Visual fan curve editor (drag and drop points)
  - Live sensor graphs over time
  - Hardware status overview
  - Seamlessly updates the YAML config file used by the background daemon

## Modularise codebase
- Split into smaller modules
- Improve code structure
- Ensure no files are larger than 500 lines

## Live config updating support ✓
- Implement file watcher to detect changes to `config.yaml` ✓
- Apply new settings without restarting the daemon or when manually triggered via CLI ✓
- Provide feedback on successful updates or errors in the config ✓

## Add support for multiple sensors per fan
- Allow users to specify multiple temperature sensors for a single fan
- Allow the user to choose how to aggregate the sensor readings (max, average, etc.) for fan curve calculations
- Get the indiviual temp for each core of the CPU and use the highest one for the fan curve instead of just the average temp. This will help prevent thermal throttling on high-end CPUs with multiple cores.

## bugs
- Flickering cli updates in monitor mode
- setting 0% fan speed doesn't turn off the fan, it just sets it to minimum speed. Need to implement an "off" mode that fully disables the fan.
