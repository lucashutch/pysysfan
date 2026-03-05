"""Tests for pysysfan.temperature — Temperature aggregation logic."""

import pytest

from pysysfan.temperature import (
    AggregationMethod,
    aggregate_temperatures,
    lookup_and_aggregate,
    get_valid_aggregation_methods,
)
from pysysfan.platforms.base import SensorInfo


# ── AggregationMethod Enum ─────────────────────────────────────────────


def test_aggregation_method_from_string_valid():
    """Should parse valid aggregation method strings."""
    assert AggregationMethod.from_string("max") == AggregationMethod.MAX
    assert AggregationMethod.from_string("MAX") == AggregationMethod.MAX
    assert AggregationMethod.from_string("min") == AggregationMethod.MIN
    assert AggregationMethod.from_string("average") == AggregationMethod.AVERAGE
    assert AggregationMethod.from_string("median") == AggregationMethod.MEDIAN


def test_aggregation_method_from_string_invalid():
    """Should raise ValueError for invalid method strings."""
    with pytest.raises(ValueError, match="Invalid aggregation method"):
        AggregationMethod.from_string("invalid")

    with pytest.raises(ValueError, match="Invalid aggregation method"):
        AggregationMethod.from_string("")


# ── aggregate_temperatures ─────────────────────────────────────────────


def test_aggregate_max():
    """MAX aggregation should return the highest temperature."""
    temps = [45.0, 50.0, 55.0, 48.0]
    result = aggregate_temperatures(temps, "max")
    assert result == 55.0


def test_aggregate_min():
    """MIN aggregation should return the lowest temperature."""
    temps = [45.0, 50.0, 55.0, 48.0]
    result = aggregate_temperatures(temps, "min")
    assert result == 45.0


def test_aggregate_average():
    """AVERAGE aggregation should return the mean temperature."""
    temps = [40.0, 50.0, 60.0]
    result = aggregate_temperatures(temps, "average")
    assert result == 50.0


def test_aggregate_average_decimal():
    """AVERAGE should handle decimal results correctly."""
    temps = [40.0, 50.0]
    result = aggregate_temperatures(temps, "average")
    assert result == 45.0


def test_aggregate_median_odd():
    """MEDIAN aggregation with odd number of values."""
    temps = [40.0, 50.0, 60.0]
    result = aggregate_temperatures(temps, "median")
    assert result == 50.0


def test_aggregate_median_even():
    """MEDIAN aggregation with even number of values."""
    temps = [40.0, 60.0]
    result = aggregate_temperatures(temps, "median")
    assert result == 50.0


def test_aggregate_median_unsorted():
    """MEDIAN should work with unsorted input."""
    temps = [60.0, 40.0, 50.0]
    result = aggregate_temperatures(temps, "median")
    assert result == 50.0


def test_aggregate_single_value():
    """All methods should work with a single value."""
    temps = [42.0]
    assert aggregate_temperatures(temps, "max") == 42.0
    assert aggregate_temperatures(temps, "min") == 42.0
    assert aggregate_temperatures(temps, "average") == 42.0
    assert aggregate_temperatures(temps, "median") == 42.0


def test_aggregate_empty_list_raises():
    """Aggregating an empty list should raise ValueError."""
    with pytest.raises(ValueError, match="Cannot aggregate empty temperature list"):
        aggregate_temperatures([], "max")


def test_aggregate_invalid_method_raises():
    """Invalid aggregation method should raise ValueError."""
    temps = [45.0, 50.0]
    with pytest.raises(ValueError):
        aggregate_temperatures(temps, "invalid_method")


def test_aggregate_with_enum():
    """Should accept AggregationMethod enum directly."""
    temps = [45.0, 55.0, 50.0]
    result = aggregate_temperatures(temps, AggregationMethod.MAX)
    assert result == 55.0


# ── lookup_and_aggregate ───────────────────────────────────────────────


def create_mock_sensor(identifier, value):
    """Helper to create mock SensorInfo objects."""
    return SensorInfo(
        hardware_name="Test",
        hardware_type="cpu",
        sensor_name="Core",
        sensor_type="temperature",
        identifier=identifier,
        value=value,
    )


def test_lookup_and_aggregate_single_sensor():
    """Should aggregate a single sensor correctly."""
    sensors = [
        create_mock_sensor("/cpu/0/temp/0", 45.0),
    ]
    result = lookup_and_aggregate(["/cpu/0/temp/0"], sensors, "max")
    assert result == 45.0


def test_lookup_and_aggregate_multiple_sensors():
    """Should aggregate multiple sensors correctly."""
    sensors = [
        create_mock_sensor("/cpu/0/temp/0", 45.0),
        create_mock_sensor("/cpu/0/temp/1", 50.0),
        create_mock_sensor("/cpu/0/temp/2", 55.0),
    ]
    result = lookup_and_aggregate(
        ["/cpu/0/temp/0", "/cpu/0/temp/1", "/cpu/0/temp/2"], sensors, "max"
    )
    assert result == 55.0


def test_lookup_and_aggregate_with_missing_sensors():
    """Should use only found sensors when some are missing."""
    sensors = [
        create_mock_sensor("/cpu/0/temp/0", 45.0),
        create_mock_sensor("/cpu/0/temp/2", 55.0),
    ]
    # temp/1 is missing
    result = lookup_and_aggregate(
        ["/cpu/0/temp/0", "/cpu/0/temp/1", "/cpu/0/temp/2"], sensors, "max"
    )
    # Should only use temps 0 and 2
    assert result == 55.0


def test_lookup_and_aggregate_all_missing():
    """Should return None when no sensors are found."""
    sensors = [
        create_mock_sensor("/cpu/0/temp/0", 45.0),
    ]
    result = lookup_and_aggregate(["/cpu/0/temp/99"], sensors, "max")
    assert result is None


def test_lookup_and_aggregate_ignores_none_values():
    """Should ignore sensors with None values."""
    sensors = [
        create_mock_sensor("/cpu/0/temp/0", 45.0),
        SensorInfo(
            hardware_name="Test",
            hardware_type="cpu",
            sensor_name="Core",
            sensor_type="temperature",
            identifier="/cpu/0/temp/1",
            value=None,
        ),
        create_mock_sensor("/cpu/0/temp/2", 55.0),
    ]
    result = lookup_and_aggregate(
        ["/cpu/0/temp/0", "/cpu/0/temp/1", "/cpu/0/temp/2"], sensors, "average"
    )
    # Should average 45.0 and 55.0 (ignoring None)
    assert result == 50.0


def test_lookup_and_aggregate_all_none_values():
    """Should return None when all sensors have None values."""
    sensors = [
        SensorInfo(
            hardware_name="Test",
            hardware_type="cpu",
            sensor_name="Core",
            sensor_type="temperature",
            identifier="/cpu/0/temp/0",
            value=None,
        ),
    ]
    result = lookup_and_aggregate(["/cpu/0/temp/0"], sensors, "max")
    assert result is None


def test_lookup_and_aggregate_empty_temp_ids():
    """Should return None when temp_ids is empty."""
    sensors = [create_mock_sensor("/cpu/0/temp/0", 45.0)]
    result = lookup_and_aggregate([], sensors, "max")
    assert result is None


def test_lookup_and_aggregate_different_methods():
    """Should work with different aggregation methods."""
    sensors = [
        create_mock_sensor("/cpu/0/temp/0", 40.0),
        create_mock_sensor("/cpu/0/temp/1", 50.0),
        create_mock_sensor("/cpu/0/temp/2", 60.0),
    ]
    temp_ids = ["/cpu/0/temp/0", "/cpu/0/temp/1", "/cpu/0/temp/2"]

    assert lookup_and_aggregate(temp_ids, sensors, "max") == 60.0
    assert lookup_and_aggregate(temp_ids, sensors, "min") == 40.0
    assert lookup_and_aggregate(temp_ids, sensors, "average") == 50.0
    assert lookup_and_aggregate(temp_ids, sensors, "median") == 50.0


# ── get_valid_aggregation_methods ──────────────────────────────────────


def test_get_valid_aggregation_methods():
    """Should return list of valid method names."""
    methods = get_valid_aggregation_methods()
    assert isinstance(methods, list)
    assert "max" in methods
    assert "min" in methods
    assert "average" in methods
    assert "median" in methods
    assert len(methods) == 4
