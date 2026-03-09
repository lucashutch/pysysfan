# Simplify GUI / Remove HTTP API Plan

## Goal

Replace the local HTTP API with a lightweight local state-file model so the daemon, CLI, and future GUI can share runtime state without FastAPI.

## Phases

### Phase 0 — State file foundation
1. Add a dedicated state file module.
2. Support atomic writes and safe reads.
3. Add tests for stale, missing, and corrupt state files.

### Phase 1 — Daemon state snapshots
1. Have the daemon write runtime snapshots to disk every control pass.
2. Include active profile, current sensors, fan targets, and recent alerts.
3. Remove in-process API state tracking from the daemon.
4. Lower the default poll interval to 1 second.

### Phase 2 — Remove HTTP API layer
1. Delete the FastAPI server/client package and API-only tests.
2. Remove API runtime options from the daemon and CLI.
3. Remove API-only dependencies from project metadata.

### Phase 3 — Service/CLI alignment
1. Add missing CLI service commands for start/stop/enable/disable/restart.
2. Add stop support to the Windows service helper.
3. Change `monitor` default refresh interval to 1 second.

## Notes
- The GUI rewrite to consume the state file lands in later phases.
- During phases 0-3, the focus is core daemon/service refactoring and dependency cleanup.
