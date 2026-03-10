# TODO

## Recently completed

- [x] 2026-03-10 — Repair the Windows Service tab flow so GUI-triggered service actions request elevation clearly and scheduled tasks run with the installing user's home-directory context.
- [x] 2026-03-10 — Refresh the Windows installer to support daemon-only or GUI installs, create a Start Menu app shortcut, and remove the obsolete Linux installer script.
- [x] 2026-03-10 — Add a desktop GUI minimize-to-tray preference on the Service page and cover it with targeted GUI tests.
- [x] 2026-03-10 — Rework the README and Windows guide for the polished Windows-first installer and GUI launch story.

### Desktop GUI
- [ ] Continue dashboard stat-card polish and information hierarchy cleanup.
- [ ] Refine curve plotting visuals and small-screen scaling behavior.
- [ ] Improve fan assignment UX with clearer sensor labels and multi-sensor editing.
- [ ] Expand profile management and profile switching polish in the desktop app.

### Core behavior
- [ ] Continue modularizing larger files in the desktop GUI and daemon paths.
- [ ] Keep type coverage improving across the codebase.
- [ ] Tighten config validation around aggregation values and user-facing error messages.

### Tooling and packaging
- [ ] Review whether future standalone GUI packaging should ship a generated `.ico` and bundled third-party notice set.
- [ ] Keep installer scripts aligned with the public installation story.
- [ ] Revisit any remaining legacy GUI or packaging paths and remove them once fully superseded.

## Improve Daemon and GUI idle resource usage
- [ ] Profile the daemon and desktop app to identify any remaining CPU or memory usage optimizations, especially around idle periods.
- [ ] Ensure gui doesnt needlessly refresh or poll when the daemon is idle or when the dashboard is not visible.
- [ ] Consider adding a dynamic polling adjustment in the daemon based on system load or idle state to further reduce resource usage when the system is not under heavy load.