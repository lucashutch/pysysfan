"""Tests for pysysfan.api.validation — Curve and hysteresis validation."""

import pytest  # noqa: F401
from pysysfan.api.validation import validate_curve, validate_hysteresis


class TestValidateCurve:
    def test_valid_curve(self):
        """A valid curve should return no errors."""
        points = [[30, 30], [60, 60], [75, 85], [85, 100]]
        assert validate_curve(points) == []

    def test_minimum_two_points(self):
        """A curve with less than 2 points should fail."""
        assert "at least 2 points" in validate_curve([])[0]
        assert "at least 2 points" in validate_curve([[50, 50]])[0]

    def test_temperature_out_of_range_below(self):
        """Temperature below 20°C should fail."""
        points = [[10, 30], [60, 60]]
        errors = validate_curve(points)
        assert any("10" in e and "20-100" in e for e in errors)

    def test_temperature_out_of_range_above(self):
        """Temperature above 100°C should fail."""
        points = [[30, 30], [110, 60]]
        errors = validate_curve(points)
        assert any("110" in e and "20-100" in e for e in errors)

    def test_speed_out_of_range_below(self):
        """Speed below 0% should fail."""
        points = [[30, -10], [60, 60]]
        errors = validate_curve(points)
        assert any("-10" in e and "0-100" in e for e in errors)

    def test_speed_out_of_range_above(self):
        """Speed above 100% should fail."""
        points = [[30, 30], [60, 150]]
        errors = validate_curve(points)
        assert any("150" in e and "0-100" in e for e in errors)

    def test_temperature_not_increasing(self):
        """Temperatures must be strictly increasing."""
        points = [[30, 30], [60, 60], [50, 80]]
        errors = validate_curve(points)
        assert any("increasing" in e.lower() for e in errors)

    def test_temperature_equal_consecutive(self):
        """Equal consecutive temperatures should fail."""
        points = [[30, 30], [30, 60], [60, 80]]
        errors = validate_curve(points)
        assert any("increasing" in e.lower() for e in errors)

    def test_valid_boundary_values(self):
        """Boundary values at 20°C and 100°C should be valid."""
        points = [[20, 0], [100, 100]]
        assert validate_curve(points) == []

    def test_valid_speed_boundary_values(self):
        """Speed at 0% and 100% should be valid."""
        points = [[30, 0], [60, 100]]
        assert validate_curve(points) == []

    def test_multiple_errors(self):
        """Multiple validation errors should all be reported."""
        points = [[5, -10], [5, 150]]
        errors = validate_curve(points)
        assert len(errors) >= 2


class TestValidateHysteresis:
    def test_valid_hysteresis(self):
        """A valid hysteresis should return no errors."""
        assert validate_hysteresis(3.0) == []
        assert validate_hysteresis(0) == []
        assert validate_hysteresis(10.0) == []

    def test_negative_hysteresis(self):
        """Negative hysteresis should fail."""
        errors = validate_hysteresis(-5.0)
        assert any("non-negative" in e.lower() for e in errors)

    def test_high_hysteresis_warning(self):
        """Very high hysteresis should produce a warning."""
        errors = validate_hysteresis(25.0)
        assert any("unusually high" in e.lower() for e in errors)
