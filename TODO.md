# pysysfan Roadmap

## Graphical User Interface (GUI)
- Optional standalone GUI application
- Built using PySide6 (Qt) or a local web interface (FastAPI + React)
- Features:
  - Visual fan curve editor (drag and drop points)
  - Live sensor graphs over time
  - Hardware status overview
  - Seamlessly updates the YAML config file used by the background daemon

## Installer Script
- create a single bat file installer script with a simple TUI for installing the app and letting the user know whats going on
- Ensure that this script downloads LHM using the inbuilt script (maybe separate it into a new entry point for the script?)
- Ensure that the script install PawnIO