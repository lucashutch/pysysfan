# Third-Party Licenses

This file tracks the direct third-party components that PySysFan relies on at runtime or through its optional desktop GUI.

It is a notice file for this repository. It does **not** replace the full upstream license texts shipped by package managers or upstream projects.

## Direct Python runtime dependencies

### Click
- **License**: BSD-3-Clause
- **Source**: https://github.com/pallets/click
- **Usage**: Command-line interface framework for `pysysfan` commands.

### packaging
- **License**: Apache-2.0 **or** BSD-2-Clause
- **Source**: https://github.com/pypa/packaging
- **Usage**: Version parsing and update-related packaging utilities.

### PyYAML
- **License**: MIT
- **Source**: https://github.com/yaml/pyyaml
- **Usage**: Configuration parsing and serialization.

### pythonnet
- **License**: MIT
- **Source**: https://github.com/pythonnet/pythonnet
- **Usage**: Loads and interfaces with the LibreHardwareMonitor .NET assembly on Windows.

### Requests
- **License**: Apache-2.0
- **Source**: https://github.com/psf/requests
- **Usage**: HTTP downloads and release/update checks.

### Rich
- **License**: MIT
- **Source**: https://github.com/Textualize/rich
- **Usage**: Terminal formatting, tables, panels, and status output.

### watchdog
- **License**: Apache-2.0
- **Source**: https://github.com/gorakhargosh/watchdog
- **Usage**: File watching for config/profile change detection.

## Optional desktop GUI dependencies

### PySide6
- **License**: LGPL-3.0-based open-source distribution for Qt for Python; see upstream `LICENSES/` notices for component-level terms
- **Source**: https://github.com/pyside/pyside-setup
- **Usage**: Native desktop GUI, taskbar icon integration, window chrome, and system tray support.

### pyqtgraph
- **License**: MIT
- **Source**: https://github.com/pyqtgraph/pyqtgraph
- **Usage**: Desktop history and curve plotting.

## External tools and binaries used by PySysFan

These are important to PySysFan's Windows workflow but are **not bundled in this repository**.

### LibreHardwareMonitor
- **License**: MPL-2.0
- **Source**: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
- **Usage**: Hardware sensor and control access through the downloaded `LibreHardwareMonitorLib.dll`.
- **Current handling**: Downloaded from upstream at user request/runtime setup time, not vendored in the repo.

### PawnIO
- **License**: No clear license file was exposed in the public `PawnIO.Setup` release repository during this audit
- **Source**: https://github.com/namazso/PawnIO.Setup
- **Usage**: Required low-level driver support for some Windows fan-control paths.
- **Current handling**: Not bundled. Users are directed to upstream installation flows.

## Compliance notes

## 1. Current packaging posture

PySysFan currently ships as source code / Python package metadata and relies on package managers or explicit upstream downloads for most third-party code. The repository does **not** vendor the dependencies listed above.

## 2. MIT / BSD / Apache dependencies

For the Python dependencies above, compliance is handled by:

- preserving this notice file in the repository
- relying on upstream packages that already ship their own metadata
- not removing or replacing upstream license information when those packages are installed

If PySysFan starts bundling dependencies into a standalone distribution, include the full upstream license texts and notices required by each package.

## 3. PySide6 / Qt obligations

The optional GUI depends on PySide6 and Qt. For the current Python-package workflow, PySide6 is installed from upstream wheels and keeps its own notice files.

If PySysFan is later distributed as a frozen or standalone desktop application, the release process must also ship the relevant Qt / PySide6 license texts and preserve replacement-friendly dynamic-linking expectations required by the open-source Qt for Python distribution.

## 4. LibreHardwareMonitor obligations

PySysFan downloads LibreHardwareMonitor from upstream instead of redistributing a modified copy.

If PySysFan ever bundles LibreHardwareMonitor binaries or modifies MPL-covered files, releases must retain MPL notices and provide the required corresponding source for modified MPL-covered files.

## 5. PawnIO caution

Because the public PawnIO release repository did not expose a clear license file at the time of review, PySysFan should continue treating PawnIO as an externally installed dependency rather than bundling or mirroring it.

## Audit date

Last reviewed: 2026-03-10
