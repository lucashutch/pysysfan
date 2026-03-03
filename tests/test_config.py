"""Tests for pysysfan.config — Config loading, saving, and validation."""

import pytest

from pysysfan.config import Config, FanConfig, CurveConfig, DEFAULT_CONFIG_DIR


# ── Load / save roundtrip ─────────────────────────────────────────────


def test_load_valid_config(tmp_path):
    """Loading a well-formed YAML config should produce a correct Config object."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 5

fans:
  gpu_fan:
    sensor: "/gpu/control/0"
    curve: balanced
    source: "/gpu/temperature/0"

curves:
  balanced:
    hysteresis: 3
    points:
      - [30, 30]
      - [60, 60]
      - [85, 100]
""")

    cfg = Config.load(cfg_file)
    assert cfg.poll_interval == 5.0
    assert "gpu_fan" in cfg.fans
    assert cfg.fans["gpu_fan"].sensor_id == "/gpu/control/0"
    assert cfg.fans["gpu_fan"].curve == "balanced"
    assert cfg.fans["gpu_fan"].source_id == "/gpu/temperature/0"
    assert "balanced" in cfg.curves
    assert cfg.curves["balanced"].hysteresis == 3.0
    assert len(cfg.curves["balanced"].points) == 3


def test_save_and_reload(tmp_path):
    """Config.save() → Config.load() should produce an identical config."""
    original = Config(
        poll_interval=3.0,
        fans={
            "test_fan": FanConfig(
                sensor_id="/mb/control/1",
                curve="silent",
                source_id="/cpu/temp/0",
            )
        },
        curves={
            "silent": CurveConfig(
                points=[(30, 20), (50, 40), (80, 100)],
                hysteresis=4.0,
            ),
        },
    )

    cfg_file = tmp_path / "roundtrip.yaml"
    original.save(cfg_file)

    reloaded = Config.load(cfg_file)
    assert reloaded.poll_interval == original.poll_interval
    assert list(reloaded.fans.keys()) == list(original.fans.keys())
    assert reloaded.fans["test_fan"].sensor_id == "/mb/control/1"
    assert reloaded.curves["silent"].hysteresis == 4.0
    assert reloaded.curves["silent"].points == [(30, 20), (50, 40), (80, 100)]


# ── Default presets ───────────────────────────────────────────────────


def test_default_presets_added(tmp_path):
    """Loading a config without presets should auto-add silent/balanced/performance."""
    cfg_file = tmp_path / "minimal.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 2
fans: {}
curves: {}
""")

    cfg = Config.load(cfg_file)
    assert "silent" in cfg.curves
    assert "balanced" in cfg.curves
    assert "performance" in cfg.curves


def test_custom_presets_not_overridden(tmp_path):
    """User-defined presets with preset names should NOT be overridden."""
    cfg_file = tmp_path / "custom.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 2
fans: {}
curves:
  silent:
    hysteresis: 99
    points:
      - [10, 10]
""")

    cfg = Config.load(cfg_file)
    assert cfg.curves["silent"].hysteresis == 99.0
    assert cfg.curves["silent"].points == [(10, 10)]


# ── Error handling ────────────────────────────────────────────────────


def test_load_missing_file():
    """Loading a non-existent file should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        Config.load("/non/existent/config.yaml")


def test_load_empty_file(tmp_path):
    """Loading an empty YAML file should produce defaults (no crash)."""
    cfg_file = tmp_path / "empty.yaml"
    cfg_file.write_text("")
    cfg = Config.load(cfg_file)
    assert cfg.poll_interval == 2.0
    assert len(cfg.fans) == 0
    assert "balanced" in cfg.curves  # default preset added


# ── Config directory default ──────────────────────────────────────────


def test_default_config_dir():
    """Default config directory should use .pysysfan."""
    assert DEFAULT_CONFIG_DIR.name == ".pysysfan"
