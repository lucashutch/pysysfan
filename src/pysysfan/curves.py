"""Fan curve logic with linear interpolation and hysteresis."""

from __future__ import annotations
from dataclasses import dataclass
import bisect


class InvalidCurveError(ValueError):
    """Raised when a curve name is invalid or out of range."""

    pass


@dataclass
class CurvePoint:
    temperature: float
    speed: float


class StaticCurve:
    """A curve that always returns a fixed percentage (no temperature dependency).

    Used for special curves like "off" (0%), "on" (100%), or custom static percentages.
    """

    def __init__(self, speed: float, name: str = "static"):
        """
        Args:
            speed: Fixed fan speed percentage (0-100).
            name: Human-readable name for the curve.
        """
        self.speed = speed
        self.name = name

    def evaluate(self, current_temp: float) -> float:
        """Always returns the fixed speed, ignoring temperature."""
        return self.speed


class FanCurve:
    """Evaluates fan speed based on temperature points with linear interpolation.

    Supports hysteresis to prevent rapid fan speed changes when temperature
    fluctuates around a threshold.
    """

    def __init__(
        self, name: str, points: list[tuple[float, float]], hysteresis: float = 2.0
    ):
        """
        Args:
            name: Human-readable name for the curve.
            points: List of (temperature, speed_percent) tuples.
            hysteresis: Degrees Celsius to wait before decreasing fan speed.
        """
        self.name = name
        # Sort points by temperature
        self._points = sorted(
            [CurvePoint(t, s) for t, s in points], key=lambda p: p.temperature
        )
        self.hysteresis = hysteresis

        if not self._points:
            raise ValueError(f"Curve '{name}' must have at least one point.")

        self._last_speed = 0.0
        self._last_temp = 0.0

    def evaluate(self, current_temp: float) -> float:
        """Calculate the target fan speed percent for a given temperature.

        Interpolates linearly between the defined points.
        Clamps to the first/last point values outside the defined range.
        Applies hysteresis when temperature is falling.
        """
        # Linear interpolation
        target_speed = self._interpolate(current_temp)

        # Apply hysteresis on falling temperature
        # Only apply if we have a previous state
        if target_speed < self._last_speed:
            # If temp hasn't dropped by at least 'hysteresis' since we peaked,
            # or if the current temp is still high enough to justify the last speed,
            # we stay at the higher speed.

            # Simple implementation: if temp is falling, we don't drop speed
            # unless current_temp + hysteresis < temp_that_justified_last_speed.
            # But a simpler way: just check if the new target speed is lower,
            # and if current_temp > (temp_required_for_last_speed - hysteresis).

            # Find what temp would result in self._last_speed
            # (Note: this is simplified, works best for monotonic curves)
            if current_temp > (self._last_temp - self.hysteresis):
                return self._last_speed

        # Only advance the hysteresis reference temperature when speed is strictly
        # increasing.  If temperature falls through a plateau (e.g. the curve is
        # clamped at 100%) target_speed == _last_speed, and updating _last_temp to
        # the lower current temperature would silently shift the effective hysteresis
        # band downward each call.
        prev_speed = self._last_speed
        self._last_speed = target_speed
        if target_speed > prev_speed:
            self._last_temp = current_temp
        return target_speed

    def _interpolate(self, temp: float) -> float:
        """Perform linear interpolation between defined points."""
        if temp <= self._points[0].temperature:
            return self._points[0].speed

        if temp >= self._points[-1].temperature:
            return self._points[-1].speed

        # Find the segment
        # bisect_right returns the index where 'temp' would be inserted to maintain order
        idx = bisect.bisect_right([p.temperature for p in self._points], temp)
        p1 = self._points[idx - 1]
        p2 = self._points[idx]

        # Linear interpolation formula: y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
        slope = (p2.speed - p1.speed) / (p2.temperature - p1.temperature)
        return p1.speed + (temp - p1.temperature) * slope

    @property
    def points(self) -> list[tuple[float, float]]:
        return [(p.temperature, p.speed) for p in self._points]


def parse_curve(name: str) -> StaticCurve | None:
    """Parse a curve name and return StaticCurve for special values.

    Special names (case-insensitive):
    - "off" → StaticCurve(0%)
    - "on" → StaticCurve(100%)
    - numeric (e.g., "50", "75%", "0", "100") → StaticCurve(%) with that value

    For numeric values, raises InvalidCurveError if:
    - Value is outside 0-100 range
    - Value is not a valid number

    Returns None if not a special curve (use regular config lookup).

    Args:
        name: The curve name to parse.

    Returns:
        StaticCurve instance for special curves, or None for regular curve names.

    Raises:
        InvalidCurveError: If a numeric value is outside the 0-100 range.
    """
    name_stripped = name.strip()
    name_lower = name_stripped.lower()

    # Handle special keywords (case-insensitive)
    if name_lower == "off":
        return StaticCurve(0.0, name="off")
    if name_lower == "on":
        return StaticCurve(100.0, name="on")

    # Handle numeric values (with optional % suffix)
    numeric_name = name_lower.rstrip("%")
    try:
        value = float(numeric_name)
    except ValueError:
        # Not a number, not a special curve
        return None

    # Validate range
    if value < 0 or value > 100:
        raise InvalidCurveError(f"Fan speed must be between 0 and 100, got {value}")
    return StaticCurve(value, name=f"{value}%")
