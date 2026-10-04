"""Operational inventory consumption rules."""
from src.services.energy_service import MODEL
from src.services.occupancy_service import current_occupancy


def consumption_rates(station: dict, energy: dict) -> dict[str, float]:
    occupancy = current_occupancy(station)
    water_status = station.get("waterStatus", "normal")
    water_factor = 0.5 if water_status != "normal" else 1.0
    return {
        "fuel": energy["fuelRate"],
        "water": 1500.0 * (occupancy / 24) * water_factor,
        "food": 24.0 * (occupancy / 24),
        "med": 4.0,
        "parts": 3.2,
    }


def consume(station: dict, energy: dict, interval_hours: float = 1 / 120) -> dict[str, float]:
    rates = consumption_rates(station, energy)
    for item in station["inv"]:
        item["stock"] = max(0.0, item["stock"] - rates.get(item["k"], 0.0) * interval_hours)
    return rates
