"""Database-backed logistics and resource Digital Twin calculations."""
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import InventoryItem, InventoryTransaction, ResupplySchedule
from src.services.energy_service import calculate_energy
from src.services.inventory_service import consumption_rates


class LogisticsService:
    def __init__(self, db: Session, lookback_days: int = 3):
        self.db = db
        self.lookback_days = lookback_days

    def _resupply(self, station_id: str) -> tuple[int, str | None]:
        row = self.db.query(ResupplySchedule).filter(
            ResupplySchedule.station_id == station_id,
            ResupplySchedule.status.notin_(["ARRIVED", "CANCELLED"]),
        ).order_by(ResupplySchedule.expected_date.asc()).first()
        if not row:
            return 999, None
        try:
            days = max(0, (datetime.strptime(row.expected_date, "%Y-%m-%d") - datetime.utcnow()).days)
        except ValueError:
            days = 999
        return days, row.expected_date

    def _recent_rate(self, item: InventoryItem) -> tuple[float, str]:
        since = datetime.utcnow() - timedelta(days=self.lookback_days)
        consumed = self.db.query(func.coalesce(func.sum(-InventoryTransaction.quantity_change), 0.0)).filter(
            InventoryTransaction.item_id == item.id,
            InventoryTransaction.timestamp >= since,
            InventoryTransaction.quantity_change < 0,
            InventoryTransaction.transaction_type.in_(["CONSUMPTION", "MAINTENANCE_USE", "EMERGENCY_USE"]),
        ).scalar() or 0.0
        if consumed > 0:
            return float(consumed) / self.lookback_days, "HISTORICAL"
        return max(0.0, item.daily_rate), "CONFIGURED_FALLBACK"

    def _rates(self, station: dict) -> dict[str, tuple[float, str]]:
        energy = calculate_energy(station)
        rates = consumption_rates(station, energy)
        return {key: (value, "ENERGY_SERVICE" if key == "fuel" else "OPERATIONAL_MODEL") for key, value in rates.items()}

    def resources(self, station_id: str, station: dict, delay_days: int = 0) -> list[dict]:
        days_to_resupply, resupply_date = self._resupply(station_id)
        days_to_resupply += max(0, delay_days)
        rates = self._rates(station)
        results = []
        for item in self.db.query(InventoryItem).filter(InventoryItem.station_id == station_id).order_by(InventoryItem.id).all():
            configured_rate, rate_source = rates.get(item.item_key, (item.daily_rate, "CONFIGURED_FALLBACK"))
            historical_rate, historical_source = self._recent_rate(item)
            rate = max(configured_rate, historical_rate) if configured_rate else historical_rate
            if item.item_key in {"fuel", "water", "food"}:
                rate_source = configured_rate and rate_source or historical_source
            days = item.stock / rate if rate > 0 else 999.0
            safety_quantity = item.capacity * item.min_pct / 100
            critical_quantity = safety_quantity * 0.5
            if days < 7 or item.stock <= critical_quantity:
                status = "CRITICAL"
            elif days < days_to_resupply or item.stock <= safety_quantity:
                status = "WARNING"
            else:
                status = "NORMAL"
            coverage = "NOT_COVERED" if days < days_to_resupply else "AT_RISK" if days < days_to_resupply + 7 else "COVERED"
            results.append({
                "k": item.item_key, "name": item.name, "unit": item.unit,
                "stock": round(item.stock), "currentQuantity": item.stock, "cap": item.capacity,
                "capacity": item.capacity, "pct": round(item.stock / item.capacity * 100, 1) if item.capacity else 0,
                "rate": round(rate, 2), "consumptionRate": round(rate, 2), "rateSource": rate_source,
                "daysLeft": round(days, 1), "daysRemaining": round(days, 1),
                "min": item.min_pct, "safetyThreshold": safety_quantity, "criticalThreshold": critical_quantity,
                "belowMin": item.stock <= safety_quantity, "risk": status.lower(), "resourceStatus": status,
                "coverageStatus": coverage, "resupplyDate": resupply_date,
                "daysUntilResupply": days_to_resupply, "sourceType": "SIMULATED",
            })
        return results

    def health(self, resources: list[dict], weather_severity: str = "normal") -> dict:
        drivers = []
        score = 100
        for resource in resources:
            if resource["coverageStatus"] == "NOT_COVERED":
                score -= 20
                drivers.append(f"{resource['name']} may deplete before resupply")
            elif resource["coverageStatus"] == "AT_RISK":
                score -= 10
                drivers.append(f"{resource['name']} has limited resupply coverage")
        if weather_severity == "warning":
            score -= 8
            drivers.append("weather severity increases transport review risk")
        elif weather_severity == "critical":
            score -= 15
            drivers.append("severe weather increases transport review risk")
        score = max(0, score)
        status = "CRITICAL" if score < 50 else "ATTENTION" if score < 80 else "NORMAL"
        return {"score": score, "status": status, "drivers": drivers or ["resources are covered by current projections"], "sourceType": "DERIVED"}

    def state(self, station_id: str, station: dict, delay_days: int = 0, weather_severity: str = "normal") -> dict:
        resources = self.resources(station_id, station, delay_days)
        days, date = self._resupply(station_id)
        days += max(0, delay_days)
        schedules = self.db.query(ResupplySchedule).filter(ResupplySchedule.station_id == station_id).order_by(ResupplySchedule.expected_date).all()
        return {"health": self.health(resources, weather_severity), "status": self.health(resources, weather_severity)["status"],
                "resources": resources, "resupply": {"inDays": days, "date": date,
                "schedule": [{"date": row.expected_date, "cargo": row.cargo_description, "status": row.status.title(),
                               "sourceType": row.source_type} for row in schedules]},
                "temporaryDelayDays": delay_days, "sourceType": "DERIVED"}

    def consume_resource(self, station_id: str, key: str, quantity: float, transaction_type: str, reason: str, user_name: str = "system") -> InventoryTransaction | None:
        item = self.db.query(InventoryItem).filter(InventoryItem.station_id == station_id, InventoryItem.item_key == key).first()
        if not item or quantity <= 0 or item.stock < quantity:
            return None
        previous = item.stock
        item.stock = max(0.0, item.stock - quantity)
        transaction = InventoryTransaction(item_id=item.id, station_id=station_id,
            previous_quantity=previous, quantity_change=item.stock - previous,
            resulting_quantity=item.stock, transaction_type=transaction_type,
            reason=reason, user_name=user_name, source_type="SIMULATED")
        self.db.add(transaction)
        self.db.commit()
        return transaction
