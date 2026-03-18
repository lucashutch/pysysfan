"""LibreHardwareMonitor DLL management."""

import os
import sys
from pathlib import Path

# Default location for LHM DLLs
LHM_DIR = Path.home() / ".pysysfan" / "lib"
LHM_DLL_NAME = "LibreHardwareMonitorLib.dll"


def get_lhm_dll_path() -> Path:
    """Get the path to LibreHardwareMonitorLib.dll.

    Searches in order:
    1. PYSYSFAN_LHM_PATH environment variable
    2. ~/.pysysfan/lib/LibreHardwareMonitorLib.dll
    3. Adjacent to the running script
    """
    # 1. Environment variable override
    env_path = os.environ.get("PYSYSFAN_LHM_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p
        # If it's a directory, look for the DLL inside
        if p.is_dir():
            dll = p / LHM_DLL_NAME
            if dll.is_file():
                return dll

    # 2. Default location
    default_path = LHM_DIR / LHM_DLL_NAME
    if default_path.is_file():
        return default_path

    # 3. Adjacent to script/package
    script_dir = Path(__file__).parent.parent
    adjacent = script_dir / LHM_DLL_NAME
    if adjacent.is_file():
        return adjacent

    raise FileNotFoundError(
        f"LibreHardwareMonitorLib.dll not found. Searched:\n"
        f"  - PYSYSFAN_LHM_PATH env var\n"
        f"  - {default_path}\n"
        f"  - {adjacent}\n\n"
        f"Run 'pysysfan lhm download' to download it, or set PYSYSFAN_LHM_PATH."
    )


_clr_loaded = False
_lhm_hardware_module = None


def _ensure_clr():
    """Ensure the .NET Framework (netfx) runtime is loaded.

    Must be called before any `import clr` or .NET usage.
    pythonnet 3.x requires explicit runtime loading before the clr module
    can be used.

    We use 'netfx' (.NET Framework) because the LHM net472 build targets
    .NET Framework 4.7.2, which is pre-installed on all Windows 10/11
    machines. This avoids requiring users to install specific .NET Core
    runtime versions.
    """
    global _clr_loaded
    if _clr_loaded:
        return

    import pythonnet  # type: ignore[import-untyped]

    try:
        pythonnet.load("netfx")
    except Exception:
        pass  # May already be loaded

    _clr_loaded = True


def load_lhm():
    """Load LibreHardwareMonitorLib via pythonnet and return the module.

    Returns the LibreHardwareMonitor.Hardware namespace for use.
    Must be called before any LHM classes are used.
    """
    global _lhm_hardware_module
    if _lhm_hardware_module is not None:
        return _lhm_hardware_module

    _ensure_clr()

    dll_path = get_lhm_dll_path()
    dll_dir = str(dll_path.parent)

    # Add DLL directory to sys.path so CLR can resolve the assembly by name
    if dll_dir not in sys.path:
        sys.path.append(dll_dir)

    import clr  # type: ignore[import-untyped]

    # Add reference by assembly name (resolved via sys.path)
    clr.AddReference("LibreHardwareMonitorLib")

    # Import the namespace
    from LibreHardwareMonitor import Hardware  # type: ignore[import-untyped]

    _lhm_hardware_module = Hardware
    return _lhm_hardware_module


def get_lhm_version() -> str | None:
    """Get the version of the loaded LHM DLL, or None if not loaded."""
    try:
        dll_path = get_lhm_dll_path()
    except FileNotFoundError:
        return None

    try:
        _ensure_clr()
        import clr  # noqa: F401  # type: ignore[import-untyped]
        from System.Reflection import Assembly  # type: ignore[import-untyped]

        asm = Assembly.LoadFrom(str(dll_path))
        return str(asm.GetName().Version)
    except Exception:
        return "unknown"
