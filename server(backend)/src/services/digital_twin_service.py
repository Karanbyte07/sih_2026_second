"""Database-backed current Digital Twin state assembled from latest observations."""
from datetime import datetime
from sqlalchemy.orm import Session
from src.db.database import ensure_energy_schema, ensure_logistics_schema

from src.db.models import (Alert, Asset, AssetReading, EnergySnapshot, EnvironmentReading,
                           EnvironmentProviderStatus, InventoryItem, PublicEnvironmentObservation)
from src.services.environment_service import severity
from src.services.operational_service import alert_output
from src.services.simulation_control_service import get_controls
from src.services.energy_service import station_energy_config


class DigitalTwinService:
    def __init__(self, db: Session):
        ensure_energy_schema()
        ensure_logistics_schema()
        self.db = db

    def _station(self, station_id: str):
        from src.db.models import Station
        return self.db.query(Station).filter(Station.id == station_id).first()

    def latest_environment(self, station_id: str):
        public = self.db.query(PublicEnvironmentObservation).filter(
            PublicEnvironmentObservation.station_id == station_id
        ).order_by(PublicEnvironmentObservation.timestamp.desc()).first()
        row = public or self.db.query(EnvironmentReading).filter(
            EnvironmentReading.station_id == station_id
        ).order_by(EnvironmentReading.timestamp.desc()).first()
        if not row:
            return None
        is_public = isinstance(row, PublicEnvironmentObservation)
        result = {"temp": row.temperature, "wind": row.wind_speed, "dir": row.wind_direction,
                  "pressure": row.pressure, "snow": row.snow, "vis": row.visibility,
                  "humidity": getattr(row, "humidity", None), "timestamp": row.timestamp.isoformat(),
                  "sourceType": "PUBLIC" if is_public else "SIMULATED",
                  "sourceName": row.source_name if is_public else "Simulation",
                  "sourceTimestamp": (row.source_timestamp if is_public else row.timestamp).isoformat()}
        status = self.db.query(EnvironmentProviderStatus).filter_by(provider="NCPOR").first()
        result["providerStatus"] = status.status if status else "UNAVAILABLE"
        result["dataAge"] = max(0, int((datetime.utcnow() - row.timestamp).total_seconds()))
        controls = get_controls(station_id)
        if controls and result["sourceType"] == "PUBLIC":
            baseline = result.copy()
            if "temperatureOffset" in controls:
                result["temp"] = (result["temp"] or 0) + controls["temperatureOffset"]
            if "windSpeed" in controls:
                result["wind"] = controls["windSpeed"]
            result["sourceType"] = "SIMULATED"
            result["sourceName"] = "Simulation overlay"
            result["baseline"] = baseline
        return result

    def latest_energy(self, station_id: str):
        row = self.db.query(EnergySnapshot).filter(EnergySnapshot.station_id == station_id).order_by(EnergySnapshot.timestamp.desc()).first()
        if not row:
            return None
        return {"gen": row.generation_kw, "demand": row.demand_kw, "cap": row.capacity_kw,
                "battery": row.battery_pct, "timestamp": row.timestamp.isoformat(),
            "fuelConsumption": row.fuel_consumption_l, "generatorLoadPct": row.generator_load_pct,
            "energyStatus": row.energy_status, "sourceType": row.source_type}

    def assets(self, station_id: str) -> list[dict]:
        assets = self.db.query(Asset).filter(Asset.station_id == station_id).all()
        energy_config = station_energy_config(station_id)
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
            generator_metadata = {}
            if asset.type == "generator":
                generator_metadata = {
                    "ratedCapacityKVA": energy_config["rated_capacity_kva"],
                    "ratedCapacitySourceType": energy_config["rated_source_type"],
                    "usableCapacityKW": energy_config["usable_capacity_kw"],
                    "usableCapacitySourceType": energy_config["usable_source_type"],
                    "powerFactorAssumption": energy_config["power_factor_assumption"],
                }
            output.append({"id": asset.asset_key, "name": asset.name, "type": asset.type,
                           "x": asset.x, "y": asset.y, "w": asset.w, "h": asset.h, "links": asset.links,
                           "cap": asset.capacity_kw, "online": asset.online, "hours": asset.operational_hours,
                           "last": asset.last_service_date, "next": asset.next_service_date,
                           "readings": [{"k": r.metric, "v": r.value, "u": r.unit} for r in latest_readings],
                           "hist": trend, **generator_metadata, **self._asset_health(asset, readings)})
        return output

    @staticmethod
    def _asset_health(asset, readings) -> dict:
        if not asset.online:
            return {"status": "offline", "healthScore": 0, "healthDrivers": ["asset is offline"]}
        values = {r.metric.lower(): r.value for r in readings}
        vibration = values.get("vibration", 0)
        temperature = values.get("temperature", 0)
        drivers = []
        if vibration >= 6 or temperature > 105:
            if vibration >= 6:
                drivers.append("vibration above critical threshold")
            if temperature > 105:
                drivers.append("temperature above critical threshold")
            return {"status": "critical", "healthScore": 35, "healthDrivers": drivers}
        if vibration >= 4.5 or temperature > 95:
            if vibration >= 4.5:
                drivers.append("vibration above baseline")
            if temperature > 95:
                drivers.append("elevated operating temperature")
            return {"status": "warning", "healthScore": 68, "healthDrivers": drivers}
        return {"status": "normal", "healthScore": 100, "healthDrivers": ["readings within configured range"]}

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

    def calculation_state(self, station_id: str) -> dict:
        """Build domain-service inputs from the latest persistent observations."""
        twin = self.state(station_id)
        if not twin:
            return None
        return self._calculation_state_from_twin(station_id, twin)

    def _calculation_state_from_twin(self, station_id: str, twin: dict) -> dict:
        env = twin["environment"] or {"temp": -15, "wind": 10}
        energy = twin["energy"] or {"battery": 50}
        energy_config = station_energy_config(station_id)
        generator_index = 0
        assets = []
        for asset in twin["assets"]:
            if asset["type"] == "generator":
                generator_index += 1
                usable = energy_config["usable_capacity_kw"]
                assets.append({"id": asset["id"], "type": "generator", "online": asset["online"],
                               "cap": usable, "rated_capacity_kva": energy_config["rated_capacity_kva"],
                               "usable_capacity_kw": usable, "power_factor_assumption": energy_config["power_factor_assumption"]})
            else:
                assets.append({"id": asset["id"], "type": asset["type"], "online": asset["online"], "cap": asset["cap"]})
        return {
            "id": station_id, "env": {"temp": env["temp"], "wind": env["wind"]},
            "baseLoad": 36 if station_id == "maitri" else 42,
            "resupplyIn": 24 if station_id == "maitri" else 20,
            "solar": 6 if station_id == "maitri" else 4, "capFactor": 1,
            "occupancy": 24 if station_id == "maitri" else 31, "occupancyCapacity": 50,
            "assets": assets,
            "battery": {"kwh": 400, "pct": energy.get("battery", 50)},
            "inv": [{"k": i.item_key, "stock": i.stock, "cap": i.capacity, "rate": i.daily_rate} for i in twin["inventory"]],
        }

    def logistics_state(self, station_id: str, delay_days: int = 0) -> dict:
        twin = self.state(station_id)
        if not twin:
            return None
        from src.services.logistics_service import LogisticsService
        state = self._calculation_state_from_twin(station_id, twin)
        return LogisticsService(self.db).state(station_id, state, delay_days, twin["environmentSeverity"])
