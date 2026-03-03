# Linux Support Implementation Plan (Refined)

## Overview
Extend pysysfan to support Linux systems (desktops and laptops including ThinkPad P14s Gen3) while maintaining full Windows compatibility. The implementation will use platform detection and abstraction to provide a unified API.

## User Decisions
1. **Primary target**: ThinkPad P14s Gen3, with broad hardware support as secondary goal
2. **Service type**: System-wide systemd service (runs when not logged in)
3. **Sensor library**: Use `pysensors` (Python bindings for libsensors) - don't reinvent the wheel
4. **ThinkPad setup**: Auto-enable `thinkpad_acpi` fan_control module

## Architecture Approach

```
src/pysysfan/
├── platforms/
│   ├── __init__.py          # Platform detection & factory
│   ├── base.py              # Abstract HardwareManager base class
│   ├── windows.py           # Windows LHM/PawnIO implementation (moved from hardware.py)
│   ├── windows_service.py   # Windows Task Scheduler integration
│   ├── linux.py             # Linux sysfs/pysensors implementation (new)
│   └── linux_service.py     # Linux systemd support (new)
├── hardware.py              # Re-export for backward compatibility (factory pattern)
├── config.py                # Unchanged (platform-agnostic)
├── curves.py                # Unchanged (platform-agnostic)
└── daemon.py                # Unchanged (uses hardware.py factory)
```

## Implementation Phases

---

### Phase 1: Hardware Abstraction Layer (HAL)
**Goal**: Create abstract base class and refactor existing Windows code
**Estimated Time**: 2-3 hours

#### 1.1 Create Base Hardware Manager
**File**: `src/pysysfan/platforms/base.py`

Define abstract class `BaseHardwareManager` with methods:
- `open()` / `close()` / `__enter__` / `__exit__`
- `scan() -> HardwareScanResult`
- `get_temperatures() -> list[SensorInfo]`
- `get_fan_speeds() -> list[SensorInfo]`
- `set_fan_speed(identifier: str, percent: float)`
- `restore_defaults()`

Define shared dataclasses:
- `HardwareScanResult` - temperatures, fans, controls, all_sensors
- `SensorInfo` - hardware_name, hardware_type, sensor_name, sensor_type, identifier, value, min_value, max_value
- `ControlInfo` - hardware_name, sensor_name, identifier, current_value, has_control
- `SensorKind` enum - VOLTAGE, CURRENT, POWER, CLOCK, TEMPERATURE, LOAD, FAN, CONTROL, etc.

#### 1.2 Refactor Windows Implementation
**File**: `src/pysysfan/platforms/windows.py`

Move current `hardware.py` implementation:
- Rename class to `WindowsHardwareManager(BaseHardwareManager)`
- Keep all LHM/pawnio logic intact
- Import and use base classes from `base.py`
- Add Windows platform check using `sys.platform.startswith('win')`

**File**: `src/pysysfan/platforms/windows_service.py`

Move Task Scheduler code from `service.py`:
- `install_task()` - Create scheduled task via `schtasks.exe`
- `uninstall_task()` - Remove scheduled task
- `get_task_status()` - Query task status

#### 1.3 Create Platform Factory
**File**: `src/pysysfan/platforms/__init__.py`

Functions:
```python
def detect_platform() -> Literal["windows", "linux"]:
    """Detect current platform."""
    if sys.platform.startswith('win'):
        return "windows"
    elif sys.platform.startswith('linux'):
        return "linux"
    else:
        raise PlatformNotSupportedError(f"Platform '{sys.platform}' not supported")

def get_hardware_manager() -> Type[BaseHardwareManager]:
    """Get the appropriate HardwareManager class for current platform."""
    platform = detect_platform()
    if platform == "windows":
        from .windows import WindowsHardwareManager
        return WindowsHardwareManager
    elif platform == "linux":
        from .linux import LinuxHardwareManager
        return LinuxHardwareManager
```

#### 1.4 Update Main Hardware Module
**File**: `src/pysysfan/hardware.py`

Replace contents with:
```python
"""Hardware manager factory - re-export for backward compatibility."""
from pysysfan.platforms import get_hardware_manager

HardwareManager = get_hardware_manager()

# Re-export types for backward compatibility
from pysysfan.platforms.base import (
    SensorKind,
    SensorInfo,
    ControlInfo,
    HardwareScanResult,
    BaseHardwareManager,
)
```

**Verification**:
- [ ] All existing Windows tests pass without modification
- [ ] Import `from pysysfan.hardware import HardwareManager` still works
- [ ] `HardwareManager` is callable/usable as a class

---

### Phase 2: Linux Hardware Implementation
**Goal**: Implement Linux pysensors and sysfs-based hardware access
**Estimated Time**: 4-6 hours

#### 2.1 Linux Hardware Manager
**File**: `src/pysysfan/platforms/linux.py`

Implement `LinuxHardwareManager(BaseHardwareManager)`:

```python
class LinuxHardwareManager(BaseHardwareManager):
    """Linux hardware access using lm-sensors (pysensors) and sysfs fallback."""
    
    def open(self):
        # Initialize pysensors
        import sensors
        sensors.init()
        self._sensors = sensors
        
        # Detect hardware capabilities
        self._detect_capabilities()
        
    def _detect_capabilities(self):
        """Detect what sensors and controls are available."""
        # Use pysensors to enumerate chips
        # Map to our SensorInfo/ControlInfo structures
        # Detect ThinkPad, Dell, or generic SuperIO
        
    def scan(self) -> HardwareScanResult:
        # Iterate through pysensors chips
        # Build HardwareScanResult with all sensor types
        # Identify controllable fans (have pwm* files)
        
    def set_fan_speed(self, identifier: str, percent: float):
        # Parse identifier format: "hwmonX/pwmY" or "thinkpad/fan"
        # For hwmon: write to /sys/class/hwmon/hwmonX/pwmY (0-255 range)
        # For ThinkPad: write level (0-7, auto, disengaged) to /proc/acpi/ibm/fan
        
    def restore_defaults(self):
        # hwmon: echo 0 > pwmY_enable (return to BIOS)
        # ThinkPad: echo "level auto" > /proc/acpi/ibm/fan
```

#### 2.2 Identifier Format for Linux
Standardize Linux sensor identifiers:
- **Temperatures**: `/sys/class/hwmon/hwmon0/temp1_input` or `hwmon0/temp1`
- **Fans**: `/sys/class/hwmon/hwmon0/fan1_input` or `hwmon0/fan1`
- **Controls**: `/sys/class/hwmon/hwmon0/pwm1` or `thinkpad/fan`

#### 2.3 ThinkPad Auto-Setup
**File**: `src/pysysfan/platforms/linux.py` (within LinuxHardwareManager.open())

Check for ThinkPad and auto-enable:
```python
def _ensure_thinkpad_fan_control(self):
    """Ensure thinkpad_acpi has fan_control enabled."""
    thinkpad_fan_path = Path("/proc/acpi/ibm/fan")
    if not thinkpad_fan_path.exists():
        return  # Not a ThinkPad or module not loaded
        
    # Check if fan control is available
    try:
        content = thinkpad_fan_path.read_text()
        if "level:" not in content:
            # Fan control not enabled, try to enable
            self._enable_thinkpad_fan_control()
    except PermissionError:
        logger.warning("Cannot access ThinkPad fan control. Run as root.")

def _enable_thinkpad_fan_control(self):
    """Auto-enable fan_control parameter."""
    modprobe_path = Path("/etc/modprobe.d/thinkpad-pysysfan.conf")
    if not modprobe_path.exists():
        # Create modprobe config
        modprobe_path.write_text("options thinkpad_acpi fan_control=1\n")
        logger.info("Created %s to enable ThinkPad fan control", modprobe_path)
        
        # Reload module (requires root)
        subprocess.run(["modprobe", "-r", "thinkpad_acpi"], check=False)
        subprocess.run(["modprobe", "thinkpad_acpi", "fan_control=1"], check=False)
```

#### 2.4 Dependencies
**File**: `pyproject.toml`

Add to `[project.optional-dependencies]`:
```toml
linux = [
    "pysensors>=0.0.4",  # Python bindings for lm-sensors
]
```

Also document system requirements in README:
```bash
# Ubuntu/Debian
sudo apt install lm-sensors libsensors-dev

# Fedora/RHEL
sudo dnf install lm_sensors lm_sensors-devel

# Arch
sudo pacman -S lm_sensors
```

**Verification**:
- [ ] `pysysfan scan` works on ThinkPad P14s Gen3
- [ ] Detects CPU temperature via k10temp
- [ ] Detects/discovers fan control
- [ ] Unit tests with mocked pysensors (no hardware required)

---

### Phase 3: Systemd Service Integration
**Goal**: Add system-wide systemd service support for Linux
**Estimated Time**: 2-3 hours

#### 3.1 Linux Service Module
**File**: `src/pysysfan/platforms/linux_service.py`

```python
def install_systemd_service(config_path: Path | None = None, system_wide: bool = True):
    """Install pysysfan as a systemd service.
    
    Args:
        config_path: Path to config file (default: ~/.pysysfan/config.yaml)
        system_wide: If True, install system-wide service requiring root.
                     If False, install user service.
    """
    
def uninstall_systemd_service(system_wide: bool = True):
    """Remove the pysysfan systemd service."""
    
def get_systemd_service_status(system_wide: bool = True) -> dict:
    """Get service status (running, enabled, etc.)."""
```

#### 3.2 Service Unit Templates

**System-wide service** (`/etc/systemd/system/pysysfan.service`):
```ini
[Unit]
Description=pysysfan - Python fan control daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/local/bin/pysysfan run --config %h/.pysysfan/config.yaml
Restart=always
RestartSec=5
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**User service** (`~/.config/systemd/user/pysysfan.service`):
```ini
[Unit]
Description=pysysfan - Python fan control daemon (user)
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/pysysfan run --config %h/.pysysfan/config.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

**Note**: Default to system-wide since fan control typically requires root.

#### 3.3 CLI Integration
**File**: `src/pysysfan/cli.py`

Update `service` command group:
```python
@main.group()
def service():
    """Manage pysysfan as a system service (Task Scheduler on Windows, systemd on Linux)."""
    pass

@service.command("install")
@click.option(
    "--user", "is_user", is_flag=True,
    help="Install as user service (Linux only). Windows always installs system-wide."
)
def service_install(is_user: bool):
    """Install pysysfan as a startup service."""
    from pysysfan.platforms import detect_platform
    
    if detect_platform() == "windows":
        from pysysfan.platforms.windows_service import install_task
        install_task()
    else:
        from pysysfan.platforms.linux_service import install_systemd_service
        install_systemd_service(system_wide=not is_user)
```

**Verification**:
- [ ] `pysysfan service install` creates systemd service
- [ ] `pysysfan service status` shows service state
- [ ] Service starts at boot and controls fans
- [ ] `pysysfan service uninstall` removes service

---

### Phase 4: Linux Installer Script
**Goal**: Create bash installer for Linux systems with auto-detection
**Estimated Time**: 2-3 hours

#### 4.1 Installer Script
**File**: `install-pysysfan.sh`

```bash
#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    elif [ -f /etc/arch-release ]; then
        echo "arch"
    else
        echo "unknown"
    fi
}

# Install system dependencies based on distro
install_dependencies() {
    local distro=$1
    echo "Installing system dependencies for $distro..."
    
    case "$distro" in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y lm-sensors libsensors-dev python3 python3-pip
            ;;
        fedora|rhel|centos)
            sudo dnf install -y lm_sensors lm_sensors-devel python3 python3-pip
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm lm_sensors python python-pip
            ;;
        *)
            echo -e "${YELLOW}Unknown distribution. Please install manually:${NC}"
            echo "  - lm-sensors (and development headers)"
            echo "  - Python 3.8+"
            exit 1
            ;;
    esac
}

# Detect package manager for Python packages
detect_python_tool() {
    if command -v uv &> /dev/null; then
        echo "uv"
    elif command -v pip3 &> /dev/null; then
        echo "pip3"
    elif command -v pip &> /dev/null; then
        echo "pip"
    else
        echo "none"
    fi
}

# Install pysysfan
install_pysysfan() {
    local tool=$1
    echo "Installing pysysfan using $tool..."
    
    case "$tool" in
        uv)
            uv tool install pysysfan[linux]
            ;;
        pip3|pip)
            $tool install --user pysysfan[linux]
            ;;
    esac
}

# Run sensors-detect
setup_sensors() {
    echo "Setting up hardware sensors..."
    echo -e "${YELLOW}This will auto-detect sensors. You may be prompted for sudo password.${NC}"
    
    # Run sensors-detect with auto-accept defaults
    sudo sensors-detect --auto || true
    
    # Load detected modules
    sudo sensors-detect --auto || true
}

# Detect ThinkPad and setup
detect_thinkpad() {
    if [ -d /sys/class/dmi/id ]; then
        product_name=$(cat /sys/class/dmi/id/product_name 2>/dev/null || echo "")
        if echo "$product_name" | grep -qi "thinkpad"; then
            echo -e "${GREEN}ThinkPad detected!$NC"
            echo "Setting up thinkpad_acpi fan control..."
            
            # Create modprobe config
            echo "options thinkpad_acpi fan_control=1" | sudo tee /etc/modprobe.d/thinkpad-pysysfan.conf > /dev/null
            
            # Reload module
            sudo modprobe -r thinkpad_acpi 2>/dev/null || true
            sudo modprobe thinkpad_acpi fan_control=1
            
            echo -e "${GREEN}ThinkPad fan control enabled.${NC}"
        fi
    fi
}

# Generate initial config
generate_config() {
    echo "Generating initial configuration..."
    if command -v pysysfan &> /dev/null; then
        pysysfan config init --force
    else
        echo -e "${YELLOW}pysysfan not in PATH. You may need to reload your shell or run:${NC}"
        echo "  source ~/.bashrc"
        echo "Then run: pysysfan config init"
    fi
}

# Install systemd service
install_service() {
    echo "Installing systemd service..."
    if command -v pysysfan &> /dev/null; then
        sudo pysysfan service install
        echo -e "${GREEN}Service installed. It will start automatically on boot.${NC}"
        echo "To start now: sudo systemctl start pysysfan"
    fi
}

# Main installation flow
main() {
    echo -e "${GREEN}=== pysysfan Linux Installer ===${NC}"
    echo ""
    
    # Check if running as root (we shouldn't be)
    if [ "$EUID" -eq 0 ]; then
        echo -e "${YELLOW}Warning: Running as root. The script will use sudo when needed.${NC}"
    fi
    
    # Detect and install dependencies
    DISTRO=$(detect_distro)
    echo "Detected distribution: $DISTRO"
    install_dependencies "$DISTRO"
    
    # Setup sensors
    setup_sensors
    
    # Detect ThinkPad
    detect_thinkpad
    
    # Install pysysfan
    PYTHON_TOOL=$(detect_python_tool)
    if [ "$PYTHON_TOOL" == "none" ]; then
        echo -e "${RED}Error: No Python package manager found. Install pip or uv first.${NC}"
        exit 1
    fi
    install_pysysfan "$PYTHON_TOOL"
    
    # Generate config
    generate_config
    
    # Ask about service installation
    echo ""
    read -p "Install pysysfan as a system service (runs at boot)? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        install_service
    fi
    
    echo ""
    echo -e "${GREEN}=== Installation Complete ===${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Edit config: pysysfan config show"
    echo "  2. Test daemon: sudo pysysfan run --once"
    echo "  3. Start service: sudo systemctl start pysysfan"
    echo "  4. View status: pysysfan service status"
    echo ""
    echo "For help: pysysfan --help"
}

# Run main
main "$@"
```

**Features**:
- Auto-detects distro (Ubuntu, Debian, Fedora, RHEL, Arch, Manjaro)
- Installs lm-sensors and Python dependencies
- Runs `sensors-detect` automatically
- Detects ThinkPad and enables fan_control
- Supports both `uv` and `pip` installation
- Optional systemd service installation
- Provides clear next steps

**Verification**:
- [ ] Script runs on Ubuntu 24.04
- [ ] Script runs on Fedora 40
- [ ] Script runs on Arch Linux
- [ ] Successfully installs on ThinkPad P14s Gen3
- [ ] Creates working config

---

### Phase 5: Testing & Documentation
**Goal**: Complete test coverage and documentation updates
**Estimated Time**: 3-4 hours

#### 5.1 Testing Strategy

**Unit Tests** (platform-agnostic, mock-based):

**File**: `tests/test_platform_detection.py`
```python
def test_detect_platform_windows():
    with patch('sys.platform', 'win32'):
        assert detect_platform() == "windows"

def test_detect_platform_linux():
    with patch('sys.platform', 'linux'):
        assert detect_platform() == "linux"

def test_detect_platform_unsupported():
    with patch('sys.platform', 'darwin'):
        with pytest.raises(PlatformNotSupportedError):
            detect_platform()
```

**File**: `tests/test_linux_hardware.py`
```python
class TestLinuxHardwareManager:
    def test_open_initializes_sensors(self, mock_sensors):
        # Mock pysensors module
        # Verify sensors.init() is called
        
    def test_scan_finds_temperatures(self, mock_sensors, mock_sysfs):
        # Mock sensors chip with temperature features
        # Verify scan returns correct SensorInfo objects
        
    def test_scan_finds_fans(self, mock_sensors, mock_sysfs):
        # Mock fan sensors
        # Verify RPM values extracted correctly
        
    def test_scan_finds_controls(self, mock_sysfs):
        # Mock pwm* files in sysfs
        # Verify ControlInfo created with has_control=True
        
    def test_set_fan_speed_pwm(self, tmp_path):
        # Create mock pwm file
        # Test writing percentage (converts to 0-255)
        
    def test_set_fan_speed_thinkpad(self, mock_thinkpad_fan):
        # Test writing to /proc/acpi/ibm/fan
        
    def test_restore_defaults_hwmon(self, tmp_path):
        # Test writing 0 to pwm*_enable
        
    def test_restore_defaults_thinkpad(self, mock_thinkpad_fan):
        # Test writing "level auto" to ThinkPad
```

**File**: `tests/test_linux_service.py`
```python
class TestLinuxService:
    def test_install_systemd_service(self, tmp_path):
        # Mock /etc/systemd/system/ directory
        # Verify service file created correctly
        
    def test_uninstall_systemd_service(self, tmp_path):
        # Create mock service file
        # Verify file removed and systemctl commands run
```

**Integration Tests** (require real hardware or VM):
- Test on ThinkPad P14s Gen3 (actual hardware)
- Test on desktop with common SuperIO chips
- Test service install/start/stop/uninstall cycle

**CI/CD**:
- Add Linux runners to GitHub Actions (Ubuntu, Fedora)
- Keep Windows CI intact

#### 5.2 Documentation

**Update README.md**:
```markdown
## Platform Support

### Windows
- Windows 10 or 11
- Administrator privileges required
- LibreHardwareMonitor + PawnIO driver

### Linux
- Kernel 5.x+ with hwmon support
- lm-sensors installed
- Root access for fan control (or udev rules)

#### Supported Hardware
- **ThinkPad laptops** (P14s, T14, X1 Carbon, etc.) - Full support via thinkpad_acpi
- **Generic desktops** - Any motherboard with hwmon driver (nct6775, it87, etc.)

## Installation

### Windows
```bash
# One-click installer
./install-pysysfan.bat
```

### Linux
```bash
# One-click installer
curl -sSL https://raw.githubusercontent.com/anomalyco/pysysfan/main/install-pysysfan.sh | bash

# Or manually:
# 1. Install dependencies
sudo apt install lm-sensors libsensors-dev  # Ubuntu/Debian
sudo dnf install lm_sensors lm_sensors-devel # Fedora
sudo pacman -S lm_sensors                     # Arch

# 2. Install pysysfan
pip install pysysfan[linux]

# 3. Setup sensors
sudo sensors-detect --auto

# 4. Generate config
pysysfan config init

# 5. (Optional) Install service
sudo pysysfan service install
```
```

**Create docs/linux.md**:
```markdown
# Linux Setup Guide

## ThinkPad Setup
ThinkPad laptops use the `thinkpad_acpi` kernel module for fan control.

The installer will automatically:
1. Create `/etc/modprobe.d/thinkpad-pysysfan.conf` with `fan_control=1`
2. Reload the module

If you need to do this manually:
```bash
echo "options thinkpad_acpi fan_control=1" | sudo tee /etc/modprobe.d/thinkpad-pysysfan.conf
sudo modprobe -r thinkpad_acpi
sudo modprobe thinkpad_acpi
```

## Generic Motherboards
Most desktop motherboards use SuperIO chips exposed via hwmon:

Common drivers:
- `nct6775` - Nuvoton NCT6775F and variants
- `it87` - ITE IT87xx chips
- `f71882fg` - Fintek F71882FG

Load the driver:
```bash
sudo modprobe nct6775  # or it87, etc.
```

## Permissions
Fan control files in `/sys/class/hwmon/` require root by default.

To allow non-root access, create udev rules:
```bash
# /etc/udev/rules.d/90-pysysfan.rules
SUBSYSTEM=="hwmon", KERNEL=="hwmon*", ATTR{name}=="nct6775", MODE="0666"
```

Then reload:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```
```

#### 5.3 Success Criteria

- [ ] All existing Windows tests pass
- [ ] New Linux tests pass (mock-based)
- [ ] Platform detection tests pass
- [ ] Integration test on ThinkPad P14s Gen3 passes
- [ ] Documentation updated with Linux instructions
- [ ] Both installers (`.bat` and `.sh`) work correctly
- [ ] CI passes on both Windows and Linux

---

## Summary

| Component | Status | Files |
|-----------|--------|-------|
| Windows HAL | Refactored | `platforms/windows.py`, `platforms/windows_service.py` |
| Linux HAL | New | `platforms/linux.py`, `platforms/linux_service.py` |
| Base classes | New | `platforms/base.py`, `platforms/__init__.py` |
| Hardware factory | Modified | `hardware.py` (re-export only) |
| Config/Curves/Daemon | Unchanged | `config.py`, `curves.py`, `daemon.py` |
| CLI | Modified | `cli.py` (service commands) |
| Windows installer | Unchanged | `install-pysysfan.bat` |
| Linux installer | New | `install-pysysfan.sh` |
| Tests | New/Modified | `tests/test_linux_*.py`, `tests/test_platform_detection.py` |
| Documentation | Updated | `README.md`, `docs/linux.md` |

## Next Steps

1. **Review** this plan
2. **Create feature branch**: `git checkout -b feature/linux-support`
3. **Update** `plan.md` and `TODO.md` with Linux phases
4. **Begin Phase 1**: Hardware abstraction layer refactoring
5. **Implement Phase 2**: Linux hardware support
6. **Add Phase 3**: Systemd service
7. **Create Phase 4**: Bash installer
8. **Complete Phase 5**: Testing and documentation

**Estimated Total Time**: 13-19 hours of development work
