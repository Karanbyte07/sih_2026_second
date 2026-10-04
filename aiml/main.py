from fastapi import FastAPI
from pydantic import BaseModel
import random

import pandas as pd
import joblib
import os

app = FastAPI(title="Antarctic Twin AI/ML Service")

# Load model on startup if it exists
model_path = 'models/isolation_forest.joblib'
isolation_forest = None
if os.path.exists(model_path):
    isolation_forest = joblib.load(model_path)

@app.get("/health")
def health_check():
    return {"status": "AI/ML API running", "model_loaded": isolation_forest is not None}

@app.post("/ml/anomaly")
def return_anomaly(payload: dict):
    if not isolation_forest:
        return {"score": 0.05, "severity": "Normal", "asset_id": payload.get("assetId"), "error": "Model not loaded"}
        
    try:
        # Expected features
        features = ['temperature', 'vibration', 'load_kw', 'power_consumption_kw', 'pressure', 'operating_hours']
        data = {f: [payload.get(f, 0.0)] for f in features}
        df = pd.DataFrame(data)
        
        score = isolation_forest.decision_function(df)[0]
        prediction = isolation_forest.predict(df)[0]
        
        # Scale score somewhat reasonably (lower score = more anomalous)
        # We will output a positive anomaly_score for severity mapping: 0 to 1
        anomaly_score = max(0, min(1, -score))
        
        severity = "Normal"
        if anomaly_score > 0.15:
            severity = "Critical"
        elif anomaly_score > 0.05 or prediction == -1:
            severity = "Warning"
            
        return {
            "score": round(anomaly_score, 3),
            "severity": severity,
            "asset_id": payload.get("assetId"),
            "raw_decision": round(score, 3)
        }
    except Exception as e:
        return {"error": str(e), "asset_id": payload.get("assetId")}

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
