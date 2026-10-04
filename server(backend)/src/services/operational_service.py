"""Persistence and response mapping for simulated operational observations."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.db.models import (
    Alert,
    Asset,
    AssetReading,
    EnergySnapshot,
    EnvironmentReading,
    InventoryItem,
    InventoryTransaction,
    MaintenanceTask,
    ResupplySchedule,
    PublicEnvironmentObservation,
)
import src.utils.simulation as sim


def _now() -> datetime:
    return datetime.utcnow()


def persist_station_snapshot(db: Session, station: dict, observed_at: datetime | None = None) -> None:
    """Write the current simulator state as a durable operational observation."""
    observed_at = observed_at or _now()
    metrics = sim.calc(station)
    battery = station["battery"]
    db.add(EnergySnapshot(
        station_id=station["id"], timestamp=observed_at,
        generation_kw=sim.r1(metrics["output"]), demand_kw=sim.r1(metrics["demand"]),
        capacity_kw=sim.r1(metrics["cap"]), battery_pct=sim.r1(battery["pct"]),
        fuel_consumption_l=sim.r1(metrics["fuelRate"] / 24),
        generator_load_pct=sim.r1(metrics["genOut"] / metrics["capGen"] * 100) if metrics["capGen"] else 0,
        source_type="SIMULATED",
    ))
    env = station["env"]
    db.add(EnvironmentReading(
        station_id=station["id"], timestamp=observed_at,
        temperature=sim.r1(env["temp"]), wind_speed=sim.r1(env["wind"]),
        wind_direction=sim.r1(env["dir"]), pressure=sim.r1(env["pressure"]),
        snow=sim.r1(env["snow"]), visibility=sim.r1(env["vis"]),
        source_type="SIMULATED",
    ))
    assets = {asset.asset_key: asset for asset in db.query(Asset).filter(Asset.station_id == station["id"])}
    for asset_state in station["assets"]:
        asset = assets.get(asset_state["id"])
        if not asset:
            continue
        asset.operational_hours = int(asset_state["hours"])
        asset.online = asset_state["online"]
        asset.last_service_date = asset_state["last"]
        asset.next_service_date = asset_state["next"]
        for reading in asset_state.get("readings", []):
            db.add(AssetReading(
                asset_id=asset.id, timestamp=observed_at, metric=reading["k"],
                value=float(reading["v"]), unit=reading["u"], source_type="SIMULATED",
            ))
    inventory = {item.item_key: item for item in db.query(InventoryItem).filter(InventoryItem.station_id == station["id"])}
    for item_state in station["inv"]:
        item = inventory.get(item_state["k"])
        if item:
            item.stock = item_state["stock"]
    db.commit()


def load_inventory(db: Session) -> dict[tuple[str, str], float]:
    return {(item.station_id, item.item_key): item.stock for item in db.query(InventoryItem).all()}


def latest_energy(db: Session, station_id: str) -> EnergySnapshot | None:
    return db.query(EnergySnapshot).filter(EnergySnapshot.station_id == station_id).order_by(EnergySnapshot.timestamp.desc()).first()


def energy_history(db: Session, station_id: str, hours: int = 72) -> list[dict]:
    since = _now() - timedelta(hours=hours)
    rows = db.query(EnergySnapshot).filter(
        EnergySnapshot.station_id == station_id, EnergySnapshot.timestamp >= since
    ).order_by(EnergySnapshot.timestamp.asc()).all()
    return [{"t": row.timestamp.strftime("%H:%M:%S"), "gen": row.generation_kw,
             "demand": row.demand_kw, "cap": row.capacity_kw, "battery": row.battery_pct}
            for row in rows]


def environment_history(db: Session, station_id: str, hours: int = 72) -> list[dict]:
    since = _now() - timedelta(hours=hours)
    rows = db.query(EnvironmentReading).filter(
        EnvironmentReading.station_id == station_id, EnvironmentReading.timestamp >= since
    ).order_by(EnvironmentReading.timestamp.asc()).all()
    public_rows = db.query(PublicEnvironmentObservation).filter(
        PublicEnvironmentObservation.station_id == station_id,
        PublicEnvironmentObservation.timestamp >= since,
    ).order_by(PublicEnvironmentObservation.timestamp.asc()).all()
    history = [{"t": row.timestamp.strftime("%H:%M:%S"), "temp": row.temperature,
                "wind": row.wind_speed, "pressure": row.pressure, "snow": row.snow,
                "sourceType": "SIMULATED", "sourceName": "Simulation"} for row in rows]
    history.extend({"t": row.timestamp.strftime("%H:%M:%S"), "temp": row.temperature,
                    "wind": row.wind_speed, "pressure": row.pressure, "snow": row.snow,
                    "humidity": row.humidity, "sourceType": "PUBLIC", "sourceName": row.source_name}
                   for row in public_rows)
    return sorted(history, key=lambda item: item["t"])


def inventory_output(db: Session, station: dict) -> list[dict]:
    rows = db.query(InventoryItem).filter(InventoryItem.station_id == station["id"]).order_by(InventoryItem.id).all()
    result = []
    for item in rows:
        rate = sim.rate_of(station, {"k": item.item_key, "rate": item.daily_rate})
        days = item.stock / rate if rate > 0 else 999.0
        pct = item.stock / item.capacity * 100 if item.capacity else 0
        risk = sim.risk(station, days)
        result.append({"k": item.item_key, "name": item.name, "unit": item.unit,
                       "stock": round(item.stock), "cap": item.capacity, "pct": sim.r1(pct),
                       "rate": sim.r1(rate), "daysLeft": sim.r1(days), "min": item.min_pct,
                       "belowMin": pct < item.min_pct, "risk": risk})
    return result


def ensure_operational_seed(db: Session) -> None:
    """Create durable operational rows without replacing existing user data."""
    for station in ("maitri", "bharati"):
        params = sim._STATION_PARAMS[station]
        if not db.query(InventoryItem).filter(InventoryItem.station_id == station).first():
            for item in sim._make_inv(params["fuel"], params["spare"]):
                db.add(InventoryItem(station_id=station, item_key=item["k"], name=item["name"],
                                     unit=item["unit"], stock=item["stock"], capacity=item["cap"],
                                     daily_rate=item["rate"], min_pct=item["min"]))
        if not db.query(ResupplySchedule).filter(ResupplySchedule.station_id == station).first():
            db.add(ResupplySchedule(station_id=station, expected_date=sim.day(params["res"]),
                                    cargo_description="Diesel, fresh food, spare parts",
                                    status="SCHEDULED", notes="DEMO/SIMULATED schedule",
                                    source_type="SIMULATED"))
            db.add(ResupplySchedule(station_id=station, expected_date=sim.day(params["res"] + 60),
                                    cargo_description="Medical, general stores", status="SCHEDULED",
                                    notes="DEMO/SIMULATED schedule", source_type="SIMULATED"))
        if not db.query(MaintenanceTask).filter(MaintenanceTask.station_id == station).first():
            db.add(MaintenanceTask(station_id=station, asset_id="gen2",
                                   title="Vibration analysis & bearing inspection", status="Open",
                                   due_date=sim.day(3), parts="Bearing kit", created_by="system"))
            db.add(MaintenanceTask(station_id=station, asset_id="comms",
                                   title="Antenna alignment check", status="Open",
                                   due_date=sim.day(9), parts="-", created_by="system"))
    db.commit()


def record_inventory_change(db: Session, item: InventoryItem, new_stock: float, reason: str, user_name: str) -> None:
    previous = item.stock
    item.stock = new_stock
    db.add(InventoryTransaction(item_id=item.id, quantity_change=new_stock - previous,
                                resulting_quantity=new_stock, reason=reason, user_name=user_name))
    db.commit()


def sync_alerts(db: Session, station: dict) -> None:
    """Upsert currently triggered rules by stable station alert key."""
    current_alerts = sim.make_alerts(station)
    current_keys = {current["id"] for current in current_alerts}
    for stale in db.query(Alert).filter(Alert.station_id == station["id"], Alert.status == "ACTIVE").all():
        if stale.alert_key not in current_keys:
            stale.status = "RESOLVED"
            stale.resolved_at = _now()
    for current in current_alerts:
        key = current["id"]
        alert = db.query(Alert).filter(Alert.station_id == station["id"], Alert.alert_key == key,
                                       Alert.status == "ACTIVE").first()
        if not alert:
            alert = Alert(station_id=station["id"], alert_key=key, first_seen=_now(), status="ACTIVE")
            db.add(alert)
        alert.severity = current["severity"]
        alert.title = current["title"]
        alert.source = current["source"]
        alert.asset_id = current.get("assetId")
        alert.description = current["desc"]
        alert.impact = current["impact"]
        alert.action = current["action"]
        alert.why = current["why"]
    db.commit()


def alert_output(alert: Alert) -> dict:
    return {"id": alert.alert_key, "severity": alert.severity, "title": alert.title,
            "source": alert.source, "assetId": alert.asset_id, "link": f"/twin?asset={alert.asset_id}" if alert.asset_id else "/overview",
            "desc": alert.description, "impact": alert.impact, "action": alert.action,
            "why": alert.why, "time": alert.first_seen.isoformat(), "acked": alert.acked}