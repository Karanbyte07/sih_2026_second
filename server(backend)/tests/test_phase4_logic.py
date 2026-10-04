import unittest

import src.utils.simulation as simulation
from src.db.database import SessionLocal
from src.services.prediction_service import PredictionService
from src.services.scenario_service import ScenarioService
from src.services.simulation_control_service import reset_controls, set_controls


class Phase4LogicTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.scenarios = ScenarioService(self.db)

    def tearDown(self):
        reset_controls("maitri")
        self.db.close()

    def test_extreme_cold_increases_demand(self):
        result = self.scenarios.run("maitri", "EXTREME_COLD", {"temperatureOffset": -8})
        self.assertGreater(result["delta"]["demand"], 0)
        self.assertTrue(result["temporary"])

    def test_generator_failure_reduces_capacity(self):
        result = self.scenarios.run("bharati", "GENERATOR_FAILURE", {"assetId": "gen2"})
        self.assertLess(result["delta"]["capacity"], 0)
        self.assertIn("gen2", result["affectedAssets"])

    def test_demand_surge_increases_demand(self):
        result = self.scenarios.run("maitri", "ENERGY_DEMAND_SURGE", {"operatingLoadFactor": 1.25})
        self.assertGreater(result["delta"]["demand"], 0)

    def test_supply_delay_projects_resource_risk(self):
        result = self.scenarios.run("bharati", "SUPPLY_DELAY", {"delayDays": 30})
        self.assertTrue(any(item["risk"] in {"warning", "critical"} for item in result["resources"]))

    def test_water_degradation_changes_projection(self):
        normal = self.scenarios.run("maitri", "WATER_PLANT_DEGRADATION", {"waterPlantAvailability": 1.0})
        degraded = self.scenarios.run("maitri", "WATER_PLANT_DEGRADATION", {"waterPlantAvailability": 0.5})
        normal_water = next(item for item in normal["resources"] if item["key"] == "water")
        degraded_water = next(item for item in degraded["resources"] if item["key"] == "water")
        self.assertGreater(degraded_water["rate"], normal_water["rate"])

    def test_prediction_is_database_backed_and_marked_predicted(self):
        original = simulation.S
        simulation.S = {}
        try:
            result = PredictionService(self.db).forecast("maitri")
        finally:
            simulation.S = original
        self.assertEqual(result["sourceType"], "PREDICTED")
        self.assertEqual(len(result["forecast"]), 24)
        self.assertEqual(result["forecast"][0]["sourceType"], "PREDICTED")

    def test_controls_are_temporary_and_resettable(self):
        self.assertEqual(set_controls("maitri", {"occupancy": 40})["occupancy"], 40)
        self.assertEqual(reset_controls("maitri"), {})

    def test_invalid_control_is_rejected(self):
        with self.assertRaises(ValueError):
            self.scenarios.run("maitri", "EXTREME_COLD", {"temperatureOffset": -31})


if __name__ == "__main__":
    unittest.main()
