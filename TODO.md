# pysysfan Roadmap

## Platform Support
- **Current**: Windows only
- **Future**: Linux support may be revisited for systems with proper fan control interfaces
  - Experimental Linux support was removed due to limited hardware compatibility
  - Most modern laptops (ThinkPad P14s Gen 3, T14s Gen 3, etc.) have firmware-locked fan control
  - Desktop Linux systems with standard PWM controls may be supported in the future

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
