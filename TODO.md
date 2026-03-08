# pysysfan Roadmap

## Platform Support
- **Current**: Windows only
- **Future**: Linux support may be revisited for systems with proper fan control interfaces
  - Experimental Linux support was removed due to limited hardware compatibility
  - Most modern laptops (ThinkPad P14s Gen 3, T14s Gen 3, etc.) have firmware-locked fan control
  - Desktop Linux systems with standard PWM controls may be supported in the future

## Graphical User Interface (GUI)
- **Status**: Phase 7 (Service Management UI) - COMPLETED ✓
- Optional standalone GUI application
- Native desktop client now built with PySide6 over the FastAPI daemon API
- Features:
  - Visual fan curve editor (drag and drop points)
  - Live sensor graphs over time
  - Hardware status overview
  - System tray with notifications
  - Multiple configuration profiles with auto-switching
  - Windows service management UI
  - Seamlessly updates the YAML config file used by the background daemon

## PySide6 migration
- Replace the desktop launcher and top-level shell with PySide6 while keeping FastAPI as the runtime boundary
- Port the dashboard, service, and curve views in small validated slices
- Remove the remaining legacy web/Tauri GUI after the native surface is fully in use

## Modularise codebase
- Split into smaller modules
- Improve code structure
- Ensure no files are larger than 500 lines

## implement ty type checker
- Using the ty type checker to improve code quality and maintainability
- Add type annotations to all functions and classes
- Ensure 100% type coverage across the codebase

## add tests for UI
- Unit tests for all UI components
- Integration tests for API endpoints
- End-to-end tests simulating user interactions with the GUI
- Use Qt widget tests for the desktop GUI and pytest for the FastAPI daemon
- Keep API stream, alert-rule, and config-persistence contracts covered as the desktop client evolves

## move downloader helpers scripts to separate scripts dir
- Create a `scripts/` directory for all helper scripts
- Move existing downloader scripts to this new directory
- include the python downloaders for pawnio and lhm into this directory as well
- Ensure all scripts are well-documented and have clear usage instructions
- remove unity tests for downloader scripts as they are not critical to the core functionality of the project

## simplify the gui code and the way the frontend and backend communicate
- Refactor the API communication layer to be more straightforward and maintainable
- Use a consistent pattern for API calls, error handling, and data management
- Repair API contract mismatches around daemon bind settings, live runtime state snapshots, and sensor controllability metadata
