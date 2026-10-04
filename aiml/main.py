from fastapi import FastAPI
from pydantic import BaseModel
import random

app = FastAPI(title="Antarctic Twin AI/ML Service")

@app.get("/health")
def health_check():
    return {"status": "AI/ML API running"}

@app.post("/ml/anomaly")
def return_anomaly(payload: dict):
    # Dummy ML output for basic anomaly detection
    return {
        "score": round(random.uniform(0, 0.1), 3),
        "severity": "Normal",
        "asset_id": payload.get("assetId")
    }

@app.get("/ml/energy-forecast")
def get_energy_forecast(station_id: str):
    # Stub for advanced forecasting
    return {
        "predicted_demand": 120.0 + random.uniform(-10, 10),
        "horizon_hours": 24,
        "station_id": station_id
    }

@app.get("/ml/inventory-forecast")
def get_inventory_forecast(station_id: str):
    return {
        "predicted_consumption": 50.0,
        "days_to_depletion": 45,
        "station_id": station_id
    }

@app.get("/ml/asset-health/{id}")
def get_asset_health(id: str):
    return {
        "asset_id": id,
        "health_score": random.randint(85, 100),
        "maintenance_risk": "Low"
    }

@app.get("/ml/station-health/{id}")
def get_station_health(id: str):
    return {
        "station_id": id,
        "overall_health_index": 92
    }

@app.post("/ml/simulate")
def run_simulation(payload: dict):
    return {
        "predicted_impact": "Medium",
        "scenario": payload.get("scenario")
    }

@app.get("/ml/recommendations/{id}")
def get_recommendations(id: str):
    return {
        "station_id": id,
        "recommendations": [
            "Inspect primary generator next week.",
            "Schedule battery testing."
        ]
    }
