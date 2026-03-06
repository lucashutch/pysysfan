# pysysfan Development Plan

## Recent: Remove Linux Support (March 2026)

**Status:** ✅ Completed

### Problem
Linux support was experimental but had limited hardware compatibility:
- Most modern ThinkPads (P14s Gen 3, T14s Gen 3, etc.) have firmware-locked fan control
- PWM interface exists but is locked by embedded controller
- /proc/acpi/ibm/fan interface accepts commands but returns "Invalid argument"
- Only works on older ThinkPads or desktop systems with standard PWM

### Solution Implemented
1. **Removed Linux-specific modules:**
   - `src/pysysfan/platforms/linux.py` - Linux hardware manager
   - `src/pysysfan/platforms/linux_service.py` - Linux service manager
   - `src/pysysfan/install_linux.py` - Linux installer
   - `tests/test_linux_hardware.py` - Linux hardware tests
   - `tests/test_linux_service.py` - Linux service tests

2. **Updated platform detection:**
   - `detect_platform()` now raises `PlatformNotSupportedError` on Linux
   - Removed Linux platform detection from all factory functions

3. **Updated CLI:**
   - Removed Linux-specific error messages
   - Simplified admin checks (Windows only)
   - Removed `--user` option from service commands (was Linux-only)
   - Updated service command docstrings

4. **Updated documentation:**
   - `README.md` - Now states Windows-only with note about future Linux support
   - `docs/linux.md` - Removed
   - `TODO.md` - Added note about potential future Linux support
   - `pyproject.toml` - Removed Linux dependencies and entry points

5. **Updated tests:**
   - `tests/test_platform_detection.py` - Tests now expect Linux to raise errors
   - `src/pysysfan/hardware.py` - Lazy load HardwareManager to avoid import errors on Linux

### Files Modified
- ✅ `src/pysysfan/platforms/__init__.py` - Removed Linux support
- ✅ `src/pysysfan/platforms/linux.py` - Deleted
- ✅ `src/pysysfan/platforms/linux_service.py` - Deleted
- ✅ `src/pysysfan/install_linux.py` - Deleted
- ✅ `src/pysysfan/hardware.py` - Lazy loading for cross-platform compatibility
- ✅ `src/pysysfan/cli.py` - Removed Linux-specific code
- ✅ `tests/test_platform_detection.py` - Updated for Windows-only
- ✅ `tests/test_linux_hardware.py` - Deleted
- ✅ `tests/test_linux_service.py` - Deleted
- ✅ `README.md` - Updated to Windows-only
- ✅ `docs/linux.md` - Deleted
- ✅ `TODO.md` - Added note about future Linux support
- ✅ `pyproject.toml` - Removed Linux dependencies

### Results
- Cleaner codebase focused on Windows
- No confusion about Linux compatibility
- Clear messaging that Linux support may be revisited in the future

---

## Previous: Performance Optimization (March 2026)

**Status:** ✅ Completed

### Problem
Startup time was slow (~4 seconds) due to:
1. Synchronous update check blocking startup (~1 second)
2. Hardware initialization with LHM/.NET runtime (~3 seconds)

### Solution Implemented
1. **Parallel Initialization**
   - Update check now runs in background thread immediately
   - Hardware initialization runs in main thread simultaneously
   - Wait for update check thread before entering control loop (5s timeout)

2. **Always-On Update Checks**
   - Removed `--no-check` CLI option since checks are now non-blocking
   - Update checks always run on startup (when `auto_check: true` in config)

3. **Timing Instrumentation**
   - Added startup timing logs for debugging
   - Log total startup duration

### Files Modified
- ✅ `src/pysysfan/daemon.py` - Parallel initialization, background update check
- ✅ `src/pysysfan/cli.py` - Removed `--no-check` option

### Results
- **Startup improvement:** 4s → 3s (25% faster)
- Update checks no longer impact startup speed
- Maintained all safety guarantees (atexit handlers, signal handlers)

---

## Previous: Bug Fix Plan (March 2026)

## Overview
Fix two bugs identified in TODO.md:
1. **Flickering CLI updates in monitor mode** - Rich Live display causes visual artifacts
2. **0% fan speed doesn't turn off fan** - LHM SetSoftware(0) sets minimum speed, not off

**Status:** Planning Phase
**Date:** March 2026

---

## Bug 1: Flickering CLI Updates in Monitor Mode

### Problem
The `pysysfan monitor` command shows flickering/corrupted display due to:
- `refresh_per_second=4` updates every 0.25s but interval is 2.0s by default
- `screen=False` writes directly to terminal causing artifacts
- Table rebuilds cause visual jumps

### Location
`src/pysysfan/cli.py`, `monitor()` command (lines 1126-1177)

### Solution
Modify the `Live` constructor to:
1. Set `screen=True` - Use alternate screen buffer (eliminates flickering)
2. Reduce `refresh_per_second` to 1 - Match the typical 2s interval
3. Add `vertical_overflow="visible"` - Prevent layout shifts

### Implementation
```python
# Line 1156 in cli.py
with Live(
    console=console, 
    refresh_per_second=1,  # Changed from 4
    screen=True,  # Changed from False - uses alternate buffer
    vertical_overflow="visible"
) as live:
```

### Testing
- Run `pysysfan monitor` with different intervals (0.5s, 2s, 5s)
- Verify smooth updates without flickering
- Test Ctrl+C exit behavior with screen=True

---

## Bug 2: 0% Fan Speed Doesn't Turn Off Fan

### Problem
When setting fan speed to 0%:
- LHM's `SetSoftware(0)` sets minimum PWM duty cycle (motherboard dependent)
- Most motherboards enforce a minimum fan speed (e.g., 20-30%)
- To truly stop a fan, must release software control back to BIOS

### Location
`src/pysysfan/platforms/windows.py`, `set_fan_speed()` (lines 199-226)

### Solution
Implement true "off" mode by calling `SetDefault()` when percent == 0:

1. **Track off-mode state** - Remember which fans are currently off
2. **0% handling** - Call `SetDefault()` instead of `SetSoftware(0)`
3. **Re-enable handling** - When transitioning from 0% to >0%, ensure software control is active
4. **Config option** - Add `allow_fan_off` (default True) to FanConfig

### Implementation Steps

#### Step 1: Update Base Hardware Manager
**File:** `src/pysysfan/platforms/base.py`

Add tracking for fans in off mode:
```python
class BaseHardwareManager(ABC):
    def __init__(self):
        self._off_mode_fans: set[str] = set()  # Track fans currently off
    
    @abstractmethod
    def set_fan_speed(self, control_identifier: str, percent: float) -> None:
        """Set fan speed. When percent==0, may turn fan off entirely."""
        pass
```

#### Step 2: Implement Windows-Specific Logic  
**File:** `src/pysysfan/platforms/windows.py`

Modify `set_fan_speed()`:
```python
def set_fan_speed(self, control_identifier: str, percent: float) -> None:
    self._ensure_open()
    
    if control_identifier not in self._controls:
        self.scan()
    
    if control_identifier not in self._controls:
        raise ValueError(f"Control '{control_identifier}' not found")
    
    sensor = self._controls[control_identifier]
    
    if percent <= 0:
        # Turn fan off by releasing software control
        try:
            sensor.Control.SetDefault()
            self._off_mode_fans.add(control_identifier)
            logger.debug(f"Turned off {control_identifier} (SetDefault)")
        except Exception as e:
            logger.error(f"Failed to turn off {control_identifier}: {e}")
            raise
    else:
        # Normal speed setting
        percent = min(100.0, percent)
        try:
            # If fan was off, we may need to re-enable software control
            # Some LHM versions require explicit SetSoftware() call first
            sensor.Control.SetSoftware(percent)
            self._off_mode_fans.discard(control_identifier)
            logger.debug(f"Set {control_identifier} to {percent:.1f}%")
        except Exception as e:
            logger.error(f"Failed to set {control_identifier} to {percent}%: {e}")
            raise
```

#### Step 3: Update Daemon Control Logic
**File:** `src/pysysfan/daemon.py`

In `_run_once()`, add logging for off mode:
```python
target_pct = curve.evaluate(agg_temp)

# Check if fan should be turned off completely
if target_pct <= 0:
    logger.info(f"Fan '{fan_name}': turning OFF (0% target)")
else:
    logger.debug(f"Fan '{fan_name}': {agg_temp:.1f}°C → {target_pct:.1f}%")

self._hw.set_fan_speed(fan_cfg.fan_id, target_pct)
```

#### Step 4: Add Config Option (Optional)
**File:** `src/pysysfan/config.py`

Add `allow_fan_off` to FanConfig:
```python
@dataclass
class FanConfig:
    fan_id: str
    curve: str
    temp_ids: list[str]
    aggregation: str = "max"
    header_name: str | None = None
    allow_fan_off: bool = True  # When False, 0% = minimum speed, not off
```

Update loading/saving logic to handle this field.

---

## Files to Modify

1. ✅ `src/pysysfan/cli.py` - Fix monitor flickering
2. ✅ `src/pysysfan/platforms/base.py` - Add off mode tracking
3. ✅ `src/pysysfan/platforms/windows.py` - Implement SetDefault logic
4. ✅ `src/pysysfan/daemon.py` - Handle off mode logging
5. ⬜ `src/pysysfan/config.py` - Add optional `allow_fan_off` setting

---

## Testing Plan

### Monitor Flickering Tests
- [ ] Run `pysysfan monitor -i 0.5` - Should update smoothly every 0.5s
- [ ] Run `pysysfan monitor -i 2.0` - Default interval, no flicker
- [ ] Press Ctrl+C - Should exit cleanly without screen corruption

### Fan Off Mode Tests  
- [ ] Set curve to "off" special curve
- [ ] Verify `SetDefault()` is called (check logs)
- [ ] Verify fan RPM goes to 0 (or motherboard minimum)
- [ ] Increase temperature - fan should restart normally
- [ ] Test hysteresis with off mode transitions
- [ ] Test daemon shutdown restores all fans to BIOS control
- [ ] Test config reload while fan is off

### Edge Cases
- [ ] Multiple fans going off/on simultaneously
- [ ] Fan off mode with very short poll interval (< 1s)
- [ ] Config with `allow_fan_off: false` - should use SetSoftware(0)

---

## Implementation Order

1. **Bug 1 (Monitor Flickering)** - Simple, isolated change
2. **Bug 2 - Step 1** - Add base class tracking
3. **Bug 2 - Step 2** - Implement Windows SetDefault logic
4. **Bug 2 - Step 3** - Update daemon logging
5. **Bug 2 - Step 4** - Add config option (optional)
6. **Write/update tests**
7. **Run linter and formatter**
8. **Update TODO.md** - Mark bugs as fixed

---

## Code Quality Requirements

- All changes must pass `uv run ruff check --fix`
- All changes must pass `uv run ruff format`
- All tests must pass `uv run pytest tests/`
- Add/update tests for new functionality
- Maintain type hints throughout

---

## Notes

### Why SetDefault() for Off Mode?
- LHM's `SetSoftware()` always applies a PWM duty cycle
- Motherboard firmware typically enforces minimum duty cycle (safety feature)
- `SetDefault()` releases software control, allowing firmware to decide
- Most firmware will stop fans entirely when no software control is active and temps are low

### Platform Considerations
- This implementation is Windows-specific via LHM
- Linux implementation would need different approach (likely writing to pwm_enable sysfs)
- Base class design allows platform-specific implementations

### Safety
- `restore_defaults()` already handles cleanup on exit
- Fans will return to BIOS control when daemon stops
- No risk of fans staying off after daemon exit
