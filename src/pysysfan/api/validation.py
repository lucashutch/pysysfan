def validate_curve(points: list[list[float]]) -> list[str]:
    """Validate curve configuration.

    Args:
        points: List of [temperature, speed] pairs.

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []

    if len(points) < 2:
        errors.append("Curve must have at least 2 points")

    for i, (temp, speed) in enumerate(points):
        if temp < 20 or temp > 100:
            errors.append(
                f"Temperature {temp}°C at point {i + 1} is out of range (20-100)"
            )
        if speed < 0 or speed > 100:
            errors.append(f"Speed {speed}% at point {i + 1} is out of range (0-100)")

    for i in range(1, len(points)):
        if points[i][0] <= points[i - 1][0]:
            errors.append("Temperatures must be in strictly increasing order")
            break

    return errors


def validate_hysteresis(hysteresis: float) -> list[str]:
    """Validate hysteresis value.

    Args:
        hysteresis: Hysteresis value in degrees Celsius.

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []

    if hysteresis < 0:
        errors.append("Hysteresis must be non-negative")
    elif hysteresis > 20:
        errors.append("Hysteresis value is unusually high (max recommended: 20°C)")

    return errors
