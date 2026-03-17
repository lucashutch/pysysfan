"""Tests for pysysfan.config — Config loading, saving, and validation."""

import pytest

from pysysfan.config import (
    Config,
    FanConfig,
    CurveConfig,
    DEFAULT_CONFIG_DIR,
    _sanitize_config_name,
    _generate_unique_name,
    auto_populate_config,
)
from pysysfan.platforms.base import (
    HardwareScanResult,
    SensorInfo,
    ControlInfo,
)


# ── Load / save roundtrip ─────────────────────────────────────────────


def test_default_poll_interval_is_one_second(tmp_path):
    """Loading a config without general.poll_interval should default to 1 second."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("fans: {}\ncurves: {}\n")

    cfg = Config.load(cfg_file)

    assert cfg.poll_interval == 1.0


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
    temp_ids:
      - "/gpu/temperature/0"
    aggregation: "max"
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
    assert cfg.fans["gpu_fan"].temp_ids == ["/gpu/temperature/0"]
    assert cfg.fans["gpu_fan"].aggregation == "max"
    assert cfg.fans["gpu_fan"].header_name == "GPU Header"
    # Test backward compatibility property
    assert cfg.fans["gpu_fan"].temp_id == "/gpu/temperature/0"
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
                temp_ids=["/cpu/temp/0"],
                aggregation="max",
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
    assert reloaded.fans["test_fan"].temp_ids == ["/cpu/temp/0"]
    assert reloaded.fans["test_fan"].aggregation == "max"
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
    assert cfg.poll_interval == 1.0
    assert len(cfg.fans) == 0
    assert "balanced" in cfg.curves  # default preset added


def test_load_legacy_config_with_temp_id(tmp_path):
    """Loading config with legacy 'temp_id' field should work (backward compatibility)."""
    cfg_file = tmp_path / "legacy.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 2

fans:
  cpu_fan:
    fan_id: "/mb/control/0"
    curve: balanced
    temp_id: "/cpu/temp/0"

curves: {}
""")

    cfg = Config.load(cfg_file)
    assert len(cfg.fans) == 1
    assert cfg.fans["cpu_fan"].temp_ids == ["/cpu/temp/0"]
    assert cfg.fans["cpu_fan"].temp_id == "/cpu/temp/0"
    assert cfg.fans["cpu_fan"].aggregation == "max"


def test_load_config_with_multiple_temp_ids(tmp_path):
    """Loading config with multiple temp_ids should work."""
    cfg_file = tmp_path / "multi_temp.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 2

fans:
  cpu_fan:
    fan_id: "/mb/control/0"
    curve: balanced
    temp_ids:
      - "/cpu/temp/0"
      - "/cpu/temp/1"
      - "/cpu/temp/2"
    aggregation: average

curves: {}
""")

    cfg = Config.load(cfg_file)
    assert len(cfg.fans) == 1
    assert cfg.fans["cpu_fan"].temp_ids == ["/cpu/temp/0", "/cpu/temp/1", "/cpu/temp/2"]
    assert cfg.fans["cpu_fan"].aggregation == "average"


def test_load_config_with_legacy_source_key(tmp_path):
    """Loading config with legacy 'source' key should work (backward compatibility)."""
    cfg_file = tmp_path / "legacy_source.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 2

fans:
  cpu_fan:
    sensor: "/mb/control/0"
    curve: balanced
    source: "/cpu/temp/0"

curves: {}
""")

    cfg = Config.load(cfg_file)
    assert len(cfg.fans) == 1
    assert cfg.fans["cpu_fan"].fan_id == "/mb/control/0"
    assert cfg.fans["cpu_fan"].temp_ids == ["/cpu/temp/0"]


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
                temp_ids=["/cpu/temp/0"],
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
    assert data["fans"]["fan1"]["temp_ids"] == ["/cpu/temp/0"]
    assert data["fans"]["fan1"]["aggregation"] == "max"


def test_save_omits_header_when_none(tmp_path):
    """Config.save should not include header key when header_name is None."""
    cfg = Config(
        fans={
            "fan1": FanConfig(
                fan_id="/mb/control/0",
                curve="balanced",
                temp_ids=["/cpu/temp/0"],
            ),
        },
    )
    cfg_file = tmp_path / "no_header.yaml"
    cfg.save(cfg_file)

    import yaml

    with open(cfg_file) as f:
        data = yaml.safe_load(f)
    assert "header" not in data["fans"]["fan1"]
    assert data["fans"]["fan1"]["temp_ids"] == ["/cpu/temp/0"]


# ── get_default_config / init_default_config ─────────────────────────


def test_get_default_config():
    """get_default_config should return a Config with default values."""
    from pysysfan.config import get_default_config

    cfg = get_default_config()
    assert cfg.poll_interval == 1.0
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


# ── Name sanitization ────────────────────────────────────────────────


def test_sanitize_config_name_simple():
    """Simple sensor names should be lowercased and spaces replaced with underscores."""
    assert _sanitize_config_name("CPU Fan") == "cpu_fan"
    assert _sanitize_config_name("System Fan") == "system_fan"


def test_sanitize_config_name_with_hash():
    """Hash symbols should be converted to underscores."""
    assert _sanitize_config_name("Fan #1") == "fan_1"
    assert _sanitize_config_name("System Fan #2") == "system_fan_2"


def test_sanitize_config_name_special_chars():
    """Special characters should be removed."""
    assert _sanitize_config_name("CPU Fan (PWM)") == "cpu_fan_pwm"
    assert _sanitize_config_name("GPU@Fan") == "gpufan"


def test_sanitize_config_name_multiple_spaces():
    """Multiple spaces should be collapsed to single underscore."""
    assert _sanitize_config_name("CPU  Fan") == "cpu_fan"
    assert _sanitize_config_name("System   Fan  #1") == "system_fan_1"


def test_generate_unique_name_no_conflict():
    """When name doesn't exist, it should be returned unchanged."""
    assert _generate_unique_name("cpu_fan", set()) == "cpu_fan"
    assert _generate_unique_name("gpu_fan", {"cpu_fan", "case_fan"}) == "gpu_fan"


def test_generate_unique_name_with_conflict():
    """When name exists, should append counter."""
    assert _generate_unique_name("cpu_fan", {"cpu_fan"}) == "cpu_fan_2"
    assert _generate_unique_name("cpu_fan", {"cpu_fan", "cpu_fan_2"}) == "cpu_fan_3"


# ── Auto-populate config ───────────────────────────────────────────────


def test_auto_populate_basic():
    """Auto-populate should generate config from hardware scan."""
    scan = HardwareScanResult(
        temperatures=[
            SensorInfo(
                hardware_name="AMD CPU",
                hardware_type="cpu",
                sensor_name="CPU Package",
                sensor_type="temperature",
                identifier="/amdcpu/0/temperature/0",
                value=45.0,
            )
        ],
        controls=[
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                identifier="/motherboard/control/0",
                current_value=50.0,
                has_control=True,
            ),
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="System Fan #1",
                identifier="/motherboard/control/1",
                current_value=40.0,
                has_control=True,
            ),
        ],
    )

    config = auto_populate_config(scan)

    # Should have 2 fans
    assert len(config.fans) == 2

    # Both should use CPU temperature
    for fan in config.fans.values():
        assert fan.temp_ids == ["/amdcpu/0/temperature/0"]
        assert fan.temp_id == "/amdcpu/0/temperature/0"  # backward compat
        assert fan.curve == "balanced"
        assert fan.aggregation == "max"

    # Should have default curves
    assert "silent" in config.curves
    assert "balanced" in config.curves
    assert "performance" in config.curves


def test_auto_populate_no_cpu_temp():
    """When no CPU temp found, should use first available temperature."""
    scan = HardwareScanResult(
        temperatures=[
            SensorInfo(
                hardware_name="GPU",
                hardware_type="gpu",
                sensor_name="GPU Core",
                sensor_type="temperature",
                identifier="/gpu/0/temperature/0",
                value=60.0,
            )
        ],
        controls=[
            ControlInfo(
                hardware_name="GPU",
                sensor_name="GPU Fan",
                identifier="/gpu/control/0",
                current_value=45.0,
                has_control=True,
            )
        ],
    )

    config = auto_populate_config(scan)
    assert len(config.fans) == 1
    assert list(config.fans.values())[0].temp_ids == ["/gpu/0/temperature/0"]
    assert list(config.fans.values())[0].aggregation == "max"


def test_auto_populate_no_temperatures():
    """Auto-populate should raise error when no temperatures found."""
    scan = HardwareScanResult(
        temperatures=[],
        controls=[
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                identifier="/motherboard/control/0",
                current_value=50.0,
                has_control=True,
            )
        ],
    )

    with pytest.raises(ValueError, match="No temperature sensors found"):
        auto_populate_config(scan)


def test_auto_populate_no_controls():
    """Auto-populate should create config with no fans when no controls found."""
    scan = HardwareScanResult(
        temperatures=[
            SensorInfo(
                hardware_name="CPU",
                hardware_type="cpu",
                sensor_name="CPU Package",
                sensor_type="temperature",
                identifier="/cpu/0/temperature/0",
                value=45.0,
            )
        ],
        controls=[],
    )

    config = auto_populate_config(scan)
    assert len(config.fans) == 0
    # Should still have default curves
    assert "balanced" in config.curves


def test_auto_populate_custom_curve():
    """Auto-populate should use specified default curve."""
    scan = HardwareScanResult(
        temperatures=[
            SensorInfo(
                hardware_name="CPU",
                hardware_type="cpu",
                sensor_name="CPU Package",
                sensor_type="temperature",
                identifier="/cpu/0/temperature/0",
                value=45.0,
            )
        ],
        controls=[
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                identifier="/motherboard/control/0",
                current_value=50.0,
                has_control=True,
            )
        ],
    )

    config = auto_populate_config(scan, default_curve="silent")
    assert list(config.fans.values())[0].curve == "silent"


def test_auto_populate_duplicate_names():
    """Auto-populate should handle duplicate sensor names."""
    scan = HardwareScanResult(
        temperatures=[
            SensorInfo(
                hardware_name="CPU",
                hardware_type="cpu",
                sensor_name="CPU Package",
                sensor_type="temperature",
                identifier="/cpu/0/temperature/0",
                value=45.0,
            )
        ],
        controls=[
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="Fan",
                identifier="/motherboard/control/0",
                current_value=50.0,
                has_control=True,
            ),
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="Fan",
                identifier="/motherboard/control/1",
                current_value=40.0,
                has_control=True,
            ),
        ],
    )

    config = auto_populate_config(scan)
    # Should have unique names
    fan_names = list(config.fans.keys())
    assert len(fan_names) == 2
    assert fan_names[0] == "fan"
    assert fan_names[1] == "fan_2"


def test_auto_populate_readonly_controls():
    """Auto-populate should include read-only controls (has_control=False)."""
    scan = HardwareScanResult(
        temperatures=[
            SensorInfo(
                hardware_name="CPU",
                hardware_type="cpu",
                sensor_name="CPU Package",
                sensor_type="temperature",
                identifier="/cpu/0/temperature/0",
                value=45.0,
            )
        ],
        controls=[
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="CPU Fan",
                identifier="/motherboard/control/0",
                current_value=50.0,
                has_control=True,
            ),
            ControlInfo(
                hardware_name="Motherboard",
                sensor_name="Case Fan",
                identifier="/motherboard/fan/1",
                current_value=None,
                has_control=False,
            ),
        ],
    )

    config = auto_populate_config(scan)
    # Should include both controllable and read-only fans
    assert len(config.fans) == 2


# ── allow_fan_off config option ──────────────────────────────────────────


def test_load_config_with_allow_fan_off(tmp_path):
    """Loading config with allow_fan_off should parse the value."""
    cfg_file = tmp_path / "allow_off.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 2

fans:
  cpu_fan:
    fan_id: "/mb/control/0"
    curve: balanced
    temp_ids:
      - "/cpu/temp/0"
    allow_fan_off: false

curves: {}
""")
    cfg = Config.load(cfg_file)
    assert cfg.fans["cpu_fan"].allow_fan_off is False


def test_load_config_default_allow_fan_off(tmp_path):
    """Loading config without allow_fan_off should default to True."""
    cfg_file = tmp_path / "default_off.yaml"
    cfg_file.write_text("""\
general:
  poll_interval: 2

fans:
  cpu_fan:
    fan_id: "/mb/control/0"
    curve: balanced
    temp_ids:
      - "/cpu/temp/0"

curves: {}
""")
    cfg = Config.load(cfg_file)
    assert cfg.fans["cpu_fan"].allow_fan_off is True


def test_save_includes_allow_fan_off_when_false(tmp_path):
    """Config.save should include allow_fan_off when set to False."""
    cfg = Config(
        fans={
            "fan1": FanConfig(
                fan_id="/mb/control/0",
                curve="balanced",
                temp_ids=["/cpu/temp/0"],
                allow_fan_off=False,
            ),
        },
    )
    cfg_file = tmp_path / "allow_off_false.yaml"
    cfg.save(cfg_file)

    import yaml

    with open(cfg_file) as f:
        data = yaml.safe_load(f)
    assert data["fans"]["fan1"]["allow_fan_off"] is False


def test_save_omits_allow_fan_off_when_true(tmp_path):
    """Config.save should omit allow_fan_off when True (default)."""
    cfg = Config(
        fans={
            "fan1": FanConfig(
                fan_id="/mb/control/0",
                curve="balanced",
                temp_ids=["/cpu/temp/0"],
                allow_fan_off=True,
            ),
        },
    )
    cfg_file = tmp_path / "allow_off_true.yaml"
    cfg.save(cfg_file)

    import yaml

    with open(cfg_file) as f:
        data = yaml.safe_load(f)
    assert "allow_fan_off" not in data["fans"]["fan1"]


def test_load_config_with_off_as_boolean(tmp_path):
    """Loading config with 'off' as YAML boolean should convert to string."""
    cfg_file = tmp_path / "off_bool.yaml"
    # YAML parses 'off' as boolean False
    cfg_file.write_text("""\
general:
  poll_interval: 2

fans:
  top_fan:
    fan_id: "/mb/control/0"
    curve: off
    temp_ids:
      - "/cpu/temp/0"

curves: {}
""")
    cfg = Config.load(cfg_file)
    # Should be converted to string "off", not boolean False
    assert cfg.fans["top_fan"].curve == "off"
    assert isinstance(cfg.fans["top_fan"].curve, str)


def test_load_config_with_on_as_boolean(tmp_path):
    """Loading config with 'on' as YAML boolean should convert to string."""
    cfg_file = tmp_path / "on_bool.yaml"
    # YAML parses 'on' as boolean True
    cfg_file.write_text("""\
general:
  poll_interval: 2

fans:
  top_fan:
    fan_id: "/mb/control/0"
    curve: on
    temp_ids:
      - "/cpu/temp/0"

curves: {}
""")
    cfg = Config.load(cfg_file)
    # Should be converted to string "on", not boolean True
    assert cfg.fans["top_fan"].curve == "on"
    assert isinstance(cfg.fans["top_fan"].curve, str)


def test_load_config_boolean_string_key_collision_raises(tmp_path):
    """Colliding bool key (true/false → 'on'/'off') and string key must raise ValueError."""
    cfg_file = tmp_path / "config.yaml"
    # YAML parses unquoted 'on' as boolean True; having both 'on' (bool) and
    # '"on"' (string) as curve keys is ambiguous and was previously silently renamed.
    cfg_file.write_text(
        "fans: {}\n"
        "curves:\n"
        "  on:\n"
        "    points: [[30, 30], [70, 100]]\n"
        '  "on":\n'
        "    points: [[30, 50], [70, 100]]\n"
    )
    with pytest.raises(ValueError, match="Conflicting curve keys"):
        Config.load(cfg_file)
