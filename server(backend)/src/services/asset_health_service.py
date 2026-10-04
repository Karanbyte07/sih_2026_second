"""Deterministic rule-based asset health derivation."""


def generator_health(readings: dict[str, float], online: bool, thresholds: dict[str, float]) -> str:
    if not online:
        return "offline"
    if readings.get("Vibration", 0) >= thresholds["vibCrit"] or readings.get("Temperature", 0) > 105:
        return "critical"
    if readings.get("Vibration", 0) >= thresholds["vibWarn"] or readings.get("Temperature", 0) > 95:
        return "warning"
    return "normal"
