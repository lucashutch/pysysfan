"""Tests for local config and curve preview validation helpers."""

from __future__ import annotations

import pytest

from pysysfan.config import Config, CurveConfig, FanConfig, UpdateConfig
from pysysfan.gui.desktop.local_backend import (
    build_curve_preview_series,
    validate_config_model,
)


def _make_config(**fan_overrides) -> Config:
    fan = FanConfig(
        fan_id="/mb/control/0",
        curve="balanced",
        temp_ids=["/cpu/temp/0"],
        aggregation="max",
        allow_fan_off=False,
    )
    for key, value in fan_overrides.items():
        setattr(fan, key, value)

    return Config(
        poll_interval=1.0,
        fans={"cpu_fan": fan},
        curves={
            "balanced": CurveConfig(
                points=[(30, 30), (60, 60), (85, 100)],
                hysteresis=3.0,
            )
        },
        update=UpdateConfig(auto_check=False),
    )


def test_validate_config_model_accepts_valid_config() -> None:
    """A valid config should return no validation errors."""
    assert validate_config_model(_make_config()) == []


def test_validate_config_model_rejects_unknown_curve() -> None:
    """Fan curve references must resolve to a configured or special curve."""
    config = _make_config(curve="missing")

    errors = validate_config_model(config)

    assert any("unknown curve 'missing'" in error for error in errors)


def test_validate_config_model_rejects_invalid_aggregation() -> None:
    """Aggregation mode must be one of the supported temperature reducers."""
    config = _make_config(aggregation="bogus")

    errors = validate_config_model(config)

    assert any("invalid aggregation 'bogus'" in error for error in errors)


def test_validate_config_model_requires_temp_ids() -> None:
    """Fans without temperature sources should fail validation."""
    config = _make_config(temp_ids=[])

    errors = validate_config_model(config)

    assert any("no temperature sensors configured" in error for error in errors)


def test_validate_config_model_rejects_non_positive_poll_interval() -> None:
    """Poll interval must remain positive."""
    config = _make_config()
    config.poll_interval = 0

    errors = validate_config_model(config)

    assert any("poll_interval must be positive" in error for error in errors)


def test_validate_config_model_rejects_too_short_poll_interval() -> None:
    """Poll intervals below the supported minimum should be rejected."""
    config = _make_config()
    config.poll_interval = 0.05

    errors = validate_config_model(config)

    assert any("minimum 0.1s" in error for error in errors)


def test_build_curve_preview_series_spans_requested_range() -> None:
    """Preview generation should return one point per temperature step."""
    series = build_curve_preview_series(
        [(30, 30), (60, 60), (85, 100)],
        hysteresis=3.0,
        start_temp=25,
        end_temp=27,
    )

    assert series == [(25.0, 30.0), (26.0, 30.0), (27.0, 30.0)]


def test_build_curve_preview_series_raises_for_invalid_curve() -> None:
    """Invalid curves should surface the parser error."""
    with pytest.raises(Exception, match="at least one point"):
        build_curve_preview_series([], hysteresis=3.0)
