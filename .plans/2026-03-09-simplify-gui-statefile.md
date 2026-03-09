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

### Phase 4
- Add `gui.desktop.local_backend` helpers for profile loading, validation, state reads, and elevated command execution
- Reuse local CLI/module entry points for privileged actions

### Phase 5
- Rewrite the desktop dashboard to consume the daemon state file directly
- Render alerts, temperatures, fan state, and optional `pyqtgraph` history charts
- Show a clear disconnected state when the daemon snapshot is missing or stale

### Phase 6
- Rewrite the curves page to edit YAML/profile config directly
- Keep direct preview plotting and profile switching without an API client
- Prevent deletion of built-in preset curves and keep fan/curve selection in sync

### Phase 7
- Rewrite the service page around Task Scheduler helpers plus daemon state-file diagnostics
- Route installer/service actions through local helper functions with elevation support

### Phase 8
- Add `pyqtgraph` to the GUI optional dependency and build prerequisite checks
- Rewrite GUI tests for dashboard, curves, service, and build flows
- Refresh stale validation/tests that still assumed the removed API layer

### Phase 9
- Update plan/TODO artifacts to reflect the completed migration
- Run final full-project validation

## Validation per phase
- Run Ruff format/check on touched files
- Run targeted pytest coverage for touched modules before each commit
- Commit once phase scope is stable

## Open follow-up work
- Consider splitting the larger desktop pages into smaller modules
- Refresh README/docs screenshots or usage notes for the new desktop workflow

## Final status
- Phases 0-9 completed
- Full validation completed with `590` passing tests
