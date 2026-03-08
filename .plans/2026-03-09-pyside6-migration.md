# 2026-03-09 PySide6 Migration Plan

## Goal

Move the GUI from the current Svelte/Tauri stack to a native PySide6 desktop client while keeping FastAPI as the canonical daemon boundary.

## Phases

### Phase 1

1. Add a new `pysysfan.gui.desktop` package.
2. Retarget the GUI entrypoint to the desktop launcher.
3. Add a minimal desktop shell with dashboard, curves, and service tabs.
4. Add import-isolation and basic Qt widget tests.

### Phase 2

1. Standardize the Python desktop client around the existing token/Bearer flow.
2. Fix server and daemon contract issues: live state population, host/port handling, fan overrides, alert rule identity, and accurate sensor metadata.
3. Split oversized API logic into smaller modules after the contract is stable.

### Phase 3

1. Add daemon-loop integration tests.
2. Expand stream and API contract tests.
3. Add PySide6 widget tests and desktop integration tests.
4. Remove obsolete TypeScript tests with the retired web GUI.

### Phase 4

1. Remove web, Tauri, and unused GUI dependencies.
2. Update docs and roadmap files.
3. Final lint, format, and test pass.

## First Commit Target

- Planning artifacts in place.
- PySide6 desktop scaffold added.
- `pysysfan-gui` launches the desktop shell.
- GUI tests updated to desktop assumptions.

## Progress

- Completed: desktop scaffold and launcher retarget.
- Completed: dashboard page backed by the Python API client with refresh and live sensor streaming.
- Completed: service management page with status, controls, logs, and Python client coverage.
- Completed: curve management page with validation, preview, save/delete, and fan assignment.
- Completed: legacy web/Tauri GUI sources removed and the helper script retargeted to PySide6.
- Completed: first API contract slice covering daemon bind host/port propagation, live runtime state snapshots, and truthful fan control metadata.
- Completed: second API contract slice covering config persistence, partial fan updates, stable alert-rule identity, stream payload parity, and API state default alignment.
- Next: expand integration coverage further and clean up remaining oversized API/documentation surfaces.
