"""Fan curve logic with linear interpolation and hysteresis."""

from __future__ import annotations
from dataclasses import dataclass, field
import bisect


@dataclass
class CurvePoint:
    temperature: float
    speed: float


class FanCurve:
    """Evaluates fan speed based on temperature points with linear interpolation.

    Supports hysteresis to prevent rapid fan speed changes when temperature
    fluctuates around a threshold.
    """

    def __init__(
        self,
        name: str,
        points: list[tuple[float, float]],
        hysteresis: float = 2.0
    ):
        """
        Args:
            name: Human-readable name for the curve.
            points: List of (temperature, speed_percent) tuples.
            hysteresis: Degrees Celsius to wait before decreasing fan speed.
        """
        self.name = name
        # Sort points by temperature
        self._points = sorted([CurvePoint(t, s) for t, s in points], key=lambda p: p.temperature)
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

        self._last_speed = target_speed
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
