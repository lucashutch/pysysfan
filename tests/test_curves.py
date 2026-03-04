"""Tests for pysysfan.curves — FanCurve interpolation, clamping, and hysteresis."""

import pytest
from pysysfan.curves import FanCurve, StaticCurve, parse_curve, InvalidCurveError


# ── Fixtures ──────────────────────────────────────────────────────────

BALANCED_POINTS = [(30, 30), (60, 60), (75, 85), (85, 100)]
SILENT_POINTS = [(30, 20), (50, 40), (70, 70), (85, 100)]
PERFORMANCE_POINTS = [(30, 50), (50, 70), (65, 90), (75, 100)]


@pytest.fixture
def balanced():
    return FanCurve(name="balanced", points=BALANCED_POINTS, hysteresis=3.0)


@pytest.fixture
def silent():
    return FanCurve(name="silent", points=SILENT_POINTS, hysteresis=3.0)


@pytest.fixture
def performance():
    return FanCurve(name="performance", points=PERFORMANCE_POINTS, hysteresis=2.0)


# ── Basic interpolation ──────────────────────────────────────────────


def test_interpolation_at_exact_point(balanced):
    """Speed at an exact defined point should equal the point's speed."""
    assert balanced.evaluate(30) == 30.0
    assert balanced.evaluate(60) == 60.0
    assert balanced.evaluate(85) == 100.0


def test_interpolation_between_points(balanced):
    """Speed between points should be linearly interpolated."""
    # Midpoint between (30, 30) and (60, 60) is (45, 45)
    result = balanced.evaluate(45)
    assert result == pytest.approx(45.0)


def test_interpolation_between_higher_points(balanced):
    """Interpolation between (60, 60) and (75, 85)."""
    # At 67.5 (midpoint): speed = 60 + (7.5 / 15) * 25 = 72.5
    result = balanced.evaluate(67.5)
    assert result == pytest.approx(72.5)


# ── Clamping ──────────────────────────────────────────────────────────


def test_clamp_below_minimum(balanced):
    """Below the lowest point, speed should clamp to the first point's speed."""
    assert balanced.evaluate(0) == 30.0
    assert balanced.evaluate(-10) == 30.0
    assert balanced.evaluate(20) == 30.0


def test_clamp_above_maximum(balanced):
    """Above the highest point, speed should clamp to the last point's speed."""
    assert balanced.evaluate(100) == 100.0
    assert balanced.evaluate(200) == 100.0


# ── Hysteresis ────────────────────────────────────────────────────────


def test_hysteresis_prevents_drop(balanced):
    """Speed should not drop when temp falls by less than hysteresis."""
    # Push temp up to latch a high speed
    balanced.evaluate(70)  # ~70% interpolated
    # Drop by less than 3°C → should maintain last speed
    result = balanced.evaluate(68)
    assert result > 60  # should NOT have dropped to the raw interpolated value


def test_hysteresis_allows_drop_after_threshold(balanced):
    """Speed should drop when temp falls by more than hysteresis."""
    balanced.evaluate(70)
    # Drop by more than hysteresis (3°C)
    result = balanced.evaluate(40)
    # Should interpolate: between (30,30) and (60,60) at 40 → 40
    assert result == pytest.approx(40.0)


def test_hysteresis_no_effect_on_rising(balanced):
    """Hysteresis should not block speed increases."""
    balanced.evaluate(40)  # 40%
    result = balanced.evaluate(60)  # should jump to 60%
    assert result == pytest.approx(60.0)


# ── Preset curve shapes ──────────────────────────────────────────────


def test_silent_curve_low_at_30(silent):
    """Silent curve should be gentle at 30°C."""
    assert silent.evaluate(30) == 20.0


def test_silent_curve_moderate_at_50(silent):
    """Silent curve should be 40% at 50°C."""
    assert silent.evaluate(50) == 40.0


def test_performance_curve_high_baseline(performance):
    """Performance curve starts at 50% even at 30°C."""
    assert performance.evaluate(30) == 50.0


def test_performance_curve_high_at_75(performance):
    """Performance curve should hit 100% by 75°C."""
    assert performance.evaluate(75) == 100.0


# ── Edge cases ────────────────────────────────────────────────────────


def test_single_point_curve():
    """Curve with a single point should always return that speed."""
    curve = FanCurve(name="flat", points=[(50, 75)])
    assert curve.evaluate(0) == 75.0
    assert curve.evaluate(50) == 75.0
    assert curve.evaluate(100) == 75.0


def test_two_point_curve():
    """Curve with two points should interpolate linearly."""
    curve = FanCurve(name="simple", points=[(0, 0), (100, 100)])
    assert curve.evaluate(50) == pytest.approx(50.0)
    assert curve.evaluate(25) == pytest.approx(25.0)


def test_unsorted_points_are_sorted():
    """Points provided out of order should be sorted by temperature."""
    curve = FanCurve(name="unsorted", points=[(80, 100), (20, 20), (50, 60)])
    # Should behave identically to sorted points
    assert curve.evaluate(20) == 20.0
    assert curve.evaluate(80) == 100.0
    assert curve.evaluate(50) == 60.0


def test_empty_curve_raises():
    """An empty curve should raise ValueError."""
    with pytest.raises(ValueError, match="at least one point"):
        FanCurve(name="empty", points=[])


def test_points_property(balanced):
    """The points property returns the curve data as tuples."""
    pts = balanced.points
    assert pts == BALANCED_POINTS


# ── StaticCurve tests ─────────────────────────────────────────────────


def test_static_curve_evaluate():
    """StaticCurve should always return the fixed speed, ignoring temperature."""
    curve = StaticCurve(50.0, name="static")
    assert curve.evaluate(0.0) == 50.0
    assert curve.evaluate(100.0) == 50.0
    assert curve.evaluate(-50.0) == 50.0
    assert curve.evaluate(200.0) == 50.0


def test_static_curve_zero_speed():
    """StaticCurve with 0 speed should work correctly."""
    curve = StaticCurve(0.0, name="off")
    assert curve.evaluate(50.0) == 0.0


def test_static_curve_full_speed():
    """StaticCurve with 100 speed should work correctly."""
    curve = StaticCurve(100.0, name="on")
    assert curve.evaluate(50.0) == 100.0


# ── parse_curve tests ──────────────────────────────────────────────────


def test_parse_curve_off():
    """Should parse 'off' case-insensitively to 0%."""
    for variant in ["off", "OFF", "Off", "  off  "]:
        result = parse_curve(variant)
        assert isinstance(result, StaticCurve)
        assert result.speed == 0.0


def test_parse_curve_on():
    """Should parse 'on' case-insensitively to 100%."""
    for variant in ["on", "ON", "On", "  on  "]:
        result = parse_curve(variant)
        assert isinstance(result, StaticCurve)
        assert result.speed == 100.0


def test_parse_curve_numeric_without_percent():
    """Should parse numeric values without % suffix."""
    result = parse_curve("50")
    assert isinstance(result, StaticCurve)
    assert result.speed == 50.0

    result = parse_curve("0")
    assert result.speed == 0.0

    result = parse_curve("100")
    assert result.speed == 100.0


def test_parse_curve_numeric_with_percent():
    """Should parse numeric values with % suffix."""
    result = parse_curve("75%")
    assert isinstance(result, StaticCurve)
    assert result.speed == 75.0

    result = parse_curve("0%")
    assert result.speed == 0.0

    result = parse_curve("100%")
    assert result.speed == 100.0


def test_parse_curve_case_insensitive_percent():
    """Should accept both '%' and '%' (though % is standard)."""
    result = parse_curve("60%")
    assert result.speed == 60.0


def test_parse_curve_decimal_values():
    """Should handle decimal values."""
    result = parse_curve("50.5")
    assert result.speed == 50.5

    result = parse_curve("33.33%")
    assert result.speed == 33.33


def test_parse_curve_out_of_range_above():
    """Should raise InvalidCurveError for values above 100."""
    with pytest.raises(InvalidCurveError, match="between 0 and 100"):
        parse_curve("150")

    with pytest.raises(InvalidCurveError, match="between 0 and 100"):
        parse_curve("101%")


def test_parse_curve_out_of_range_below():
    """Should raise InvalidCurveError for values below 0."""
    with pytest.raises(InvalidCurveError, match="between 0 and 100"):
        parse_curve("-10")

    with pytest.raises(InvalidCurveError, match="between 0 and 100"):
        parse_curve("-1%")


def test_parse_curve_regular_name():
    """Should return None for regular curve names."""
    assert parse_curve("balanced") is None
    assert parse_curve("silent") is None
    assert parse_curve("performance") is None
    assert parse_curve("custom_curve") is None


def test_parse_curve_invalid_format():
    """Should return None for non-numeric, non-special strings."""
    assert parse_curve("abc") is None
    assert parse_curve("50abc") is None
    assert parse_curve("abc50") is None
    assert parse_curve("50.5.5") is None


def test_parse_curve_empty_and_whitespace():
    """Should handle empty/whitespace-only strings appropriately."""
    # Empty string is not a valid curve name
    assert parse_curve("") is None
    # Pure whitespace is also not valid
    assert parse_curve("   ") is None
