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

## bugs
- remove LHM manager in the main CLI (should only be available in the lhm manager entry point like the pawnio manager)
