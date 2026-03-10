# pysysfan Roadmap

## Platform Support
- **Current**: Windows only
- **Future**: Linux support may be revisited for systems with proper fan control interfaces
  - Experimental Linux support was removed due to limited hardware compatibility
  - Most modern laptops (ThinkPad P14s Gen 3, T14s Gen 3, etc.) have firmware-locked fan control
  - Desktop Linux systems with standard PWM controls may be supported in the future

## Graphical User Interface (GUI)
- **Status**: Native PySide6 GUI using direct local state/config/service integration
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
- Continue splitting large desktop modules into smaller focused components

## implement ty type checker
- Using the ty type checker to improve code quality and maintainability
- Add type annotations to all functions and classes
- Ensure 100% type coverage across the codebase

## move downloader helpers scripts to separate scripts dir
- Create a `scripts/` directory for all helper scripts
- Move existing downloader scripts to this new directory
- include the python downloaders for pawnio and lhm into this directory as well
- Ensure all scripts are well-documented and have clear usage instructions
- remove unity tests for downloader scripts as they are not critical to the core functionality of the project

## - Refine UI visuals: 
- status: grouped fan mappings, tab chrome, and graph key refresh completed
- completed: aligned dashboard fan groups to config keys, tightened graph selectors, and rebalanced dashboard card/plot spacing
- completed: dashboard height balancing, config-tab layout refresh, poll-interval save UX, profile management controls, and draggable curve editing
- completed: dashboard graph chrome cleanup, fan-card simplification, configured-fan graph filtering, and extra Config/Service styling polish
- completed: fan-card pane now scrolls independently, curve-editor temperature columns are wider, and graph selectors have clearer labels/arrows
- completed: daemon fan/control matching now preserves GPU graph coverage and configured target groups remain visible in the dashboard
- completed: daemon-owned 15-minute NDJSON history now feeds dashboard graphs even when the UI starts later than the service
- add icons, colored status badges, improved card styling, and small UX polish to stat cards and plots
- fix the curve plotting, it is very basic and doesnt look good and on all screens it isnt scaled well.
- the chosen card items at the top of the dashboard look very basic and could use some styling and polish to make them more visually appealing and easier to read at a glance.
- add icons to the stat cards to visually represent the different sensor types (CPU, GPU, etc.) and alert statuses (normal, warning, critical).
- the items in the cards dont make sense. It should more show the collection of sensor that are currently being used to control the fans, and the current target speeds for each fan. The current profile should be more prominent and ideally there should be a way to see at a glance which sensors are controlling which fans and what the current targets are.
- the curve plotting is very basic and could use some improvements to make it more visually appealing and easier to read. This could include adding grid lines, improving the color scheme, and making sure the plot scales well on different screen sizes.
- the overall styling of the dashboard could be improved to make it more visually appealing and easier to read. This could include using a more modern design, improving the layout, and adding some visual hierarchy to make it easier to find important information at a glance.
- the fan config section could be improved to make it more user-friendly and visually appealing. This could include adding icons to represent different fan types, improving the layout of the controls, and making it easier to see which fans are currently active and what their target speeds are. it should also include the option to select temps from a ddrop down by common name rather than path and easily be able to add multiple and delete them. It should also be clear which fans are assigned to which curves and which sensors are controlling them.