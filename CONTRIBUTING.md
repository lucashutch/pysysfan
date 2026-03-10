# Contributing to PySysFan

Thanks for contributing.

This repository is actively evolving around a **Windows-first** hardware control workflow, so changes should stay practical, tested, and easy to audit.

## Supported development environment

- Python **3.11+**
- `uv`
- Windows 10/11 for hardware-facing work
- Optional GUI dependencies for desktop changes

Most unit tests run cross-platform, but hardware integration and service validation are Windows-specific.

## Getting started

```powershell
git clone https://github.com/lucashutch/pysysfan.git
cd pysysfan
uv sync --extra gui --group dev
```

If you only need the default CLI/runtime dependencies:

```powershell
uv sync --group dev
```

## Required workflow

Before making code changes:

1. Create a feature branch. Do not work directly on `main`.
2. Create a new plan file in `.plans/` for the task.
3. Update the top-level `plan.md` with the current work.
4. Keep `TODO.md` in sync as phases are completed.

Expected branch naming examples:

- `feature/gui-icon-refresh`
- `fix/windows-service-status`
- `docs/readme-cleanup`

## Repository map

Key paths in the current codebase:

- `src/pysysfan/cli.py` — main CLI entry point
- `src/pysysfan/config.py` — YAML config load/save and defaults
- `src/pysysfan/curves.py` — interpolation and static curve parsing
- `src/pysysfan/daemon.py` — control loop
- `src/pysysfan/platforms/windows.py` — Windows hardware implementation
- `src/pysysfan/platforms/windows_service.py` — Task Scheduler integration
- `src/pysysfan/gui/desktop/` — native PySide6 desktop app
- `src/pysysfan/lhm/` — LibreHardwareMonitor download and bootstrap helpers
- `src/pysysfan/pawnio/` — PawnIO download and elevation helpers
- `tests/` — pytest suite
- `docs/` — end-user documentation

## Coding expectations

Please keep changes:

- modular
- type-hinted
- commented where behavior is non-obvious
- consistent with existing naming and structure
- focused on the smallest viable change set

General rules:

- follow PEP 8
- prefer explicit, testable helpers over deeply nested logic
- keep public docs and user-facing messages aligned with actual behavior
- add or update tests for new features and regressions
- update `pyproject.toml` if dependencies or packaging behavior change

## Documentation expectations

Update documentation whenever behavior changes materially.

That includes, when relevant:

- `README.md`
- files in `docs/`
- `THIRD_PARTY_LICENSES.md`
- `CONTRIBUTING.md`
- `TODO.md`
- `plan.md`
- the task plan under `.plans/`

## Validation commands

Run these before opening a pull request:

```powershell
uv run ruff check --fix
uv run ruff format
uv run pytest tests/
```

For GUI-focused work, also run targeted tests while iterating.

Examples:

```powershell
uv run python -m pytest --no-cov tests/test_gui_desktop.py tests/test_gui_dashboard.py
uv run python -m pytest --no-cov tests/test_windows_service.py
```

## Testing guidance

- Put new tests in `tests/`
- Use descriptive test names
- Mock hardware or OS-specific boundaries when possible
- Avoid requiring real hardware for unit tests
- Keep tests deterministic and isolated

For GUI changes:

- prefer widget-level tests with `pytest-qt`
- verify user-visible behavior, not only implementation details
- keep the desktop app import boundary lazy unless GUI entry points are explicitly used

## Pull requests

A good pull request should:

- explain the problem being solved
- describe the user-facing effect
- mention documentation changes
- mention test coverage and validation run
- stay scoped to one change set when practical

Checklist:

- [ ] feature branch used
- [ ] `.plans/`, `plan.md`, and `TODO.md` updated
- [ ] code formatted and linted
- [ ] tests added or updated as needed
- [ ] docs refreshed
- [ ] no unrelated refactors slipped in

## Licensing and third-party components

If your change adds or changes dependencies, also update [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

Be careful with anything that bundles or redistributes third-party binaries, especially:

- LibreHardwareMonitor
- PySide6 / Qt
- PawnIO

If redistribution terms are unclear, keep the component external and document the decision.

## Questions

If a change touches packaging, Windows hardware behavior, or GUI runtime boundaries, keep the PR especially explicit about the reasoning and validation steps.
