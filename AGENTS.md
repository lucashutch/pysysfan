# AI Agent Instructions

When working in this repository:
- Always update `plan.md` and `TODO.md` as you complete phases.
- Ensure all code is modular, type-hinted, and commented.
- When creating new features, include unit tests in `tests/`.
- Ensure `pyproject.toml` is up-to-date with dependencies.
- Follow PEP 8 guidelines and use the existing style.
- Run `uv run ruff check --fix` and `uv run ruff format` before committing.
- Run `uv run pytest tests/` to verify all tests pass.
- Maintain the `pysysfan` naming convention throughout.

## Project Structure

- `src/pysysfan/cli.py` — Main CLI entry point (Click groups: `lhm`, `config`, `service`, etc.)
- `src/pysysfan/hardware.py` — LHM hardware manager (sensor reads, fan control)
- `src/pysysfan/config.py` — YAML config loading/saving
- `src/pysysfan/curves.py` — Fan curve interpolation + hysteresis
- `src/pysysfan/daemon.py` — Fan control loop
- `src/pysysfan/service.py` — Windows Task Scheduler integration
- `src/pysysfan/lhm/` — LHM DLL management and GitHub release download
- `src/pysysfan/pawnio/` — PawnIO driver detection and installer download
- `src/pysysfan/updater.py` — Self-update logic (GitHub release check, `uv tool install`)
- `src/pysysfan/install.py` — Independent entry points for `pysysfan-install-lhm` and `pysysfan-install-pawnio`
- `install-pysysfan.bat` — One-click Windows batch installer

## Entry Points

- `pysysfan` — Main CLI (`pysysfan.cli:main`)
  - Subcommands: `lhm`, `config`, `run`, `service`, `update`, `scan`, `status`, `monitor`
- `pysysfan-install-lhm` — Standalone LHM download (`pysysfan.install:install_lhm`)
- `pysysfan-install-pawnio` — Standalone PawnIO install (`pysysfan.install:install_pawnio`)

## Key Conventions

- LHM and PawnIO download modules use version marker files (`.lhm_version`, `.pawnio_version`) in `~/.pysysfan/` to avoid re-downloading when already up-to-date.
- PawnIO installer requires elevation — use `powershell Start-Process -Verb RunAs`.
- All downloads go through the GitHub releases API.
