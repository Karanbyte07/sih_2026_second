"""Temporary deterministic scenario calculations using Phase 3 domain services."""
from copy import deepcopy

from src.services.digital_twin_service import DigitalTwinService
from src.services.energy_service import calculate_energy, update_battery
from src.services.inventory_service import consumption_rates
from src.services.simulation_control_service import get_controls
from src.services.logistics_service import LogisticsService

SCENARIO_LIMITS = {
    "temperatureOffset": (-30.0, 10.0), "windSpeed": (0.0, 40.0),
    "waterPlantAvailability": (0.0, 1.0), "occupancy": (1, 50),
    "operatingLoadFactor": (0.5, 1.5), "delayDays": (0, 60),
}

SCENARIOS = {"GENERATOR_FAILURE", "EXTREME_COLD", "HIGH_WIND", "SUPPLY_DELAY",
             "ENERGY_DEMAND_SURGE", "WATER_PLANT_DEGRADATION"}


class ScenarioService:
    def __init__(self, db):
        self.db = db
        self.twin_service = DigitalTwinService(db)

    def _state(self, station_id: str) -> dict:
        state = self.twin_service.calculation_state(station_id)
        if state:
            state["twin"] = self.twin_service.state(station_id)
        return state

    @staticmethod
    def _validate(inputs: dict) -> None:
        for key, value in inputs.items():
            if key in SCENARIO_LIMITS:
                low, high = SCENARIO_LIMITS[key]
                if not isinstance(value, (int, float)) or not low <= value <= high:
                    raise ValueError(f"{key} must be between {low} and {high}")

    def run(self, station_id: str, scenario: str, inputs: dict | None = None) -> dict:
        scenario = scenario.upper()
        aliases = {"GENERATOR_FAILURE": "GENERATOR_FAILURE", "TEMP_DROP": "EXTREME_COLD",
                   "DEMAND_INCREASE": "ENERGY_DEMAND_SURGE", "DELAYED_RESUPPLY": "SUPPLY_DELAY",
                   "REDUCED_GENERATION": "GENERATOR_FAILURE"}
        scenario = aliases.get(scenario, scenario)
        if scenario not in SCENARIOS:
            raise ValueError("Unknown simulation scenario")
        inputs = {**get_controls(station_id), **(inputs or {})}
        self._validate(inputs)
        baseline = self._state(station_id)
        if not baseline:
            return None
        simulated = deepcopy(baseline)
        if scenario == "GENERATOR_FAILURE":
            failures = inputs.get("generatorFailures", [inputs.get("assetId", "gen2")])
            for asset in simulated["assets"]:
                if asset["id"] in failures and asset["type"] == "generator":
                    asset["online"] = False
        elif scenario == "EXTREME_COLD":
            simulated["env"]["temp"] += inputs.get("temperatureOffset", -8)
        elif scenario == "HIGH_WIND":
            simulated["env"]["wind"] = inputs.get("windSpeed", 25)
        elif scenario == "ENERGY_DEMAND_SURGE":
            simulated["operatingLoadFactor"] = inputs.get("operatingLoadFactor", 1.25)
            simulated["baseLoad"] *= simulated["operatingLoadFactor"]
        elif scenario == "WATER_PLANT_DEGRADATION":
            simulated["waterPlantAvailability"] = inputs.get("waterPlantAvailability", 0.5)
        elif scenario == "SUPPLY_DELAY":
            simulated["delayDays"] = inputs.get("delayDays", 14)
        before = calculate_energy(baseline)
        after = calculate_energy(simulated)
        update_battery(simulated, after, interval_hours=1 / 24)
        rates = consumption_rates(simulated, after)
        projections = []
        for item in simulated["inv"]:
            rate = rates.get(item["k"], item.get("rate", 0))
            if item["k"] == "water":
                rate /= max(0.1, simulated.get("waterPlantAvailability", 1.0))
            days = item["stock"] / rate if rate else 999
            if scenario == "SUPPLY_DELAY":
                days -= simulated.get("delayDays", 0)
            risk = "critical" if days < 7 else "warning" if days < 14 else "ok"
            projections.append({"key": item["k"], "stock": round(item["stock"], 1), "rate": round(rate, 2),
                                "daysRemaining": round(max(0, days), 1), "risk": risk, "sourceType": "PREDICTED"})
        delta = {"demand": round(after["demand"] - before["demand"], 1),
                 "capacity": round(after["cap"] - before["cap"], 1),
                 "deficit": round(after["deficit"] - before["deficit"], 1),
                 "fuelRate": round(after["fuelRate"] - before["fuelRate"], 1),
                 "battery": round(simulated["battery"]["pct"] - baseline["battery"]["pct"], 1)}
        logistics = LogisticsService(self.db).state(
            station_id, simulated, simulated.get("delayDays", 0), baseline["twin"]["environmentSeverity"]
        )
        def view(metrics, state):
            fuel = next((item for item in state["inv"] if item["k"] == "fuel"), None)
            fuel_days = fuel["stock"] / metrics["fuelRate"] if fuel and metrics["fuelRate"] else 999
            return {"capacity": round(metrics["cap"], 1), "demand": round(metrics["demand"], 1),
                "deficit": round(metrics["deficit"], 1), "battery": round(state["battery"]["pct"], 1),
                "batteryHours": round(state["battery"]["pct"] * 400 / 100 / metrics["deficit"], 1) if metrics["deficit"] else None,
                "fuelDays": round(fuel_days, 1), "fuelGap": round(fuel_days - 24, 1),
                "fuelRate": round(metrics["fuelRate"], 1), "sourceType": "DERIVED"}
        return {"scenario": scenario, "stationId": station_id, "temporary": True,
            "before": view(before, baseline), "after": view(after, simulated),
                "delta": delta, "resources": projections, "logistics": logistics,
                "affectedAssets": [a["id"] for a in simulated["assets"] if a["online"] != next(x["online"] for x in baseline["assets"] if x["id"] == a["id"])],
                "affectedSystems": ["energy", "battery", "fuel", "inventory"],
                "alerts": [{"severity": "critical" if after["deficit"] > 0 else "warning", "title": f"{scenario.replace('_', ' ').title()} scenario"}],
                "recommendations": ["Restore generation or reduce non-critical loads."] if after["deficit"] > 0 else ["Monitor the projected resource impact."],
                "notes": ["Temporary scenario only; persistent telemetry was not changed."],
                "recs": ["Restore generation or reduce non-critical loads."] if after["deficit"] > 0 else ["Monitor the projected resource impact."],
                "sourceType": "DERIVED"}
