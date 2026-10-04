"""Database-backed current Digital Twin state assembled from latest observations."""
from datetime import datetime
from sqlalchemy.orm import Session

from src.db.models import Alert, Asset, AssetReading, EnergySnapshot, EnvironmentReading, InventoryItem
from src.services.environment_service import severity
from src.services.operational_service import alert_output


class DigitalTwinService:
    def __init__(self, db: Session):
        self.db = db

    def _station(self, station_id: str):
        from src.db.models import Station
        return self.db.query(Station).filter(Station.id == station_id).first()

    def latest_environment(self, station_id: str):
        row = self.db.query(EnvironmentReading).filter(EnvironmentReading.station_id == station_id).order_by(EnvironmentReading.timestamp.desc()).first()
        if not row:
            return None
        return {"temp": row.temperature, "wind": row.wind_speed, "dir": row.wind_direction,
                "pressure": row.pressure, "snow": row.snow, "vis": row.visibility,
                "timestamp": row.timestamp.isoformat(), "sourceType": row.source_type}

    def latest_energy(self, station_id: str):
        row = self.db.query(EnergySnapshot).filter(EnergySnapshot.station_id == station_id).order_by(EnergySnapshot.timestamp.desc()).first()
        if not row:
            return None
        return {"gen": row.generation_kw, "demand": row.demand_kw, "cap": row.capacity_kw,
                "battery": row.battery_pct, "timestamp": row.timestamp.isoformat(),
                "sourceType": row.source_type}

    def assets(self, station_id: str) -> list[dict]:
        assets = self.db.query(Asset).filter(Asset.station_id == station_id).all()
        output = []
        for asset in assets:
            readings = self.db.query(AssetReading).filter(AssetReading.asset_id == asset.id).order_by(AssetReading.timestamp.desc()).limit(30).all()
            metric_names = []
            for reading in readings:
                if reading.metric not in metric_names:
                    metric_names.append(reading.metric)
            latest_readings = [next(reading for reading in readings if reading.metric == metric) for metric in metric_names]
            trend_metric = latest_readings[0].metric if latest_readings else None
            trend = [reading.value for reading in reversed(readings) if reading.metric == trend_metric]
            output.append({"id": asset.asset_key, "name": asset.name, "type": asset.type,
                           "x": asset.x, "y": asset.y, "w": asset.w, "h": asset.h, "links": asset.links,
                           "cap": asset.capacity_kw, "online": asset.online, "hours": asset.operational_hours,
                           "last": asset.last_service_date, "next": asset.next_service_date,
                           "readings": [{"k": r.metric, "v": r.value, "u": r.unit} for r in latest_readings],
                           "hist": trend, "status": self._asset_status(asset, readings)})
        return output

    @staticmethod
    def _asset_status(asset, readings) -> str:
        if not asset.online:
            return "offline"
        values = {r.metric.lower(): r.value for r in readings}
        vibration = values.get("vibration", 0)
        temperature = values.get("temperature", 0)
        if vibration >= 6 or temperature > 105:
            return "critical"
        if vibration >= 4.5 or temperature > 95:
            return "warning"
        return "normal"

    def state(self, station_id: str) -> dict:
        station = self._station(station_id)
        if not station:
            return None
        environment = self.latest_environment(station_id)
        energy = self.latest_energy(station_id)
        inventory = self.db.query(InventoryItem).filter(InventoryItem.station_id == station_id).all()
        alerts = self.db.query(Alert).filter(Alert.station_id == station_id, Alert.status == "ACTIVE").all()
        latest = environment or energy
        age = (datetime.utcnow() - datetime.fromisoformat(latest["timestamp"])).total_seconds() if latest else 999999
        freshness = "CONNECTED" if age < 15 else "DEGRADED" if age < 60 else "STALE"
        return {"id": station.id, "name": station.name, "environment": environment,
                "energy": energy, "assets": self.assets(station_id),
                "inventory": inventory, "alerts": [alert_output(a) for a in alerts],
                "freshness": {"status": freshness, "age": int(age)},
                "environmentSeverity": severity(environment) if environment else "unknown"}
