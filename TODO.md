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

## Live config updating support
- Implement file watcher to detect changes to `config.yaml`
- Apply new settings without restarting the daemon or when manually triggered via CLI
- Provide feedback on successful updates or errors in the config


## bugs
- Flickering cli updates in monitor mode
- setting 0% fan speed doesn't turn off the fan, it just sets it to minimum speed. Need to implement an "off" mode that fully disables the fan.
- DONE: monitor command shows all sensors, including sensor like temp sensor resolution or low limit or high limit. Need to filter out non-relevant sensors.