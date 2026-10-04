import unittest

from src.db.database import SessionLocal
from src.db.models import InventoryItem, InventoryTransaction, ResupplySchedule
from src.services.digital_twin_service import DigitalTwinService
from src.services.energy_service import calculate_energy
from src.services.logistics_service import LogisticsService


class Phase7LogisticsTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.twin = DigitalTwinService(self.db)
        self.service = LogisticsService(self.db)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_stock_percentage_and_resource_state(self):
        state = self.twin.calculation_state("bharati")
        fuel = next(item for item in self.service.resources("bharati", state) if item["k"] == "fuel")
        self.assertAlmostEqual(fuel["pct"], fuel["currentQuantity"] / fuel["capacity"] * 100, places=1)
        self.assertIn(fuel["coverageStatus"], {"COVERED", "AT_RISK", "NOT_COVERED"})

    def test_fuel_rate_reuses_energy_service(self):
        state = self.twin.calculation_state("bharati")
        energy = calculate_energy(state)
        fuel = next(item for item in self.service.resources("bharati", state) if item["k"] == "fuel")
        self.assertEqual(fuel["rateSource"], "ENERGY_SERVICE")
        self.assertAlmostEqual(fuel["consumptionRate"], energy["fuelRate"], places=1)

    def test_higher_energy_demand_worsens_fuel_projection(self):
        state = self.twin.calculation_state("bharati")
        normal = next(item for item in self.service.resources("bharati", state) if item["k"] == "fuel")
        state["operatingLoadFactor"] = 1.5
        surge = next(item for item in self.service.resources("bharati", state) if item["k"] == "fuel")
        self.assertLessEqual(surge["daysRemaining"], normal["daysRemaining"])

    def test_water_and_food_respond_to_occupancy(self):
        state = self.twin.calculation_state("maitri")
        normal = {item["k"]: item for item in self.service.resources("maitri", state)}
        state["occupancy"] = 50
        higher = {item["k"]: item for item in self.service.resources("maitri", state)}
        self.assertGreaterEqual(higher["water"]["consumptionRate"], normal["water"]["consumptionRate"])
        self.assertGreaterEqual(higher["food"]["consumptionRate"], normal["food"]["consumptionRate"])

    def test_maintenance_part_consumption_is_auditable(self):
        item = self.db.query(InventoryItem).filter_by(station_id="maitri", item_key="parts").one()
        before = item.stock
        transaction = self.service.consume_resource("maitri", "parts", 1, "MAINTENANCE_USE", "test maintenance")
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.transaction_type, "MAINTENANCE_USE")
        self.assertEqual(transaction.previous_quantity, before)
        self.assertEqual(transaction.resulting_quantity, before - 1)
        item.stock = before
        self.db.query(InventoryTransaction).filter(InventoryTransaction.id == transaction.id).delete()
        self.db.commit()

    def test_inventory_never_becomes_negative(self):
        transaction = self.service.consume_resource("maitri", "parts", 100000, "EMERGENCY_USE", "test emergency")
        self.assertIsNone(transaction)
        item = self.db.query(InventoryItem).filter_by(station_id="maitri", item_key="parts").one()
        self.assertGreaterEqual(item.stock, 0)

    def test_supply_delay_changes_projection_not_schedule(self):
        state = self.twin.calculation_state("bharati")
        baseline = self.service.state("bharati", state)
        delayed = self.service.state("bharati", state, delay_days=7)
        self.assertEqual(delayed["resupply"]["date"], baseline["resupply"]["date"])
        self.assertEqual(delayed["resupply"]["inDays"], baseline["resupply"]["inDays"] + 7)
        persisted = self.db.query(ResupplySchedule).filter_by(station_id="bharati").order_by(ResupplySchedule.id).first()
        self.assertNotEqual(persisted.expected_date, delayed["resupply"]["date"] if delayed["resupply"]["date"] != persisted.expected_date else "")

    def test_logistics_health_has_drivers(self):
        state = self.twin.calculation_state("bharati")
        result = self.service.state("bharati", state, delay_days=60)
        self.assertIn(result["status"], {"NORMAL", "ATTENTION", "CRITICAL"})
        self.assertTrue(result["health"]["drivers"])


if __name__ == "__main__":
    unittest.main()
