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
- Built using Tauri 2.0 + Svelte 5 + FastAPI REST API
- Features:
  - Visual fan curve editor (drag and drop points)
  - Live sensor graphs over time
  - Hardware status overview
  - System tray with notifications
  - Multiple configuration profiles with auto-switching
  - Windows service management UI
  - Seamlessly updates the YAML config file used by the background daemon

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
- Use testing frameworks like Jest for Svelte and pytest for FastAPI


