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
    fan_id: "/gpu/control/0"
    curve: "silent"
    temp_id: "/gpu/temperature/0"
    header: "GPU Header"

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
    assert len(cfg.fans) == 1
    assert cfg.fans["gpu_fan"].fan_id == "/gpu/control/0"
    assert cfg.fans["gpu_fan"].curve == "silent"
    assert cfg.fans["gpu_fan"].temp_id == "/gpu/temperature/0"
    assert cfg.fans["gpu_fan"].header_name == "GPU Header"
    assert "balanced" in cfg.curves
    assert cfg.curves["balanced"].hysteresis == 3.0
    assert len(cfg.curves["balanced"].points) == 3


def test_save_and_reload(tmp_path):
    """Config.save() → Config.load() should produce an identical config."""
    original = Config(
        poll_interval=3.0,
        fans={
            "test_fan": FanConfig(
                fan_id="/mb/control/1",
                curve="silent",
                temp_id="/cpu/temp/0",
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
    assert reloaded.fans["test_fan"].fan_id == "/mb/control/1"
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


# ── UpdateConfig ─────────────────────────────────────────────────────


def test_load_update_config(tmp_path):
    """Loading config with update section should parse auto_check and notify_only."""
    cfg_file = tmp_path / "with_update.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 2
fans: {}
curves: {}
update:
  auto_check: false
  notify_only: false
""")
    cfg = Config.load(cfg_file)
    assert cfg.update.auto_check is False
    assert cfg.update.notify_only is False


def test_load_default_update_config(tmp_path):
    """Loading config without update section should use defaults."""
    cfg_file = tmp_path / "no_update.yaml"
    cfg_file.write_text("general:\n  poll_interval: 2\nfans: {}\ncurves: {}\n")
    cfg = Config.load(cfg_file)
    assert cfg.update.auto_check is True
    assert cfg.update.notify_only is True


# ── Save with header_name ────────────────────────────────────────────


def test_save_includes_header_name(tmp_path):
    """Config.save should include header_name when set."""
    cfg = Config(
        fans={
            "fan1": FanConfig(
                fan_id="/mb/control/0",
                curve="balanced",
                temp_id="/cpu/temp/0",
                header_name="Header A",
            ),
        },
    )
    cfg_file = tmp_path / "header.yaml"
    cfg.save(cfg_file)

    import yaml

    with open(cfg_file) as f:
        data = yaml.safe_load(f)
    assert data["fans"]["fan1"]["header"] == "Header A"


def test_save_omits_header_when_none(tmp_path):
    """Config.save should not include header key when header_name is None."""
    cfg = Config(
        fans={
            "fan1": FanConfig(
                fan_id="/mb/control/0",
                curve="balanced",
                temp_id="/cpu/temp/0",
            ),
        },
    )
    cfg_file = tmp_path / "no_header.yaml"
    cfg.save(cfg_file)

    import yaml

    with open(cfg_file) as f:
        data = yaml.safe_load(f)
    assert "header" not in data["fans"]["fan1"]


# ── get_default_config / init_default_config ─────────────────────────


def test_get_default_config():
    """get_default_config should return a Config with default values."""
    from pysysfan.config import get_default_config

    cfg = get_default_config()
    assert cfg.poll_interval == 2.0
    assert len(cfg.fans) == 0


def test_init_default_config_creates_file(tmp_path):
    """init_default_config should create a config file when it doesn't exist."""
    from pysysfan.config import init_default_config

    cfg_file = tmp_path / "config.yaml"
    init_default_config(cfg_file)
    assert cfg_file.is_file()


def test_init_default_config_skips_existing(tmp_path):
    """init_default_config should not overwrite an existing file."""
    from pysysfan.config import init_default_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("original content")
    init_default_config(cfg_file)
    assert cfg_file.read_text() == "original content"
