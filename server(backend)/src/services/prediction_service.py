"""Database-backed, explainable rule-based forecasts."""
from datetime import datetime, timedelta
import math

from sqlalchemy.orm import Session

from src.services.digital_twin_service import DigitalTwinService
from src.services.energy_service import calculate_energy
from src.services.operational_service import energy_history, inventory_output


class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.twin_service = DigitalTwinService(db)

    def _calculation_state(self, station_id: str) -> dict:
        return self.twin_service.calculation_state(station_id)

    def forecast(self, station_id: str) -> dict:
        state = self._calculation_state(station_id)
        if not state:
            return None
        current = calculate_energy(state)
        environment = state["env"]["temp"]
        forecast = []
        for hour in range(24):
            temperature = environment + 2.5 * math.sin((hour - 4) / 24 * 6.283)
            state["env"]["temp"] = temperature
            result = calculate_energy(state)
            forecast.append({
                "h": f"+{hour}h", "temp": round(temperature, 1),
                "demand": round(result["demand"], 1), "capacity": round(result["cap"], 1),
                "sourceType": "PREDICTED", "method": "RULE_BASED",
                "explanation": "Demand reflects temperature-driven heating and current occupancy.",
                "drivers": ["temperature", "heating demand", "occupancy"],
            })
        resources = []
        twin = self.twin_service.state(station_id)
        for item in inventory_output(self.db, state):
            resources.append({**item, "sourceType": "DERIVED", "method": "RATE_BASED",
                              "explanation": f"Projected from current {item['name']} stock and operational consumption rate."})
        anomalies = []
        for asset in twin["assets"]:
            if asset["status"] in ("normal", "offline") or not asset["readings"]:
                continue
            reading = asset["readings"][0]
            anomalies.append({"assetId": asset["id"], "name": asset["name"], "severity": asset["status"],
                              "metric": reading["k"], "value": f"{reading['v']} {reading['u']}",
                              "reason": f"{reading['k']} is outside its configured rule-based operating range.",
                              "urgency": "Inspect at the next maintenance window.", "trend": asset["hist"],
                              "sourceType": "DERIVED"})
        return {"forecast": forecast, "shortageHours": sum(x["demand"] > x["capacity"] for x in forecast),
                "peak": max(x["demand"] for x in forecast), "anomalies": anomalies,
                "resources": resources, "sourceType": "PREDICTED", "method": "RULE_BASED",
                "explanation": "Forecast uses persistent telemetry, current environment, occupancy, and online assets."}
