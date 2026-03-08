# Implementation Plan

## Current Focus

- Phase 1: Replace the current GUI launcher with a PySide6 desktop shell.
- Preserve the FastAPI daemon boundary and lazy GUI imports.
- Port the current web surface in small, testable slices.

## Execution Order

1. Add PySide6 desktop scaffold and retarget `pysysfan-gui`.
2. Port dashboard, curve editor, and service management to desktop widgets.
3. Remove the legacy web/Tauri GUI.
4. Repair API contracts around the Python desktop client.
5. Replace shallow tests with integration and Qt widget coverage.
6. Clean up dependencies, docs, and repository structure.

## Status

- Phase 1 scaffold: completed
- Phase 1 dashboard page: completed
- Phase 1 service page: completed
- Phase 1 curves page: completed
- Phase 1 native desktop surfaces: completed
- Phase 1 legacy GUI retirement: completed
- Phase 2 API repair: not started
- Phase 3 testing overhaul: not started
- Phase 4 cleanup: not started
