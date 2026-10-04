"""
Station routes — all /api/stations/* endpoints.

Serves: overview, assets, energy, logistics, environment,
        alerts, maintenance, predictions, and inventory update.
Data flows from the in-memory simulation (sim.S) to match the
existing frontend API contract exactly.
"""
import copy
import math
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import Alert, Asset, EnvironmentProviderStatus, InventoryItem, MaintenanceTask, ResupplySchedule, Station, User
from src.middleware.auth import get_current_user, require_role
from src.services.audit_service import log_action
from src.services.operational_service import (
    alert_output, energy_history, environment_history, inventory_output,
    latest_energy, record_inventory_change, sync_alerts,
)
from src.services.digital_twin_service import DigitalTwinService
from src.services.prediction_service import PredictionService
from src.services.scenario_service import SCENARIO_LIMITS, ScenarioService
from src.services.simulation_control_service import reset_controls, set_controls
from src.services.energy_service import calculate_energy
from src.services.energy_health_service import calculate_energy_health
from src.services.logistics_service import LogisticsService
from src.services.environment_ingestion_service import PublicDataIngestionService
from src.services.public_environment_provider import PublicEnvironmentProvider
from src.config.settings import get_settings
import src.utils.simulation as sim

router = APIRouter(prefix="/api/stations", tags=["stations"])
api_router = APIRouter(prefix="/api", tags=["operations"])


def _get_station(station_id: str) -> dict:
    """Resolve station ID to in-memory state or raise 404."""
    s = sim.S.get(station_id)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown station")
    return s


# ---------------------------------------------------------------------------
# GET /api/stations
# ---------------------------------------------------------------------------
@router.get("")
async def list_stations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    age_ms = 0
    twin = DigitalTwinService(db)
    def station_status(twin_state):
        if any(alert["severity"] == "critical" for alert in twin_state["alerts"]):
            return "Critical"
        if twin_state["freshness"]["status"] == "STALE" or any(alert["severity"] == "warning" for alert in twin_state["alerts"]):
            return "Attention"
        return "Operational"

    return {
        "ts": int(datetime.now().timestamp() * 1000),
        "age": age_ms,
        "simulated": True,
        "stations": [
            {"id": station.id, "name": station.name, "status": station_status(twin.state(station.id))}
            for station in db.query(Station).filter(Station.active == True).all()
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/stations/:id/overview
# ---------------------------------------------------------------------------
@router.get("/{station_id}/overview")
async def get_overview(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    twin_service = DigitalTwinService(db)
    twin = twin_service.state(station_id)
    if not twin:
        raise HTTPException(status_code=404, detail="Unknown station")
    s = twin_service.calculation_state(station_id)
    m = calculate_energy(s)
    f = next((i for i in twin["inventory"] if i.item_key == "fuel"), None)
    al = twin["alerts"]
    env = twin["environment"] or sim.env_now(s)
    energy = twin["energy"] or {}
    assets = twin["assets"]
    status = "CRITICAL" if any(a["severity"] == "critical" for a in al) else "ATTENTION" if al else "OPERATIONAL"

    return {
        "id": twin["id"],
        "name": twin["name"],
        "status": status,
        "kpis": {
            "gen": energy.get("gen", sim.r1(m["output"])),
            "demand": energy.get("demand", sim.r1(m["demand"])),
            "cap": energy.get("cap", sim.r1(m["cap"])),
            "fuelPct": round(f.stock / f.capacity * 100) if f else 0,
            "fuelDays": sim.r1(f.stock / max(0.1, m["fuelRate"])) if f else 0,
            "battery": energy.get("battery", sim.r1(s["battery"]["pct"])),
            "normal": sum(1 for a in assets if a["status"] == "normal"),
            "total": len(assets),
        },
        "env": env,
        "alerts": [a for a in al if not a["acked"]][:4],
        "alertCount": {
            "critical": sum(1 for a in al if a["severity"] == "critical" and not a["acked"]),
            "warning": sum(1 for a in al if a["severity"] == "warning" and not a["acked"]),
        },
        "assets": assets,
        "chain": sim.chain_info(s),
        "freshness": twin["freshness"],
    }


# ---------------------------------------------------------------------------
# GET /api/stations/:id/assets
# ---------------------------------------------------------------------------
@router.get("/{station_id}/assets")
async def get_assets(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    twin = DigitalTwinService(db).state(station_id)
    if not twin:
        raise HTTPException(status_code=404, detail="Unknown station")
    return {"assets": twin["assets"], "env": twin["environment"]}


# ---------------------------------------------------------------------------
# GET /api/stations/:id/energy
# ---------------------------------------------------------------------------
@router.get("/{station_id}/energy")
async def get_energy(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    twin_service = DigitalTwinService(db)
    twin = twin_service.state(station_id)
    if not twin:
        raise HTTPException(status_code=404, detail="Unknown station")
    s = twin_service.calculation_state(station_id)
    m = calculate_energy(s)
    base = s["baseLoad"]
    fuel = inventory_output(db, s)[0]
    fuel_days = fuel["stock"] / m["fuelRate"] if m["fuelRate"] else 999
    history = energy_history(db, station_id)
    demands = [row["demand"] for row in history if row.get("demand") is not None]
    health = calculate_energy_health({**m, "batteryPct": (twin["energy"] or {}).get("battery", s["battery"]["pct"])}, fuel_days, twin["assets"])
    return {
        "history": history,
        "now": {
            "gen": sim.r1(m["output"]),
            "demand": sim.r1(m["demand"]),
            "cap": sim.r1(m["cap"]),
            "deficit": sim.r1(m["deficit"]),
            "battery": sim.r1((twin["energy"] or {}).get("battery", s["battery"]["pct"])),
            "kwh": s["battery"]["kwh"],
            "fuel": fuel,
        },
        "breakdown": [
            {"name": "Base load", "value": sim.r1(m["base"])},
            {"name": "Heating", "value": sim.r1(m["heat"])},
            {"name": "Water", "value": sim.r1(m["water"])},
            {"name": "Laboratories", "value": sim.r1(m["lab"])},
            {"name": "Communications", "value": sim.r1(m["comms"])},
            {"name": "Lighting", "value": sim.r1(m["lighting"])},
            {"name": "Other", "value": sim.r1(m["other"])},
        ],
        "chain": sim.chain_info(s),
        "energyStatus": m["energyStatus"], "energyHealth": health,
        "peakDemand": max(demands + [m["demand"]]),
        "averageDemand": sum(demands) / len(demands) if demands else m["demand"],
        "generatorSummary": m["dispatch"],
        "batterySummary": {"soc": s["battery"]["pct"], "chargeRateKw": s["battery"].get("charge_rate_kw", 0),
                            "dischargeRateKw": s["battery"].get("discharge_rate_kw", 0)},
        "fuelAutonomy": {"days": sim.r1(fuel_days), "rateLPerDay": sim.r1(m["fuelRate"]), "sourceType": "DERIVED"},
    }


# ---------------------------------------------------------------------------
# GET /api/stations/:id/logistics
# ---------------------------------------------------------------------------
@router.get("/{station_id}/logistics")
async def get_logistics(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    twin_service = DigitalTwinService(db)
    s = twin_service.calculation_state(station_id)
    if not s:
        raise HTTPException(status_code=404, detail="Unknown station")
    logistics = LogisticsService(db).state(station_id, s)
    return {
        "items": logistics["resources"], "logistics": logistics,
        "resupply": logistics["resupply"],
    }


# ---------------------------------------------------------------------------
# POST /api/stations/:id/inventory
# ---------------------------------------------------------------------------
@router.post("/{station_id}/inventory")
async def update_inventory(
    station_id: str,
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="Unknown station")
    k = body.get("k")
    stock_raw = body.get("stock")

    if k is None or stock_raw is None:
        raise HTTPException(status_code=400, detail="Bad input: k and stock required")

    try:
        v = float(stock_raw)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Bad input: stock must be a number")

    if v < 0:
        raise HTTPException(status_code=400, detail="Bad input: stock cannot be negative")

    inv_item = db.query(InventoryItem).filter(InventoryItem.station_id == station_id,
                                              InventoryItem.item_key == k).first()
    if not inv_item:
        raise HTTPException(status_code=400, detail=f"Bad input: unknown inventory key '{k}'")

    v = min(v, inv_item.capacity)
    log_action(
        db,
        f"Updated {inv_item.name} stock at {station.name} to {v}",
        user=user,
        entity_type="inventory",
        entity_id=f"{station_id}:{k}",
    )
    record_inventory_change(db, inv_item, v, body.get("reason", "ADJUSTMENT"), user.name,
                            body.get("transactionType", "ADJUSTMENT"))
    return {"ok": True, "items": inventory_output(db, DigitalTwinService(db).calculation_state(station_id))}


# ---------------------------------------------------------------------------
# GET /api/stations/:id/environment
# ---------------------------------------------------------------------------
@router.get("/{station_id}/environment")
async def get_environment(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    twin_service = DigitalTwinService(db)
    twin = twin_service.state(station_id)
    if not twin:
        raise HTTPException(status_code=404, detail="Unknown station")
    s = twin_service.calculation_state(station_id)
    e = twin["environment"]
    if twin and twin["environment"]:
        e = twin["environment"]
    m = calculate_energy(s)
    imp: list[str] = []

    if e["temp"] < -25:
        imp.append(
            f"Extreme cold ({sim.r1(e['temp'])} °C) → heating demand rises → "
            f"energy consumption and fuel burn increase."
        )
    else:
        imp.append(f"Temperature {sim.r1(e['temp'])} °C → heating load is {sim.r1(m['heat'])} kW.")

    if e["wind"] > 15:
        imp.append(
            f"Strong wind ({sim.r1(e['wind'])} m/s) → comms link degrades and snow drifts around modules."
        )
    if e["vis"] < 3:
        imp.append("Low visibility → restrict outdoor travel.")
    if e["pressure"] < 965:
        imp.append("Falling pressure → storm may be approaching.")

    return {"now": e, "history": environment_history(db, station_id), "implications": imp,
            "sourceType": e.get("sourceType", "SIMULATED"), "sourceName": e.get("sourceName"),
            "sourceTimestamp": e.get("sourceTimestamp"), "dataAge": e.get("dataAge"),
            "providerStatus": e.get("providerStatus", "UNAVAILABLE")}


# ---------------------------------------------------------------------------
# GET /api/stations/:id/alerts
# ---------------------------------------------------------------------------
@router.get("/{station_id}/alerts")
async def get_alerts(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alerts = db.query(Alert).filter(Alert.station_id == station_id, Alert.status == "ACTIVE").order_by(Alert.severity).all()
    return {"alerts": [alert_output(alert) for alert in alerts]}


# ---------------------------------------------------------------------------
# GET /api/stations/:id/maintenance
# ---------------------------------------------------------------------------
@router.get("/{station_id}/maintenance")
async def get_maintenance(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    twin = DigitalTwinService(db).state(station_id)
    if not twin:
        raise HTTPException(status_code=404, detail="Unknown station")
    return {
        "tasks": [{"id": t.id, "assetId": t.asset_id, "title": t.title, "status": "Done" if t.status == "Completed" else t.status,
               "due": t.due_date, "parts": t.parts, "by": t.created_by} for t in
              db.query(MaintenanceTask).filter(MaintenanceTask.station_id == station_id).order_by(MaintenanceTask.id).all()],
        "assets": [
            {
                "id": a["id"],
                "name": a["name"],
                "type": a["type"],
                "status": a["status"],
                "hours": a["hours"],
                "last": a["last"],
                "next": a["next"],
            }
            for a in twin["assets"]
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/stations/:id/predictions
# ---------------------------------------------------------------------------
@router.get("/{station_id}/predictions")
async def get_predictions(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = PredictionService(db).forecast(station_id)
    if not result:
        raise HTTPException(status_code=404, detail="Unknown station")
    return result


@api_router.post("/stations/{station_id}/simulation/control")
async def simulation_control(station_id: str, body: dict,
                              user: User = Depends(require_role("admin", "ops")),
                              db: Session = Depends(get_db)):
    allowed = {"temperatureOffset", "windSpeed", "waterPlantAvailability", "occupancy", "operatingLoadFactor", "delayDays", "generatorFailures"}
    controls = {key: value for key, value in body.items() if key in allowed}
    try:
        for key, value in controls.items():
            if key == "generatorFailures":
                if not isinstance(value, list) or not all(item in {"gen1", "gen2", "gen3"} for item in value):
                    raise ValueError("generatorFailures must contain only gen1, gen2, or gen3")
                continue
            low, high = SCENARIO_LIMITS[key]
            if not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f"{key} must be between {low} and {high}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"stationId": station_id, "temporary": True, "controls": set_controls(station_id, controls)}


@api_router.post("/stations/{station_id}/simulation/reset")
async def simulation_reset(station_id: str, user: User = Depends(require_role("admin", "ops"))):
    return {"stationId": station_id, "temporary": True, "controls": reset_controls(station_id), "reset": True}


@api_router.post("/simulations")
async def run_simulation(body: dict, user: User = Depends(require_role("admin", "ops")), db: Session = Depends(get_db)):
    station_id = body.get("stationId")
    if not station_id:
        raise HTTPException(status_code=400, detail="stationId is required")
    scenario = body.get("scenario", "GENERATOR_FAILURE")
    value = body.get("value")
    inputs = {"assetId": body.get("assetId", "gen2")}
    mapping = {"temp_drop": "temperatureOffset", "demand_increase": "operatingLoadFactor", "delayed_resupply": "delayDays"}
    if scenario in mapping and value is not None:
        inputs[mapping[scenario]] = -float(value) if scenario == "temp_drop" else (1 + float(value) / 100 if scenario == "demand_increase" else float(value))
    try:
        result = ScenarioService(db).run(station_id, scenario, inputs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Unknown station")
    return result


@api_router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.alert_key == alert_id, Alert.status == "ACTIVE").first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acked = True
    alert.acked_by = user.name
    alert.acked_at = datetime.utcnow()
    db.commit()
    log_action(db, f"Acknowledged alert {alert_id}", user=user, entity_type="alert", entity_id=alert_id)
    return {"ok": True, "alert": alert_output(alert)}


@api_router.post("/maintenance")
async def create_maintenance(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    station_id = body.get("stationId")
    title = body.get("title")
    if not station_id or not title:
        raise HTTPException(status_code=400, detail="stationId and title are required")
    if not db.query(Asset).filter(Asset.station_id == station_id, Asset.asset_key == body.get("assetId")).first():
        raise HTTPException(status_code=400, detail="Unknown asset for station")
    task = MaintenanceTask(station_id=station_id, asset_id=body.get("assetId"), title=title,
                            due_date=body.get("due"), parts=body.get("parts"), created_by=user.name)
    db.add(task)
    db.commit()
    return {"ok": True, "id": task.id}


@api_router.post("/maintenance/{task_id}/complete")
async def complete_maintenance(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Maintenance task not found")
    task.status = "Completed"
    task.completed_at = datetime.utcnow()
    db.commit()
    part_transaction = None
    if task.parts and task.parts != "-":
        part_transaction = LogisticsService(db).consume_resource(
            task.station_id, "parts", 1, "MAINTENANCE_USE",
            f"Maintenance task {task.id}: {task.parts}", user.name
        )
    log_action(db, f"Completed maintenance task {task_id}", user=user, entity_type="maintenance", entity_id=str(task_id))
    return {"ok": True, "partConsumed": bool(part_transaction),
            "partAvailable": part_transaction is not None}


@api_router.get("/environment/provider-status")
async def environment_provider_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    status = db.query(EnvironmentProviderStatus).filter_by(provider="NCPOR").first()
    if not status:
        return {"provider": "NCPOR", "status": "UNAVAILABLE", "lastSuccessfulFetch": None,
                "lastSourceTimestamp": None, "lastError": None}
    return {"provider": status.provider, "status": status.status,
            "lastSuccessfulFetch": status.last_successful_fetch.isoformat() if status.last_successful_fetch else None,
            "lastSourceTimestamp": status.last_source_timestamp.isoformat() if status.last_source_timestamp else None,
            "lastError": status.last_error}


@api_router.post("/environment/ingest")
async def ingest_public_environment(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.PUBLIC_ENVIRONMENT_ENABLED or not settings.PUBLIC_ENVIRONMENT_URL:
        raise HTTPException(status_code=503, detail="Official NCPOR public environment source is not configured")
    provider = PublicEnvironmentProvider(settings.PUBLIC_ENVIRONMENT_URL, settings.PUBLIC_ENVIRONMENT_TIMEOUT_SECONDS)
    ingestion = PublicDataIngestionService(db)
    try:
        observations = await __import__("asyncio").to_thread(provider.fetch)
        return {"inserted": ingestion.ingest(observations), "sourceType": "PUBLIC", "provider": provider.name}
    except Exception as error:
        ingestion.record_failure(error)
        raise HTTPException(status_code=502, detail="Public NCPOR environment ingestion failed") from error
