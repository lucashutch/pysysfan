#!/bin/bash
# pysysfan Linux Installer
# Minimal bash wrapper that calls the Python installer
#
# Usage: ./install-pysysfan.sh [options]
#   --user         Install user service instead of system-wide
#   --no-service   Skip service installation
#   --dry-run      Show what would be done without making changes
#   --verbose      Enable verbose output
#   --help         Show help message
#
# For full help: ./install-pysysfan.sh --help

set -e

# Check if pysysfan-linux-install is available
if command -v pysysfan-linux-install &>/dev/null; then
	exec pysysfan-linux-install "$@"
fi

# Fallback: try to run directly from source
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="${SCRIPT_DIR}/src"

if [ -f "${SCRIPT_DIR}/src/pysysfan/install_linux.py" ]; then
	PYTHONPATH="${PYTHON_PATH}" exec python3 -m pysysfan.install_linux "$@"
fi

# Not installed - provide installation instructions
echo "Error: pysysfan is not installed." >&2
echo "" >&2
echo "Please install pysysfan first:" >&2
echo "  pip install pysysfan[linux]" >&2
echo "  # or" >&2
echo "  uv tool install pysysfan[linux]" >&2
echo "" >&2
echo "Then run this installer again." >&2
exit 1
