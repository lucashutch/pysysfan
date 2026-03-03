# pysysfan Development Plan

## Phased Implementation

Each phase is an atomic, testable unit (feature branch / commit).

---

### Phase 1: Project Scaffolding & LHM Integration ✅
- [x] Project structure (`pyproject.toml`, `src/pysysfan/`)
- [x] LHM DLL loader via `pythonnet` (`src/pysysfan/hardware.py`)
  - Uses `netfx` runtime + net472 LHM build (pre-installed on all Win 10/11)
- [x] LHM download helper (`src/pysysfan/lhm/download.py`)
- [x] CLI entry point with `pysysfan scan`, `pysysfan lhm download/info`
- [x] Housekeeping: `README.md`, `LICENSE`, `AGENTS.md`, `THIRD_PARTY_LICENSES.md`

**Verified**: `uv run pysysfan scan` detects hardware sensors and controllable fan outputs.

---

### Phase 2: Config System & Fan Curves ✅
- [x] YAML config schema (fans, sensors, curves, hysteresis)
- [x] `Config` dataclass + loader (`src/pysysfan/config.py`)
- [x] `FanCurve` with linear interpolation + hysteresis (`src/pysysfan/curves.py`)
- [x] Preset curves: `silent`, `balanced`, `performance`
- [x] CLI: `pysysfan config init`, `pysysfan config validate`, `pysysfan config show`
- [x] 27 unit tests — all passing (`uv run pytest`)

---

### Phase 3: Fan Control Loop ✅
- [x] `FanDaemon` control loop (`src/pysysfan/daemon.py`)
- [x] Poll sensors → evaluate curves → set fan speeds
- [x] Graceful shutdown: restore BIOS fan control on exit/crash
- [x] `atexit` + signal handlers for safety
- [x] CLI: `pysysfan run`, `pysysfan run --once`

---

### Phase 4: Windows Startup (Task Scheduler) ✅
- [x] Task Scheduler integration via `schtasks.exe` (`src/pysysfan/service.py`)
  - Runs as SYSTEM at boot, with highest privileges
- [x] CLI: `pysysfan service install`, `pysysfan service uninstall`, `pysysfan service status`

---

### Phase 5: Status & Monitoring CLI ✅
- [x] `pysysfan status` — formatted snapshot of all sensors
- [x] `pysysfan monitor` — live-updating terminal dashboard (using `rich.Live`)

---

### Phase 6: Installer Script ✅
- [x] PawnIO driver download module (`src/pysysfan/pawnio/`)
  - Driver status detection via `sc query`
  - GitHub release download and installer launch
- [x] Independent install entry points (`src/pysysfan/install.py`)
  - `pysysfan-install-lhm` — standalone LHM download
  - `pysysfan-install-pawnio` — standalone PawnIO install
- [x] Batch installer (`install-pysysfan.bat`)
  - Double-click runnable, install/upgrade detection
  - Installs UV, pysysfan, LHM, and PawnIO
- [x] Unit tests for new modules (18 tests)

---

### Future Phases → see [TODO.md](TODO.md)

