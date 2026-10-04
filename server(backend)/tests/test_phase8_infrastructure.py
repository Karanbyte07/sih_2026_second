import unittest
from types import SimpleNamespace

from src.db.database import SessionLocal
from src.db.models import InventoryItem, InventoryTransaction, MaintenanceTask
from src.services.asset_health_service import calculate_asset_health
from src.services.digital_twin_service import DigitalTwinService
from src.services.maintenance_service import MaintenanceService


class Phase8InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.maintenance = MaintenanceService(self.db)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_generator_trend_reduces_health(self):
        asset = SimpleNamespace(type="generator", online=True, criticality="CRITICAL")
        readings = [SimpleNamespace(metric="Vibration", value=value) for value in [4.1, 4.4, 4.8, 5.2, 5.6]]
        health = calculate_asset_health(asset, readings)
        self.assertEqual(health["status"], "warning")
        self.assertEqual(health["healthTrend"], "INCREASING")
        self.assertIn("vibration trend is increasing", health["healthDrivers"])

    def test_offline_critical_asset_is_critical(self):
        asset = SimpleNamespace(type="generator", online=False, criticality="CRITICAL")
        health = calculate_asset_health(asset, [])
        self.assertEqual(health["status"], "offline")
        self.assertEqual(health["healthScore"], 0)

    def test_maintenance_priority_and_readiness_are_derived(self):
        task = self.db.query(MaintenanceTask).filter(MaintenanceTask.station_id == "bharati").first()
        output = self.maintenance.task_output(task)
        self.assertIn(output["priority"], {"LOW", "MEDIUM", "HIGH", "CRITICAL"})
        self.assertIn(output["readiness"], {"READY", "PARTIALLY_READY", "NOT_READY"})

    def test_exact_required_part_quantity_is_consumed(self):
        item = self.db.query(InventoryItem).filter_by(station_id="maitri", item_key="parts").one()
        before = item.stock
        task = self.maintenance.create_task("maitri", "gen1", "Exact parts test", None, None,
                                             [{"partName": "Bearing kit", "quantity": 2}], "test")
        result = self.maintenance.complete_task(task.id, "test")
        item = self.db.query(InventoryItem).filter_by(station_id="maitri", item_key="parts").one()
        self.assertEqual(item.stock, before - 2)
        self.assertEqual(result["status"], "Done")
        transaction = self.db.query(InventoryTransaction).filter(
            InventoryTransaction.reason == f"Task {task.id}: Bearing kit"
        ).one()
        self.assertEqual(transaction.quantity_change, -2)
        item.stock = before
        self.db.query(InventoryTransaction).filter(InventoryTransaction.id == transaction.id).delete()
        self.db.query(MaintenanceTask).filter(MaintenanceTask.id == task.id).delete()
        self.db.commit()

    def test_insufficient_parts_prevent_completion(self):
        task = self.maintenance.create_task("maitri", "gen1", "Unavailable parts test", None, None,
                                             [{"partName": "Unavailable component", "quantity": 1}], "test")
        with self.assertRaises(ValueError):
            self.maintenance.complete_task(task.id, "test")
        self.db.refresh(task)
        self.assertNotEqual(task.status, "Completed")
        self.db.delete(task)
        self.db.commit()

    def test_digital_twin_exposes_infrastructure_health(self):
        state = DigitalTwinService(self.db).state("bharati")
        self.assertIn(state["infrastructure"]["status"], {"NORMAL", "ATTENTION", "CRITICAL"})
        self.assertIn("maintenanceSummary", state["infrastructure"])
        self.assertTrue(state["assets"])
        self.assertIn("criticality", state["assets"][0])


if __name__ == "__main__":
    unittest.main()
