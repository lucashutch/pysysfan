# AI Agent Instructions

## Workflow Rules

- **Always create a plan** in `.plans/` with a clear breakdown of steps before writing any code. never commit a raw plan.md to the repo.
- **Never commit to `main`** — always create a feature branch and open a PR for review.
- Update `TODO.md` as issues are completed.
- Run `uv run ruff check --fix` and `uv run ruff format` before committing.
- Run `uv run pytest tests/` to verify all tests pass.
- All new features need unit tests in `tests/`.
- Keep code modular, type-hinted, and PEP 8–compliant.
- Keep `pyproject.toml` dependencies up-to-date.

## Sub-Agent Usage

**Aggressively delegate to sub-agents.** Prefer spawning a sub-agent over manually chaining search and read operations in the main context. Use sub-agents for:

- **Exploration** — reading multiple files, mapping a module's API, understanding an unfamiliar area of the codebase. Use the `Explore` agent.
- **Research** — fetching docs, checking PyPI/GitHub, comparing approaches.
- **Parallel independent work** — two sub-agents can explore different parts of the codebase simultaneously.
- **Large refactors** — delegate scoped subtasks (e.g. "update all callers of X") to a sub-agent rather than doing it manually file-by-file.

Keep the main context lean. If a task requires reading more than ~3 files to gather context, use a sub-agent instead.

## Project Structure

| Path | Purpose |
|------|---------|
| `src/pysysfan/cli.py` | Main CLI (`scan`, `run`, `status`, `monitor`, `config`, `service`, `update`) |
| `src/pysysfan/hardware.py` | LHM hardware manager — sensor reads, fan control |
| `src/pysysfan/config.py` | YAML config loading/saving/validation |
| `src/pysysfan/curves.py` | Fan curve interpolation + hysteresis |
| `src/pysysfan/daemon.py` | Fan control loop |
| `src/pysysfan/service_entry.py` | Windows service entry point (`pysysfan-service`) |
| `src/pysysfan/profiles.py` | Profile management |
| `src/pysysfan/watcher.py` | Config file watcher |
| `src/pysysfan/notifications.py` | System notifications |
| `src/pysysfan/temperature.py` | Temperature aggregation helpers |
| `src/pysysfan/cache.py` | Sensor value caching |
| `src/pysysfan/state_file.py` | Daemon state persistence |
| `src/pysysfan/history_file.py` | Sensor history persistence |
| `src/pysysfan/lhm/` | LHM DLL management and GitHub release download |
| `src/pysysfan/pawnio/` | PawnIO driver detection and installer download |
| `src/pysysfan/platforms/` | Platform abstraction (`base.py`, `windows.py`, `windows_service.py`) |
| `src/pysysfan/api/` | REST API (routes under `api/routes/`) |
| `src/pysysfan/gui/desktop/` | PyQt desktop UI (pages, theme, sidebar, plotting) |
| `src/pysysfan/updater.py` | Self-update logic (GitHub release check, `uv tool install`) |
| `src/pysysfan/install.py` | Standalone LHM/PawnIO install entry points |
| `scripts/install-pysysfan.bat` | One-click Windows batch installer |

## Entry Points

| Command | Target |
|---------|--------|
| `pysysfan` | `pysysfan.cli:main` |
| `pysysfan-gui` | `pysysfan.gui:main` |
| `pysysfan-service` | `pysysfan.service_entry:main` |
| `pysysfan-install-lhm` | `pysysfan.install:install_lhm` |
| `pysysfan-install-pawnio` | `pysysfan.install:install_pawnio` |

## Key Conventions

- LHM and PawnIO use version marker files (`.lhm_version`, `.pawnio_version`) in `~/.pysysfan/` to skip re-downloads.
- PawnIO installer requires elevation — use `powershell Start-Process -Verb RunAs`.
- All downloads go through the GitHub releases API.

## Desktop UI

- Icons: Heroicons only (`https://heroicons.com/`). No emoji, Unicode glyphs, or extra icon packs.
- Theme is palette-aware — derive from `QPalette` tokens (`window`, `base`, `text`, `raised`, `panel`, `card`, `muted`, `border`, `accent`, `graph`). Never hard-code a separate palette.
- Visual language: flat, boxy, square corners, borderless surfaces, thin neutral separators. No shadows or gradients.
- Accent colors (use sparingly — status/emphasis only): blue `#60a5fa`, green `#34d399`, amber `#f59e0b`, red `#ef4444`, cyan `#22d3ee`, pink `#f472b6`, purple `#a78bfa`.
