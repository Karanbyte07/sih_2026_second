"""Configurable prototype energy calculations for the digital twin."""
from src.services.occupancy_service import occupancy_factor


MODEL = {
    "heating_per_degree_kw": 0.9,
    "water_load_kw": 5.0,
    "lab_load_kw": 12.0,
    "comms_load_kw": 7.0,
    "battery_efficiency": 0.92,
    "fuel_l_per_kwh": 0.30,
}


def calculate_energy(station: dict) -> dict:
    env = station["env"]
    heating = max(0.0, -5.0 - env["temp"]) * MODEL["heating_per_degree_kw"] + 10.0
    factor = occupancy_factor(station)
    water = MODEL["water_load_kw"] * (0.6 + factor)
    lab = MODEL["lab_load_kw"] * (0.7 + 0.3 * factor)
    comms = MODEL["comms_load_kw"] * (0.8 + station["env"]["wind"] / 100)
    demand = station["baseLoad"] + heating + water + lab + comms
    available_generators = [a for a in station["assets"] if a["type"] == "generator" and a["online"]]
    cap_gen = sum(a["cap"] for a in available_generators) * station["capFactor"]
    capacity = cap_gen + station["solar"] * station["capFactor"]
    output = min(demand, capacity)
    generator_output = max(0.0, output - station["solar"] * station["capFactor"])
    return {"heat": heating, "water": water, "lab": lab, "comms": comms,
            "demand": demand, "capGen": cap_gen, "cap": capacity,
            "output": output, "genOut": generator_output,
            "deficit": max(0.0, demand - capacity),
            "surplus": max(0.0, capacity - demand),
            "fuelRate": generator_output * MODEL["fuel_l_per_kwh"] * 24}


def update_battery(station: dict, energy: dict, interval_hours: float = 1 / 120) -> None:
    battery = station["battery"]
    if energy["deficit"] > 0:
        delta = energy["deficit"] * interval_hours / battery["kwh"] * 100 / MODEL["battery_efficiency"]
        battery["pct"] -= delta
    else:
        delta = energy["surplus"] * interval_hours * MODEL["battery_efficiency"] / battery["kwh"] * 100
        battery["pct"] += delta
    battery["pct"] = max(0.0, min(100.0, battery["pct"]))
