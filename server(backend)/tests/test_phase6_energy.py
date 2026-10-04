import unittest

from src.services.energy_health_service import calculate_energy_health
from src.services.energy_service import calculate_energy, dispatch_generation, station_energy_config, update_battery


class Phase6EnergyTests(unittest.TestCase):
    def station(self):
        return {
            "id": "bharati", "env": {"temp": -18, "wind": 10}, "baseLoad": 42,
            "solar": 0, "capFactor": 1, "occupancy": 31, "occupancyCapacity": 50,
            "assets": [
                {"id": "gen1", "type": "generator", "online": True, "usable_capacity_kw": 80},
                {"id": "gen2", "type": "generator", "online": True, "usable_capacity_kw": 80},
                {"id": "gen3", "type": "generator", "online": True, "usable_capacity_kw": 80},
            ], "battery": {"kwh": 400, "pct": 60},
        }

    def test_load_breakdown_sums_to_demand(self):
        station = self.station()
        energy = calculate_energy(station)
        components = sum(energy[key] for key in ("base", "heat", "water", "lab", "comms", "lighting", "other"))
        self.assertAlmostEqual(components, energy["demand"])

    def test_dispatch_never_exceeds_unit_capacity(self):
        result = dispatch_generation(500, [
            {"id": "gen1", "online": True, "usable_capacity_kw": 80},
            {"id": "gen2", "online": True, "usable_capacity_kw": 80},
        ])
        self.assertEqual(result["generation_kw"], 160)
        self.assertTrue(all(unit["output_kw"] <= unit["usable_capacity_kw"] for unit in result["units"]))

    def test_generator_failure_reduces_capacity(self):
        station = self.station()
        normal = calculate_energy(station)
        station["assets"][1]["online"] = False
        failed = calculate_energy(station)
        self.assertLess(failed["cap"], normal["cap"])

    def test_battery_is_bounded_and_has_discharge_rate(self):
        station = self.station()
        station["baseLoad"] = 500
        energy = calculate_energy(station)
        update_battery(station, energy, interval_hours=24)
        self.assertGreaterEqual(station["battery"]["pct"], 0)
        self.assertLessEqual(station["battery"]["pct"], 100)
        self.assertLessEqual(station["battery"]["discharge_rate_kw"], 20)

    def test_higher_output_increases_fuel_rate(self):
        station = self.station()
        low = calculate_energy(station)["fuelRate"]
        station["baseLoad"] = 150
        high = calculate_energy(station)["fuelRate"]
        self.assertGreater(high, low)

    def test_energy_state_and_health_are_explainable(self):
        station = self.station()
        station["baseLoad"] = 500
        energy = calculate_energy(station)
        self.assertEqual(energy["energyStatus"], "CRITICAL_DEFICIT")
        health = calculate_energy_health({**energy, "batteryPct": 10}, 5, [{"status": "offline"}])
        self.assertLess(health["score"], 80)
        self.assertTrue(health["drivers"])

    def test_station_capacity_provenance(self):
        bharati = station_energy_config("bharati")
        maitri = station_energy_config("maitri")
        self.assertEqual(bharati["rated_capacity_kva"], 100)
        self.assertEqual(bharati["rated_source_type"], "PUBLIC")
        self.assertEqual(bharati["usable_source_type"], "SIMULATED")
        self.assertIsNone(maitri["rated_capacity_kva"])


if __name__ == "__main__":
    unittest.main()
