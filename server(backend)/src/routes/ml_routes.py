"""
Routes that expose AI/ML microservice data to the frontend.

These endpoints act as a Backend-for-Frontend (BFF) layer:
 • They call the AI/ML microservice via aiml_client
 • Enrich the response with backend context (station name, twin state)
 • Return a single JSON the frontend can render directly
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import User
from src.middleware.auth import get_current_user
from src.services import aiml_client
from src.services.digital_twin_service import DigitalTwinService
from src.services.energy_service import calculate_energy
from src.services.operational_service import inventory_output

router = APIRouter(prefix="/api/ml", tags=["ai-ml"])


@router.get("/health")
async def aiml_health(user: User = Depends(get_current_user)):
    result = aiml_client.ml_health()
    return result or {"status": "UNAVAILABLE", "models_loaded": {}}


@router.get("/stations/{station_id}/anomalies")
async def station_anomalies(station_id: str,
                            user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    twin = DigitalTwinService(db).state(station_id)
    if not twin:
        raise HTTPException(status_code=404, detail="Unknown station")

    results = []
    for asset in twin["assets"]:
        if not asset["readings"]:
            continue
        readings = {reading["k"]: reading["v"] for reading in asset["readings"]}
        ml = aiml_client.ml_anomaly(
            asset_id=asset["id"],
            temperature=readings.get("temperature", 0.0),
            vibration=readings.get("vibration", 2.0),
            load_kw=asset.get("cap", 50),
            power_kw=asset.get("cap", 50) * 1.1,
            pressure=980,
            operating_hours=asset.get("hours", 1000),
        )
        results.append({
            "assetId": asset["id"],
            "name": asset["name"],
            "type": asset["type"],
            "status": asset["status"],
            "ml": ml or {"score": None, "severity": "Unknown", "error": "ML service unavailable"},
        })
    return {"stationId": station_id, "anomalies": results, "ts": datetime.utcnow().isoformat()}


@router.get("/stations/{station_id}/forecast")
async def station_forecast(station_id: str,
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    twin_service = DigitalTwinService(db)
    state = twin_service.calculation_state(station_id)
    if not state:
        raise HTTPException(status_code=404, detail="Unknown station")

    temp = state["env"]["temp"]
    load = state["baseLoad"]
    energy = aiml_client.ml_energy_forecast(station_id, temperature=temp, load_kw=load)

    fuel_item = next((i for i in state["inv"] if i["k"] == "fuel"), None)
    fuel_stock = fuel_item["stock"] if fuel_item else 10000
    inventory = aiml_client.ml_inventory_forecast(station_id, current_stock=fuel_stock,
                                                   temperature=temp, load_kw=load)

    health = aiml_client.ml_station_health(station_id)
    recommendations = aiml_client.ml_recommendations(station_id)

    return {
        "stationId": station_id,
        "energy": energy or {"predicted_demand": None, "error": "ML unavailable"},
        "inventory": inventory or {"predicted_consumption": None, "error": "ML unavailable"},
        "health": health or {"overall_health_index": None, "error": "ML unavailable"},
        "recommendations": (recommendations or {}).get("recommendations", []),
        "ts": datetime.utcnow().isoformat(),
    }


@router.post("/stations/{station_id}/simulate")
async def ml_simulate(station_id: str, body: dict,
                      user: User = Depends(get_current_user)):
    result = aiml_client.ml_simulate(station_id, body.get("scenario", ""), body.get("value"))
    if not result:
        raise HTTPException(status_code=503, detail="AI/ML service unavailable")
    return result
