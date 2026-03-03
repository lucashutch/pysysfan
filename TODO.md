# pysysfan Roadmap

## Graphical User Interface (GUI)
- Optional standalone GUI application
- Built using PySide6 (Qt) or a local web interface (FastAPI + React)
- Features:
  - Visual fan curve editor (drag and drop points)
  - Live sensor graphs over time
  - Hardware status overview
  - Seamlessly updates the YAML config file used by the background daemon

## Installer Script ✅
- [x] create a single bat file installer script with a simple TUI for installing the app and letting the user know whats going on
- [x] Ensure that this script downloads LHM using the inbuilt script (separate entry point: `pysysfan-install-lhm`)
- [x] Ensure that the script installs PawnIO (separate entry point: `pysysfan-install-pawnio`)

## Automatic updates
- Add automatic updates with a configurable schedule (maybe just check on startup??)
- Add a way to disable automatic updates
- add a way to check for updates
- add a way to manually update

## Improve testing
- Add coverage
- Add more tests
