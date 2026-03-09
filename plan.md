# Simplify GUI / Remove HTTP API Plan

## Active Work — Dashboard Stat Implementation

### Goal

Improve the dashboard stat section so the GUI highlights the active profile, fan targets, and controlling sensors with clearer visual hierarchy.

### Current slice
1. Add planning and tracking artifacts for the dashboard stat refresh.
2. Implement a first-pass dashboard stat redesign with shared QSS styling.
3. Update dashboard GUI tests and run targeted validation.

Status: in progress.

## Goal

Replace the local HTTP API with a lightweight local state-file model so the daemon, CLI, and future GUI can share runtime state without FastAPI.

## Phases

### Phase 0 — State file foundation
1. Add a dedicated state file module.
2. Support atomic writes and safe reads.
3. Add tests for stale, missing, and corrupt state files.

Status: completed.

### Phase 1 — Daemon state snapshots
1. Have the daemon write runtime snapshots to disk every control pass.
2. Include active profile, current sensors, fan targets, and recent alerts.
3. Remove in-process API state tracking from the daemon.
4. Lower the default poll interval to 1 second.

Status: completed.

### Phase 2 — Remove HTTP API layer
1. Delete the FastAPI server/client package and API-only tests.
2. Remove API runtime options from the daemon and CLI.
3. Remove API-only dependencies from project metadata.

Status: completed.

### Phase 3 — Service/CLI alignment
1. Add missing CLI service commands for start/stop/enable/disable/restart.
2. Add stop support to the Windows service helper.
3. Change `monitor` default refresh interval to 1 second.

Status: completed.

### Phase 4 — Desktop local backend helpers
1. Add shared desktop helpers for reading daemon state, loading profiles, validating config, and invoking installer/service actions.
2. Keep privileged actions routed through existing CLI/module entry points.

Status: completed.

### Phase 5 — Dashboard rewrite
1. Replace API polling with direct reads from the daemon state file.
2. Surface summary, sensors, targets, alerts, and optional `pyqtgraph` history charts.
3. Show clear "daemon not running" state when no fresh snapshot exists.

Status: completed.

### Phase 6 — Curves/profile editor rewrite
1. Edit YAML/profile data directly through `Config` and `ProfileManager`.
2. Keep preview plotting local and preserve daemon auto-reload semantics.
3. Align fan assignment editing with direct profile switching.

Status: completed.

### Phase 7 — Service page rewrite
1. Replace API-backed service actions with direct Task Scheduler/service helpers.
2. Read daemon/task health from local helpers and the state file.
3. Keep installer/elevation flows available from the desktop app.

Status: completed.

### Phase 8 — GUI dependency/test refresh
1. Add `pyqtgraph` to the GUI extra and prerequisite checks.
2. Rewrite GUI/widget tests for the local desktop architecture.
3. Refresh stale validation tests that still referenced removed API behavior.

Status: completed.

### Phase 9 — Final validation and cleanup
1. Update plans and roadmap notes to reflect the simplified architecture.
2. Run full Ruff/pytest validation for the completed migration.

Status: completed.

## Notes
- The desktop GUI now uses direct local state/config/service integration throughout.
- Full validation completed with `590` passing tests.
