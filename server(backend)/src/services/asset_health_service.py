"""Deterministic, type-specific asset health and trend derivation."""


CRITICALITY = {"generator": "CRITICAL", "heating": "CRITICAL", "water": "CRITICAL",
              "battery": "HIGH", "comms": "HIGH", "lab": "MEDIUM", "living": "LOW", "fuel": "CRITICAL"}


def asset_criticality(asset) -> str:
    configured = getattr(asset, "criticality", None)
    return CRITICALITY.get(getattr(asset, "type", ""), configured or "MEDIUM") if configured in {None, "MEDIUM"} else configured


def _trend(readings, metric: str) -> tuple[str, float]:
    ordered = list(reversed(readings)) if readings and all(hasattr(reading, "timestamp") for reading in readings) else readings
    values = [reading.value for reading in ordered if reading.metric.lower() == metric.lower()]
    if len(values) < 2:
        return "STABLE", 0.0
    slope = (values[-1] - values[0]) / (len(values) - 1)
    return ("INCREASING" if slope > 0.02 else "DECREASING" if slope < -0.02 else "STABLE"), slope


def calculate_asset_health(asset, readings) -> dict:
    asset_type = getattr(asset, "type", "")
    online = getattr(asset, "online", True)
    values = {reading.metric.lower(): reading.value for reading in readings}
    drivers = []
    score = 100
    trend_name, slope = _trend(readings, "vibration")
    if not online:
        return {"status": "offline", "healthScore": 0, "healthDrivers": ["asset is offline"],
                "healthTrend": "DECREASING", "criticality": asset_criticality(asset)}
    if asset_type in {"generator", "chp"}:
        vibration, temperature = values.get("vibration", 0), values.get("temperature", 0)
        if vibration >= 6 or temperature > 105:
            score -= 65
            if vibration >= 6: drivers.append("vibration above critical threshold")
            if temperature > 105: drivers.append("temperature above critical threshold")
            status = "critical"
        elif vibration >= 4.5 or temperature > 95:
            score -= 32
            if vibration >= 4.5: drivers.append("vibration above baseline")
            if temperature > 95: drivers.append("elevated operating temperature")
            status = "warning"
        else:
            status = "normal"
        if trend_name == "INCREASING":
            score -= 8
            drivers.append("vibration trend is increasing")
    elif asset_type == "battery":
        soc = values.get("charge", values.get("soc", 100))
        status = "critical" if soc < 10 else "warning" if soc < 30 else "normal"
        score = 35 if status == "critical" else 70 if status == "warning" else 100
        if status != "normal": drivers.append("state of charge is low")
    elif asset_type == "water":
        status = "normal" if online else "offline"
        if values.get("level", 100) < 20:
            status, score = "warning", 65
            drivers.append("water reserve level is low")
    elif asset_type == "comms":
        quality = values.get("link quality", 100)
        status = "critical" if quality < 30 else "warning" if quality < 60 else "normal"
        score = 35 if status == "critical" else 70 if status == "warning" else 100
        if status != "normal": drivers.append("communication quality is degraded")
    else:
        status = "normal"
    return {"status": status, "healthScore": max(0, score),
            "healthDrivers": drivers or ["readings within configured range"],
            "healthTrend": trend_name, "criticality": asset_criticality(asset)}


def generator_health(readings: dict[str, float], online: bool, thresholds: dict[str, float]) -> str:
    if not online:
        return "offline"
    if readings.get("Vibration", 0) >= thresholds["vibCrit"] or readings.get("Temperature", 0) > 105:
        return "critical"
    if readings.get("Vibration", 0) >= thresholds["vibWarn"] or readings.get("Temperature", 0) > 95:
        return "warning"
    return "normal"
