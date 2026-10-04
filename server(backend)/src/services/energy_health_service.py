"""Explainable energy health and risk calculation."""


def calculate_energy_health(energy: dict, fuel_days: float, assets: list[dict]) -> dict:
    drivers = []
    score = 100
    if energy["energyStatus"] == "CRITICAL_DEFICIT":
        score -= 45
        drivers.append("generation and battery support cannot cover demand")
    elif energy["energyStatus"] == "DEFICIT":
        score -= 25
        drivers.append("battery support is required to cover demand")
    if energy["generatorLoadPct"] > 90:
        score -= 15
        drivers.append("generator utilization is above 90%")
    if energy.get("batteryPct", 100) < 30:
        score -= 15
        drivers.append("battery reserve is below 30%")
    if fuel_days < 14:
        score -= 15
        drivers.append("fuel autonomy is below 14 days")
    if any(asset.get("status") == "offline" for asset in assets):
        score -= 10
        drivers.append("one or more generation assets are offline")
    score = max(0, min(100, score))
    status = "CRITICAL" if score < 50 else "ATTENTION" if score < 80 else "HEALTHY"
    return {"score": score, "status": status, "drivers": drivers or ["generation, storage, and fuel reserves are within configured limits"],
            "sourceType": "DERIVED"}
