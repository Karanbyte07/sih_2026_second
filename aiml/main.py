from fastapi import FastAPI
from pydantic import BaseModel
import random
from pathlib import Path

import pandas as pd
import joblib

app = FastAPI(title="Antarctic Twin AI/ML Service")

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
DATASET_PATH = BASE_DIR / "data" / "telemetry_dataset.csv"

# Load model artifacts relative to this file so the service works from any cwd.
model_path = MODEL_DIR / "isolation_forest.joblib"
isolation_forest = None
if model_path.exists():
    isolation_forest = joblib.load(model_path)

energy_model_path = MODEL_DIR / "energy_model.joblib"
energy_model = None
if energy_model_path.exists():
    energy_model = joblib.load(energy_model_path)

fuel_model_path = MODEL_DIR / "fuel_model.joblib"
fuel_model = None
if fuel_model_path.exists():
    fuel_model = joblib.load(fuel_model_path)

@app.get("/health")
def health_check():
    return {
        "status": "AI/ML API running",
        "models_loaded": {
            "isolation_forest": isolation_forest is not None,
            "energy_model": energy_model is not None,
            "fuel_model": fuel_model is not None
        },
        "model_artifacts": sorted(path.name for path in MODEL_DIR.glob("*.joblib")),
        "training_dataset_present": DATASET_PATH.exists(),
        "data_mode": "MODEL_ARTIFACTS_WITH_SIMULATED_BACKEND_TELEMETRY",
    }

@app.post("/ml/anomaly")
def return_anomaly(payload: dict):
    if not isolation_forest:
        return {"score": 0.05, "severity": "Normal", "asset_id": payload.get("assetId"), "error": "Model not loaded"}
        
    try:
        features = ['temperature', 'vibration', 'load_kw', 'power_consumption_kw', 'pressure', 'operating_hours']
        data = {f: [payload.get(f, 0.0)] for f in features}
        df = pd.DataFrame(data)
        
        score = isolation_forest.decision_function(df)[0]
        prediction = isolation_forest.predict(df)[0]
        
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
def get_energy_forecast(station_id: str, temperature: float = -15.0, load_kw: float = 50.0):
    if not energy_model:
        return {"predicted_demand": 120.0, "horizon_hours": 24, "station_id": station_id}
        
    # Create dummy DataFrame with recent state to predict next hour
    # We use some defaults if not provided since this is a GET
    df = pd.DataFrame([{
        'temperature': temperature,
        'vibration': 2.0,
        'load_kw': load_kw,
        'power_consumption_kw': load_kw * 1.1,
        'pressure': 980.0,
        'hour': 12,
        'day': 100
    }])
    
    predicted_demand = energy_model.predict(df)[0]
    return {
        "predicted_demand": round(float(predicted_demand), 2),
        "horizon_hours": 24,
        "station_id": station_id
    }

@app.get("/ml/inventory-forecast")
def get_inventory_forecast(station_id: str, current_stock: float = 10000.0, temperature: float = -15.0, load_kw: float = 50.0):
    if not fuel_model:
        return {"predicted_consumption": 50.0, "days_to_depletion": 45, "station_id": station_id}
        
    df = pd.DataFrame([{
        'temperature': temperature,
        'vibration': 2.0,
        'load_kw': load_kw,
        'power_consumption_kw': load_kw * 1.1,
        'pressure': 980.0,
        'hour': 12,
        'day': 100
    }])
    
    predicted_hourly_consumption = fuel_model.predict(df)[0]
    predicted_daily_consumption = predicted_hourly_consumption * 24
    
    days_to_depletion = 999
    if predicted_daily_consumption > 0:
        days_to_depletion = current_stock / predicted_daily_consumption
        
    return {
        "predicted_consumption": round(float(predicted_daily_consumption), 2),
        "days_to_depletion": round(float(days_to_depletion), 1),
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
