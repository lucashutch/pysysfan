# Contributing to pysysfan

Thank you for your interest in contributing to pysysfan! This guide covers the development setup and workflow.

## Development Setup

### Prerequisites

- Python 3.8+
- `uv` (recommended) or `pip`
- Git

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/anomalyco/pysysfan.git
cd pysysfan

# Install with development dependencies
uv pip install -e ".[dev]"
# or
pip install -e ".[dev]"
```

## Project Structure

```
pysysfan/
├── src/pysysfan/          # Main source code
│   ├── cli.py             # CLI entry point (Click commands)
│   ├── daemon.py          # Fan control loop
│   ├── curves.py          # Fan curve logic
│   ├── config.py          # YAML configuration
│   ├── hardware.py        # Hardware abstraction
│   ├── updater.py         # Self-update logic
│   ├── lhm/               # LibreHardwareMonitor integration
│   ├── pawnio/            # PawnIO driver management
│   └── platforms/         # Platform-specific code
│       ├── windows.py     # Windows implementation
│       └── linux.py       # Linux implementation
├── tests/                 # Test suite
├── docs/                  # Documentation
└── pyproject.toml         # Project configuration
```

## Development Workflow

### Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes following the coding standards below

3. Run tests and linting:
   ```bash
   # Run all tests
   uv run pytest tests/
   
   # Run linting
   uv run ruff check --fix
   
   # Format code
   uv run ruff format
   ```

4. Commit with a descriptive message

## Coding Standards

### Style Guidelines

- Follow **PEP 8**
- Use **type hints** for all function signatures
- Add **docstrings** to all public functions and classes
- Keep functions focused and small
- Use meaningful variable names

### Example

```python
def parse_curve(name: str) -> StaticCurve | None:
    """Parse a curve name and return StaticCurve for special values.

    Special names (case-insensitive):
    - "off" → StaticCurve(0%)
    - "on" → StaticCurve(100%)
    - numeric (e.g., "50", "75%") → StaticCurve(%) with that value

    Args:
        name: The curve name to parse.

    Returns:
        StaticCurve instance for special curves, or None.

    Raises:
        InvalidCurveError: If a numeric value is outside the 0-100 range.
    """
    # Implementation here
```

### Type Hints

Use Python 3.10+ union syntax:
```python
# Good
def func() -> str | None:
    ...

# Avoid
def func() -> Optional[str]:
    ...
```

### Imports

- Group imports: stdlib, third-party, local
- Use `from __future__ import annotations` for forward references
- Sort imports with `ruff` (runs automatically on format)

## Testing

### Writing Tests

Tests are located in `tests/` and use **pytest**:

```python
# tests/test_my_feature.py
import pytest
from pysysfan.curves import parse_curve


def test_parse_curve_off():
    """Should parse 'off' to 0%."""
    result = parse_curve("off")
    assert result.speed == 0.0
```

### Test Guidelines

- Name tests descriptively: `test_<function>_<scenario>`
- Use pytest fixtures for shared setup
- Test edge cases and error conditions
- Keep tests independent (no shared state)

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_curves.py

# Run with coverage
pytest tests/ --cov=pysysfan

# Run in verbose mode
pytest tests/ -v
```

### Mocking Hardware

When testing hardware-dependent code, use mocks:

```python
from unittest.mock import MagicMock, patch

@patch('pysysfan.hardware.HardwareManager')
def test_daemon(mock_hw_class):
    mock_hw = MagicMock()
    mock_hw_class.return_value = mock_hw
    # Test with mocked hardware
```

## Documentation

### Code Documentation

- Add docstrings to all public APIs
- Use Google-style docstrings (as shown above)
- Include type information in docstrings when helpful

### User Documentation

- Update `docs/` for feature changes
- Keep `README.md` end-user focused
- Add examples for new features

## Pull Request Process

1. Ensure all tests pass
2. Run linting and formatting
3. Update documentation if needed
4. Create a PR with a clear description
5. Link to any related issues

## Release Process

Releases are automated via GitHub Actions when a tag is pushed:

```bash
# Version bump (example: patch)
git tag v1.2.3
git push origin v1.2.3
```

## Platform-Specific Development

### Windows Development

- Requires Windows 10/11
- Administrator privileges needed for hardware access
- LibreHardwareMonitor DLL auto-downloads on first run

### Linux Development

- Tested on Ubuntu, Fedora, Arch
- Install lm-sensors: `sudo apt install lm-sensors libsensors-dev`
- Run as root or set up udev rules for non-root testing

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:
```bash
export PYSYSFAN_DEBUG=1
```

### Common Issues

**Import errors on Linux**: Install the Linux extras:
```bash
pip install -e ".[linux]"
```

**Permission errors**: Ensure you're running as Administrator (Windows) or root (Linux) when accessing hardware.

## Questions?

- Open an issue for bugs or feature requests
- Join discussions in existing issues
- Check existing tests and code for examples

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
