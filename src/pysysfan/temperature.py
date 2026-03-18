"""Temperature sensor aggregation utilities."""

from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pysysfan.platforms.base import SensorInfo


class AggregationMethod(Enum):
    """Supported temperature aggregation methods."""

    MAX = "max"
    MIN = "min"
    AVERAGE = "average"
    MEDIAN = "median"

    @classmethod
    def from_string(cls, value: str) -> AggregationMethod:
        """Parse aggregation method from string."""
        try:
            return cls(value.lower())
        except ValueError:
            valid = [m.value for m in cls]
            raise ValueError(
                f"Invalid aggregation method '{value}'. Valid options: {valid}"
            )


def aggregate_temperatures(
    temp_values: list[float],
    method: str | AggregationMethod = AggregationMethod.MAX,
) -> float:
    """
    Aggregate multiple temperature readings into a single value.

    Args:
        temp_values: List of temperature readings (in Celsius)
        method: Aggregation method ("max", "min", "average", "median")

    Returns:
        Aggregated temperature value

    Raises:
        ValueError: If temp_values is empty or method is invalid
    """
    if not temp_values:
        raise ValueError("Cannot aggregate empty temperature list")

    if isinstance(method, str):
        method = AggregationMethod.from_string(method)

    if method == AggregationMethod.MAX:
        return max(temp_values)
    elif method == AggregationMethod.MIN:
        return min(temp_values)
    elif method == AggregationMethod.AVERAGE:
        return sum(temp_values) / len(temp_values)
    elif method == AggregationMethod.MEDIAN:
        sorted_temps = sorted(temp_values)
        n = len(sorted_temps)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_temps[mid - 1] + sorted_temps[mid]) / 2
        else:
            return sorted_temps[mid]
    else:
        raise ValueError(f"Unknown aggregation method: {method}")


def lookup_and_aggregate(
    temp_ids: list[str],
    temperatures: list[SensorInfo],
    method: str = "max",
    sensor_index: dict[str, SensorInfo] | None = None,
) -> float | None:
    """
    Look up multiple temperature sensors and aggregate their values.

    Args:
        temp_ids: List of temperature sensor identifiers
        temperatures: Available temperature readings from hardware
        method: Aggregation method

    Returns:
        Aggregated temperature or None if no sensors found
    """
    if sensor_index is None:
        sensor_index = {sensor.identifier: sensor for sensor in temperatures}

    values = []
    for temp_id in temp_ids:
        sensor = sensor_index.get(temp_id)
        if sensor is not None and sensor.value is not None:
            values.append(sensor.value)

    if not values:
        return None

    return aggregate_temperatures(values, method)


def build_temperature_index(temperatures: list[SensorInfo]) -> dict[str, SensorInfo]:
    """Build an identifier-indexed sensor lookup map for a polling cycle."""
    return {sensor.identifier: sensor for sensor in temperatures}


def get_valid_aggregation_methods() -> list[str]:
    """Return list of valid aggregation method names."""
    return [m.value for m in AggregationMethod]
