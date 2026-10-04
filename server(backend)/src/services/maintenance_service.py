"""Maintenance domain service: priority, readiness, parts, and atomic completion."""
from datetime import datetime, timedelta

from src.db.models import Asset, AssetReading, InventoryItem, InventoryTransaction, MaintenanceTask
from src.services.asset_health_service import asset_criticality, calculate_asset_health


def normalize_parts(task: MaintenanceTask) -> list[dict]:
    if task.required_parts:
        return task.required_parts
    if task.parts and task.parts != "-":
        return [{"partName": task.parts, "quantity": 1}]
    return []


class MaintenanceService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _is_generic_parts_name(part_name: str) -> bool:
        return part_name in {"parts", "spare parts", "bearing kit"}

    def _find_part(self, task: MaintenanceTask, part_name: str):
        query = self.db.query(InventoryItem).filter(InventoryItem.station_id == task.station_id)
        if self._is_generic_parts_name(part_name):
            return query.filter(InventoryItem.item_key == "parts").first()
        return query.filter(InventoryItem.name.ilike(f"%{part_name}%")).first()

    def readiness(self, task: MaintenanceTask) -> str:
        parts = normalize_parts(task)
        if not parts:
            return "READY"
        partial = False
        for requirement in parts:
            quantity = float(requirement.get("quantity", 1))
            part_name = str(requirement.get("partName", "")).lower()
            item = self._find_part(task, part_name)
            available = item.stock if item else 0
            if available < quantity:
                if available > 0:
                    partial = True
                else:
                    return "NOT_READY"
        return "PARTIALLY_READY" if partial else "READY"

    def asset_context(self, task: MaintenanceTask) -> dict:
        asset = self.db.query(Asset).filter(Asset.station_id == task.station_id, Asset.asset_key == task.asset_id).first()
        if not asset:
            return {"criticality": "MEDIUM", "status": "normal", "healthTrend": "STABLE"}
        readings = self.db.query(AssetReading).filter(AssetReading.asset_id == asset.id).order_by(AssetReading.timestamp.desc()).limit(30).all()
        return calculate_asset_health(asset, readings)

    def priority(self, task: MaintenanceTask) -> str:
        context = self.asset_context(task)
        criticality = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(context["criticality"], 2)
        status = {"critical": 3, "offline": 3, "warning": 2, "normal": 0}.get(context["status"], 0)
        score = criticality + status + (1 if context.get("healthTrend") == "INCREASING" else 0)
        if score >= 7:
            return "CRITICAL"
        if score >= 5:
            return "HIGH"
        if score >= 3:
            return "MEDIUM"
        return "LOW"

    def maintenance_state(self, task: MaintenanceTask) -> str:
        if task.status in {"Completed", "Done"}:
            return "COMPLETED"
        if not task.due_date:
            return "NOT_DUE"
        try:
            due = datetime.strptime(task.due_date, "%Y-%m-%d").date()
        except ValueError:
            return "NOT_DUE"
        today = datetime.utcnow().date()
        if due < today:
            return "OVERDUE"
        if (due - today).days <= 7:
            return "DUE"
        return "UPCOMING"

    def task_output(self, task: MaintenanceTask) -> dict:
        readiness = self.readiness(task)
        priority = self.priority(task)
        state = self.maintenance_state(task)
        task.readiness, task.priority, task.maintenance_state = readiness, priority, state
        return {"id": task.id, "assetId": task.asset_id, "title": task.title,
                "status": "Done" if task.status == "Completed" else task.status,
                "due": task.due_date, "parts": task.parts, "requiredParts": normalize_parts(task),
                "priority": priority, "maintenanceState": state, "readiness": readiness,
                "by": task.created_by}

    def create_task(self, station_id: str, asset_id: str, title: str, due_date: str | None,
                    parts: str | None, required_parts: list[dict] | None, user_name: str) -> MaintenanceTask:
        normalized = required_parts or ([{"partName": parts, "quantity": 1}] if parts and parts != "-" else [])
        for part in normalized:
            if not part.get("partName") or float(part.get("quantity", 0)) <= 0:
                raise ValueError("requiredParts must contain positive quantities and partName")
        task = MaintenanceTask(station_id=station_id, asset_id=asset_id, title=title,
                               due_date=due_date, parts=parts, required_parts=normalized,
                               created_by=user_name)
        self.db.add(task)
        self.db.flush()
        self.task_output(task)
        self.db.commit()
        return task

    def complete_task(self, task_id: int, user_name: str) -> dict:
        task = self.db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
        if not task:
            raise ValueError("Maintenance task not found")
        if task.status == "Completed":
            return self.task_output(task)
        allocations = []
        for requirement in normalize_parts(task):
            quantity = float(requirement.get("quantity", 1))
            part_name = str(requirement.get("partName", "")).lower()
            item = self._find_part(task, part_name)
            if not item or item.stock < quantity:
                raise ValueError(f"Required part unavailable: {requirement.get('partName')}")
            allocations.append((item, quantity, requirement.get("partName")))
        for item, quantity, part_name in allocations:
            previous = item.stock
            item.stock -= quantity
            self.db.add(InventoryTransaction(item_id=item.id, station_id=task.station_id,
                previous_quantity=previous, quantity_change=-quantity, resulting_quantity=item.stock,
                transaction_type="MAINTENANCE_USE", reason=f"Task {task.id}: {part_name}",
                user_name=user_name, source_type="SIMULATED"))
        task.status = "Completed"
        task.completed_at = datetime.utcnow()
        task.maintenance_state = "COMPLETED"
        task.readiness = "READY"
        asset = self.db.query(Asset).filter(Asset.station_id == task.station_id, Asset.asset_key == task.asset_id).first()
        if asset:
            asset.last_service_date = datetime.utcnow().strftime("%Y-%m-%d")
            asset.next_service_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
        self.db.commit()
        return self.task_output(task)
