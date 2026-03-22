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
- ALWAYS create a new plan in the .plans witha clear breakdown of steps before coding.
- NEVER commit to main, always create a feature branch and open a PR for review.

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

## Desktop UI

- Use Heroicons from https://heroicons.com/ for all new in-product icons. Do not introduce emoji, Unicode glyph icons, or additional icon packs unless a specific asset already exists for branding.
- Treat the desktop theme as palette-aware rather than fixed-theme. The shared styles derive `window`, `base`, `text`, `raised`, `panel`, `card`, `muted`, `border`, `accent`, and `graph` tokens from `QPalette`, so keep new surfaces aligned with those tokens instead of hard-coding a separate palette.
- The visual language is flat and boxy. Prefer square or near-square corners, borderless surfaces, and thin neutral separators over heavy outlines, shadows, or gradients. Most controls intentionally use `border: none` or a 0 to 4px radius; larger containers only use modest rounding when they need to read as shells.
- Use color sparingly and intentionally. Neutral grays carry the layout, while accents are reserved for status and emphasis: blue `#60a5fa`, green `#34d399`, amber `#f59e0b`, red `#ef4444`, cyan `#22d3ee`, pink `#f472b6`, and purple `#a78bfa`. Keep those colors for component bars, alerts, and chart series rather than decorative fills.
- When styling new desktop UI, match the existing flat management pages and dashboard rows: solid fills, compact spacing, uppercase or bold section labels, and accent bars instead of decorative chrome.
