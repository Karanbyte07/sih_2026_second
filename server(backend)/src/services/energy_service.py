"""Configurable energy domain model and deterministic generator dispatch."""
from src.services.occupancy_service import occupancy_factor


MODEL = {
    "heating_per_degree_kw": 0.9,
    "water_load_kw": 5.0,
    "lab_load_kw": 12.0,
    "comms_load_kw": 7.0,
    "lighting_load_kw": 5.0,
    "other_load_kw": 3.0,
    "battery_efficiency": 0.92,
    "battery_max_charge_kw": 20.0,
    "battery_max_discharge_kw": 20.0,
    "fuel_l_per_kwh": 0.30,
}

STATION_ENERGY_CONFIG = {
    "bharati": {
        "rated_capacity_kva": 100.0,
        "power_factor_assumption": 0.80,
        "usable_capacity_kw": 80.0,
        "rated_source_type": "PUBLIC",
        "usable_source_type": "SIMULATED",
    },
    "maitri": {
        "rated_capacity_kva": None,
        "power_factor_assumption": None,
        "usable_capacity_kw": 30.0,
        "rated_source_type": "SIMULATED",
        "usable_source_type": "SIMULATED",
    },
}


def station_energy_config(station_id: str) -> dict:
    return STATION_ENERGY_CONFIG.get(station_id, STATION_ENERGY_CONFIG["maitri"]).copy()


def dispatch_generation(demand_kw: float, units: list[dict], renewable_kw: float = 0.0) -> dict:
    """Dispatch online units in stable order without exceeding unit capacity."""
    remaining = max(0.0, demand_kw - renewable_kw)
    dispatched = []
    for unit in units:
        capacity = max(0.0, float(unit.get("usable_capacity_kw", unit.get("cap", 0))))
        online = bool(unit.get("online", False))
        output = min(remaining, capacity) if online else 0.0
        remaining -= output
        dispatched.append({**unit, "usable_capacity_kw": capacity, "output_kw": output,
                           "load_pct": output / capacity * 100 if capacity else 0.0})
    generation = renewable_kw + sum(unit["output_kw"] for unit in dispatched)
    capacity = renewable_kw + sum(unit["usable_capacity_kw"] for unit in dispatched if unit["online"])
    return {"units": dispatched, "generation_kw": generation, "capacity_kw": capacity,
            "deficit_kw": max(0.0, demand_kw - generation),
            "surplus_kw": max(0.0, generation - demand_kw)}


def calculate_energy(station: dict) -> dict:
    env = station["env"]
    heating = max(0.0, -5.0 - env["temp"]) * MODEL["heating_per_degree_kw"] + 10.0
    factor = occupancy_factor(station)
    operating_factor = station.get("operatingLoadFactor", 1.0)
    base = station["baseLoad"] * (0.85 + 0.15 * factor) * operating_factor
    water = MODEL["water_load_kw"] * (0.6 + factor) * (1 + (1 - station.get("waterPlantAvailability", 1.0)) * 0.2)
    lab = MODEL["lab_load_kw"] * (0.7 + 0.3 * factor) * operating_factor
    comms = MODEL["comms_load_kw"] * (0.8 + env["wind"] / 100)
    lighting = MODEL["lighting_load_kw"] * (0.7 + 0.3 * factor)
    other = MODEL["other_load_kw"]
    demand = base + heating + water + lab + comms + lighting + other
    units = [a for a in station["assets"] if a["type"] in ("generator", "chp")]
    dispatch = dispatch_generation(demand, units, station.get("solar", 0) * station.get("capFactor", 1))
    generator_output = sum(unit["output_kw"] for unit in dispatch["units"])
    battery = station.get("battery", {})
    battery_available_kw = min(MODEL["battery_max_discharge_kw"], battery.get("pct", 0) / 100 * battery.get("kwh", 0))
    battery_support = min(dispatch["deficit_kw"], battery_available_kw)
    net_deficit = max(0.0, dispatch["deficit_kw"] - battery_support)
    status = "CRITICAL_DEFICIT" if net_deficit > 0 else "DEFICIT" if dispatch["deficit_kw"] > 0 else "SURPLUS" if dispatch["surplus_kw"] > 0 else "BALANCED"
    return {"base": base, "heat": heating, "water": water, "lab": lab, "comms": comms,
            "lighting": lighting, "other": other, "demand": demand,
            "capGen": dispatch["capacity_kw"] - station.get("solar", 0) * station.get("capFactor", 1),
            "cap": dispatch["capacity_kw"], "output": dispatch["generation_kw"],
            "genOut": generator_output, "deficit": net_deficit,
            "generationDeficit": dispatch["deficit_kw"], "surplus": dispatch["surplus_kw"],
            "batterySupport": battery_support, "fuelRate": generator_output * MODEL["fuel_l_per_kwh"] * 24,
            "generatorLoadPct": generator_output / max(0.1, dispatch["capacity_kw"] - station.get("solar", 0)) * 100,
            "dispatch": dispatch["units"], "energyStatus": status}


def update_battery(station: dict, energy: dict, interval_hours: float = 1 / 120) -> None:
    battery = station["battery"]
    battery["charge_rate_kw"] = 0.0
    battery["discharge_rate_kw"] = 0.0
    if energy["generationDeficit"] > 0:
        discharge = min(energy["generationDeficit"], MODEL["battery_max_discharge_kw"])
        delta = discharge * interval_hours / battery["kwh"] * 100 / MODEL["battery_efficiency"]
        battery["discharge_rate_kw"] = discharge
        battery["pct"] -= delta
    else:
        charge = min(energy["surplus"], MODEL["battery_max_charge_kw"])
        delta = charge * interval_hours * MODEL["battery_efficiency"] / battery["kwh"] * 100
        battery["charge_rate_kw"] = charge
        battery["pct"] += delta
    battery["pct"] = max(0.0, min(100.0, battery["pct"]))
