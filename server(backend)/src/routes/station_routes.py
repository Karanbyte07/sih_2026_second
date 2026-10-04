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
from src.db.models import Alert, Asset, InventoryItem, MaintenanceTask, ResupplySchedule, User
from src.middleware.auth import get_current_user
from src.services.audit_service import log_action
from src.services.operational_service import (
    alert_output, energy_history, environment_history, inventory_output,
    latest_energy, record_inventory_change, sync_alerts,
)
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
async def list_stations(user: User = Depends(get_current_user)):
    age_ms = int((datetime.now() - sim.last_tick).total_seconds() * 1000)
    return {
        "ts": int(datetime.now().timestamp() * 1000),
        "age": age_ms,
        "simulated": True,
        "stations": [
            {"id": s["id"], "name": s["name"], "status": sim.station_status(s)}
            for s in sim.S.values()
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/stations/:id/overview
# ---------------------------------------------------------------------------
@router.get("/{station_id}/overview")
async def get_overview(station_id: str, user: User = Depends(get_current_user)):
    s = _get_station(station_id)
    m = sim.calc(s)
    f = s["inv"][0]
    al = sim.make_alerts(s)

    return {
        "id": s["id"],
        "name": s["name"],
        "status": sim.station_status(s),
        "kpis": {
            "gen": sim.r1(m["output"]),
            "demand": sim.r1(m["demand"]),
            "cap": sim.r1(m["cap"]),
            "fuelPct": round(f["stock"] / f["cap"] * 100),
            "fuelDays": sim.r1(sim.days_of(s, f)),
            "battery": sim.r1(s["battery"]["pct"]),
            "normal": sum(1 for a in s["assets"] if a["status"] == "normal"),
            "total": len(s["assets"]),
        },
        "env": sim.env_now(s),
        "alerts": [a for a in al if not a["acked"]][:4],
        "alertCount": {
            "critical": sum(1 for a in al if a["severity"] == "critical" and not a["acked"]),
            "warning": sum(1 for a in al if a["severity"] == "warning" and not a["acked"]),
        },
        "assets": s["assets"],
        "chain": sim.chain_info(s),
    }


# ---------------------------------------------------------------------------
# GET /api/stations/:id/assets
# ---------------------------------------------------------------------------
@router.get("/{station_id}/assets")
async def get_assets(station_id: str, user: User = Depends(get_current_user)):
    s = _get_station(station_id)
    return {"assets": s["assets"], "env": sim.env_now(s)}


# ---------------------------------------------------------------------------
# GET /api/stations/:id/energy
# ---------------------------------------------------------------------------
@router.get("/{station_id}/energy")
async def get_energy(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get_station(station_id)
    m = sim.calc(s)
    base = s["baseLoad"]
    return {
        "history": energy_history(db, station_id),
        "now": {
            "gen": sim.r1(m["output"]),
            "demand": sim.r1(m["demand"]),
            "cap": sim.r1(m["cap"]),
            "deficit": sim.r1(m["deficit"]),
            "battery": sim.r1(s["battery"]["pct"]),
            "kwh": s["battery"]["kwh"],
            "fuel": sim.inv_out(s)[0],
        },
        "breakdown": [
            {"name": "Heating",      "value": sim.r1(m["heat"])},
            {"name": "Living",       "value": sim.r1(base * 0.30)},
            {"name": "Laboratories", "value": sim.r1(base * 0.35)},
            {"name": "Water",        "value": sim.r1(base * 0.15)},
            {"name": "Comms & other","value": sim.r1(base * 0.20)},
        ],
        "chain": sim.chain_info(s),
    }


# ---------------------------------------------------------------------------
# GET /api/stations/:id/logistics
# ---------------------------------------------------------------------------
@router.get("/{station_id}/logistics")
async def get_logistics(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get_station(station_id)
    return {
        "items": inventory_output(db, s),
        "resupply": {
            "inDays": s["resupplyIn"],
            "date": sim.day(s["resupplyIn"]),
            "schedule": [{"date": row.expected_date, "cargo": row.cargo_description,
                           "status": row.status.title()} for row in db.query(ResupplySchedule)
                           .filter(ResupplySchedule.station_id == station_id)
                           .order_by(ResupplySchedule.expected_date).all()],
        },
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
    s = _get_station(station_id)
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
    next(item for item in s["inv"] if item["k"] == k)["stock"] = v

    log_action(
        db,
        f"Updated {inv_item.name} stock at {s['name']} to {v}",
        user=user,
        entity_type="inventory",
        entity_id=f"{station_id}:{k}",
    )
    record_inventory_change(db, inv_item, v, body.get("reason", "ADJUSTMENT"), user.name)
    return {"ok": True, "items": inventory_output(db, s)}


# ---------------------------------------------------------------------------
# GET /api/stations/:id/environment
# ---------------------------------------------------------------------------
@router.get("/{station_id}/environment")
async def get_environment(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get_station(station_id)
    e = s["env"]
    m = sim.calc(s)
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

    return {"now": sim.env_now(s), "history": environment_history(db, station_id), "implications": imp,
            "sourceType": "SIMULATED"}


# ---------------------------------------------------------------------------
# GET /api/stations/:id/alerts
# ---------------------------------------------------------------------------
@router.get("/{station_id}/alerts")
async def get_alerts(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get_station(station_id)
    sync_alerts(db, s)
    alerts = db.query(Alert).filter(Alert.station_id == station_id, Alert.status == "ACTIVE").order_by(Alert.severity).all()
    return {"alerts": [alert_output(alert) for alert in alerts]}


# ---------------------------------------------------------------------------
# GET /api/stations/:id/maintenance
# ---------------------------------------------------------------------------
@router.get("/{station_id}/maintenance")
async def get_maintenance(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _get_station(station_id)
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
            for a in s["assets"]
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/stations/:id/predictions
# ---------------------------------------------------------------------------
@router.get("/{station_id}/predictions")
async def get_predictions(station_id: str, user: User = Depends(get_current_user)):
    s = _get_station(station_id)
    e = s["env"]
    m = sim.calc(s)

    # 24-hour demand forecast (rule-based, same as original)
    forecast = []
    for h in range(24):
        temp = e["temp"] + 2.5 * math.sin((h - 4) / 24 * 6.283) - (
            6 * math.exp(-((h - 14) ** 2) / 30) if s["cold"] else 0
        )
        demand = sim.r1(
            s["baseLoad"]
            + max(0, -5 - temp) * 0.9
            + 10
            + (4 if 6 <= h <= 20 else 0)
        )
        forecast.append(
            {"h": f"+{h}h", "temp": sim.r1(temp), "demand": demand, "capacity": sim.r1(m["cap"])}
        )

    # Anomaly detection (rule-based)
    anomalies = []
    for a in s["assets"]:
        if a["status"] == "normal" or not a["online"]:
            continue
        r0 = a["readings"][0] if a["readings"] else None
        if not r0:
            continue
        hist = a["hist"][-10:]
        slope = (hist[-1] - hist[0]) / (len(hist) - 1) if len(hist) > 1 else 0.0
        is_gen = a["type"] == "generator"
        hrs = None
        if is_gen and slope > 0.02:
            hrs = sim.r1((sim._settings["vibCrit"] - a["vib"]) / slope * 10 / 60)

        anomalies.append(
            {
                "assetId": a["id"],
                "name": a["name"],
                "severity": a["status"],
                "metric": r0["k"],
                "value": f"{r0['v']} {r0['u']}",
                "reason": (
                    f"Vibration is {r0['v']} mm/s, "
                    f"{(r0['v'] / 2.2):.1f}× the 2.2 mm/s baseline and rising "
                    f"~{(slope * 6):.2f} mm/s per simulated hour."
                    if is_gen
                    else f"Rule-based: {r0['k']} {r0['v']} {r0['u']} is outside its normal range."
                ),
                "urgency": (
                    f"≈ {hrs} simulated hours until critical threshold at current trend"
                    if hrs and hrs > 0
                    else "Past critical threshold – inspect now"
                    if is_gen and a["vib"] > sim._settings["vibCrit"]
                    else "Inspect at next maintenance window"
                ),
                "trend": a["hist"],
            }
        )

    resources = [
        {
            "name": i["name"],
            "daysLeft": i["daysLeft"],
            "resupplyIn": s["resupplyIn"],
            "risk": i["risk"],
            "pct": i["pct"],
        }
        for i in sim.inv_out(s)
    ]

    shortage_hours = sum(1 for x in forecast if x["demand"] > x["capacity"])
    peak = max(x["demand"] for x in forecast) if forecast else 0

    return {
        "forecast": forecast,
        "shortageHours": shortage_hours,
        "peak": peak,
        "anomalies": anomalies,
        "resources": resources,
    }


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
    log_action(db, f"Completed maintenance task {task_id}", user=user, entity_type="maintenance", entity_id=str(task_id))
    return {"ok": True}
