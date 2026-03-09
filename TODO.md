# pysysfan Roadmap

## Simplify GUI / Remove HTTP API
- **Status**: In progress
- Replace the local FastAPI bridge with a local daemon state file
- Have the GUI read daemon state directly from disk instead of HTTP
- Keep config editing YAML-first with daemon auto-reload via file watching
- Extend service commands so the GUI can drive install/start/stop/enable/disable flows through the existing CLI/service helpers
- Current implementation focus:
  - Phase 0: state file foundation
  - Phase 1: daemon state snapshots
  - Phase 2: remove HTTP API package and dependencies
  - Phase 3: service/CLI alignment

## Platform Support
- **Current**: Windows only
- **Future**: Linux support may be revisited for systems with proper fan control interfaces
  - Experimental Linux support was removed due to limited hardware compatibility
  - Most modern laptops (ThinkPad P14s Gen 3, T14s Gen 3, etc.) have firmware-locked fan control
  - Desktop Linux systems with standard PWM controls may be supported in the future

## Graphical User Interface (GUI)
- **Status**: Native PySide6 GUI in place; backend simplification in progress
- Optional standalone GUI application
- Native desktop client now built with PySide6
- Features:
  - Visual fan curve editor (drag and drop points)
  - Live sensor graphs over time
  - Hardware status overview
  - System tray with notifications
  - Multiple configuration profiles with auto-switching
  - Windows service management UI
  - Seamlessly updates the YAML config file used by the background daemon

## PySide6 migration
- Replace the desktop launcher and top-level shell with PySide6 while simplifying the runtime boundary
- Port the dashboard, service, and curve views in small validated slices
- Remove the remaining legacy web/Tauri GUI after the native surface is fully in use

## Modularise codebase
- Split into smaller modules
- Improve code structure
- Ensure no files are larger than 500 lines
- Split the FastAPI server surface into focused route-registration modules and shared serializers

## implement ty type checker
- Using the ty type checker to improve code quality and maintainability
- Add type annotations to all functions and classes
- Ensure 100% type coverage across the codebase

## add tests for UI
- Unit tests for all UI components
- Integration tests for API endpoints
- End-to-end tests simulating user interactions with the GUI
- Use Qt widget tests for the desktop GUI and pytest for the FastAPI daemon
- Keep CI installing the `gui` extra so Qt widget tests run under `pytest-qt`
- Keep API stream, alert-rule, and config-persistence contracts covered as the desktop client evolves
- Keep the desktop helper entry points and prerequisite checks covered so GUI packaging regressions are caught early
- Cover profile switching, alert summaries/history, and richer service interactions in the PySide6 desktop tests

## move downloader helpers scripts to separate scripts dir
- Create a `scripts/` directory for all helper scripts
- Move existing downloader scripts to this new directory
- include the python downloaders for pawnio and lhm into this directory as well
- Ensure all scripts are well-documented and have clear usage instructions
- remove unity tests for downloader scripts as they are not critical to the core functionality of the project

## simplify the gui code and the way the frontend and backend communicate
- Remove the local HTTP layer where it adds complexity without user value
- Use a local daemon state file plus direct config/service integration instead
- Keep the desktop dashboard aligned with daemon state snapshots, profiles, alerts, and service state
