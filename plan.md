# Current Work Plan

## Graphs / Sidebar Live Updating
- Root issue: provider polling stops when switching away from `DashboardPage`, so the Graphs tab stops redrawing.
- Fix: make `MainWindow` the single polling owner (start when visible, pause when minimized/hidden) so tab switching never stops live updates.

## Status
- Implemented fix in `MainWindow` (single-owner polling) and updated `DashboardPage`/`GraphsPage` to no longer start/stop polling.
- Added hover stats row + hover label rendering.
- Updated legend marker glyphs to match expected behavior.

## Verification
- Run `uv run ruff check --fix` and `uv run ruff format`
- Run `uv run pytest tests/`

## Config Tab Colorization (3 Phases)
- Phase 1: Preview accent + tooltip card styling (applied to `CurvesPage` + QSS selectors)
- Phase 2: Accordion cards open-state accents + header hierarchy
- Phase 3: Points table header + alternating rows + selected-row accent

## Verification
- Run `uv run ruff check --fix` and `uv run ruff format`
- Run `uv run pytest tests/`

## Service Diagnostics Log Alignment
- Updated Service page diagnostics header styling and spacing to align with the left `SERVICE` section and running-state box.

## Verification
- Run `uv run ruff check --fix` and `uv run ruff format`
- Run `uv run pytest tests/`

## Service Diagnostics Log Improvements
- Renamed diagnostics header to `LOG` and squared log corners.
- Increased diagnostics log height to extend further toward the bottom.

## Minimise-to-tray Toggle Contrast
- Updated tray toggle unchecked color to dark grey and enabled color to match the service running green.

## PawnIO Version UI Fix
- Fixed PawnIO version mismatch in the desktop Service page by reading the installed version from Windows "Installed apps" registry.
- Verified with `tests/test_pawnio_version.py` and `tests/test_gui_service_page.py`.

## UAC Admin Permission Flow
- Removed the blocking "Administrator Permission Needed" popup from the desktop `ServicePage` when service/install actions request elevation.
- Updated the Windows elevation path in `src/pysysfan/gui/desktop/local_backend.py` to wait for the elevated process to finish and return real success/failure based on the elevated exit code.

## Verification
- Run `uv run ruff check --fix` and `uv run ruff format`
- Run `uv run pytest tests/`

## Daemon State Write Permission Error
- Fix Windows daemon crash by handling `PermissionError` during `daemon_state.json` writes.
- Skip state persistence update when writes fail; keep controlling fans.

## Verification
- Run `uv run ruff check --fix` and `uv run ruff format`
- Run `uv run pytest tests/`
