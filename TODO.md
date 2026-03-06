# pysysfan Roadmap

## Platform Support
- **Current**: Windows only
- **Future**: Linux support may be revisited for systems with proper fan control interfaces
  - Experimental Linux support was removed due to limited hardware compatibility
  - Most modern laptops (ThinkPad P14s Gen 3, T14s Gen 3, etc.) have firmware-locked fan control
  - Desktop Linux systems with standard PWM controls may be supported in the future

## Graphical User Interface (GUI)
- **Status**: Phase 0 (Contracts & Architecture) - COMPLETED ✓
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

## Completed Phases
- [x] **Phase 0**: Contracts & Architecture (2026-03-06)
  - API module structure created
  - Daemon state management implemented
  - Token authentication implemented
  - Windows service updated with explicit config path
  - Config schema documented
  - Unit tests added (30 tests, 100% passing)
