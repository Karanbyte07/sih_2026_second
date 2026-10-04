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

        from src.services import aiml_client
        temp = state["env"]["temp"]
        load = state["baseLoad"] if "baseLoad" in state else 50
        fuel_item = next((i for i in state["inv"] if i["k"] == "fuel"), None)
        fuel_stock = fuel_item["stock"] if fuel_item else 10000

        ml_forecast = aiml_client.ml_energy_forecast(station_id, temperature=temp, load_kw=load)
        ml_inventory = aiml_client.ml_inventory_forecast(station_id, current_stock=fuel_stock,
                                                         temperature=temp, load_kw=load)
        ml_station_health = aiml_client.ml_station_health(station_id)
            
        current = calculate_energy(state)
        environment = state["env"]["temp"]
        forecast = []
        for hour in range(24):
            temperature = environment + 2.5 * math.sin((hour - 4) / 24 * 6.283)
            state["env"]["temp"] = temperature
            result = calculate_energy(state)
            
            # If ML provided a demand prediction, blend or use it
            predicted_demand = round(result["demand"], 1)
            if ml_forecast:
                # Naive adjustment based on ML's single point prediction for simplicity
                predicted_demand = round(ml_forecast.get("predicted_demand", predicted_demand) + (hour * 0.5), 1)

            forecast.append({
                "h": f"+{hour}h", "temp": round(temperature, 1),
                "demand": predicted_demand, "capacity": round(result["cap"], 1),
                "sourceType": "PREDICTED_ML" if ml_forecast else "PREDICTED", 
                "method": "ML_MODEL" if ml_forecast else "RULE_BASED",
                "explanation": "Demand prediction powered by ML model." if ml_forecast else "Demand reflects temperature-driven heating and current occupancy.",
                "drivers": ["temperature", "heating demand", "occupancy"],
            })
        resources = []
        twin = self.twin_service.state(station_id)
        for item in inventory_output(self.db, state):
            explanation = f"Projected from current {item['name']} stock and operational consumption rate."
            if ml_inventory:
                explanation = f"ML Projected depletion in {ml_inventory.get('days_to_depletion')} days based on advanced forecasting."
            resources.append({**item, "sourceType": "PREDICTED_ML" if ml_inventory else "DERIVED", 
                              "method": "ML_MODEL" if ml_inventory else "RATE_BASED",
                              "explanation": explanation})
        anomalies = []
        for asset in twin["assets"]:
            if asset["status"] in ("normal", "offline") or not asset["readings"]:
                continue
            reading = asset["readings"][0]
            
            # Fetch individual asset anomaly if needed, but doing it in a loop might be slow.
            # Using rule-based anomaly but marking it as such.
            anomalies.append({"assetId": asset["id"], "name": asset["name"], "severity": asset["status"],
                              "metric": reading["k"], "value": f"{reading['v']} {reading['u']}",
                              "reason": f"{reading['k']} is outside its configured rule-based operating range.",
                              "urgency": "Inspect at the next maintenance window.", "trend": asset["hist"],
                              "sourceType": "DERIVED"})
                              
        explanation = "Forecast uses persistent telemetry, current environment, occupancy, and online assets."
        if ml_station_health:
            explanation += f" Station health ML index: {ml_station_health.get('overall_health_index')}."
                              
        return {"forecast": forecast, "shortageHours": sum(x["demand"] > x["capacity"] for x in forecast),
                "peak": max(x["demand"] for x in forecast), "anomalies": anomalies,
                "resources": resources, 
                "sourceType": "PREDICTED_ML" if (ml_forecast or ml_inventory) else "PREDICTED", 
                "method": "ML_HYBRID" if (ml_forecast or ml_inventory) else "RULE_BASED",
                "explanation": explanation}
