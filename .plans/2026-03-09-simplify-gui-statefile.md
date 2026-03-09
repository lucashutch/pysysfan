# 2026-03-09 Simplify GUI / State File Refactor Plan

## Goal

Move pysysfan away from a local HTTP boundary and toward a simpler desktop architecture:
- daemon writes local runtime state to disk
- GUI reads local state and edits YAML directly
- service UI uses existing CLI/service helpers instead of HTTP calls

## Phases

### Phase 0
- Add `pysysfan.state_file`
- Define the persisted state schema
- Implement atomic write/read helpers
- Add tests for state file behavior

### Phase 1
- Write daemon snapshots to the state file every poll
- Include alerts and runtime fan targets
- Delete daemon API thread/state-manager usage
- Reduce default poll interval to 1 second

### Phase 2
- Delete `src/pysysfan/api/`
- Delete API-only tests
- Remove API dependencies from `pyproject.toml`
- Remove API flags/options from CLI/daemon construction

### Phase 3
- Add missing `service start|stop|enable|disable|restart` CLI commands
- Add `stop_task()` to `windows_service`
- Change CLI monitor default interval to 1 second
- Add/adjust tests for the new service commands

## Validation per phase
- Run Ruff format/check on touched files
- Run targeted pytest coverage for touched modules before each commit
- Commit once phase scope is stable

## Open follow-up work
- Rewrite the PySide6 GUI tabs to use the state file
- Add graphing via `pyqtgraph`
- Remove old GUI/API assumptions from widget tests
- Update docs after the GUI migration is complete
