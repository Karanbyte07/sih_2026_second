import unittest

from src.services.energy_service import calculate_energy, update_battery
from src.services.inventory_service import consume
import src.utils.simulation as simulation


class Phase3LogicTests(unittest.TestCase):
    def station(self):
        return {
            "env": {"temp": -20, "wind": 10}, "baseLoad": 30, "solar": 0,
            "capFactor": 1, "occupancy": 24, "occupancyCapacity": 50,
            "assets": [{"type": "generator", "online": True, "cap": 100}],
            "battery": {"kwh": 400, "pct": 50},
            "inv": [{"k": "fuel", "stock": 1000}, {"k": "water", "stock": 1000}],
        }

    def test_cold_temperature_increases_demand(self):
        station = self.station()
        normal = calculate_energy(station)["demand"]
        station["env"]["temp"] = -35
        self.assertGreater(calculate_energy(station)["demand"], normal)

    def test_generator_output_increases_fuel_rate(self):
        station = self.station()
        low = calculate_energy(station)["fuelRate"]
        station["baseLoad"] = 80
        self.assertGreater(calculate_energy(station)["fuelRate"], low)

    def test_offline_generator_reduces_capacity(self):
        station = self.station()
        online = calculate_energy(station)["cap"]
        station["assets"][0]["online"] = False
        self.assertLess(calculate_energy(station)["cap"], online)

    def test_battery_bounds_and_discharge(self):
        station = self.station()
        station["env"]["temp"] = -48
        update_battery(station, calculate_energy(station), interval_hours=10)
        self.assertGreaterEqual(station["battery"]["pct"], 0)
        self.assertLessEqual(station["battery"]["pct"], 100)

    def test_inventory_consumption_is_operational(self):
        station = self.station()
        energy = calculate_energy(station)
        before = station["inv"][0]["stock"]
        consume(station, energy, interval_hours=1)
        self.assertLess(station["inv"][0]["stock"], before)

    def test_bharati_generator_vibration_drift_reaches_warning(self):
        simulation.init_simulation()
        generator = next(asset for asset in simulation.S["bharati"]["assets"] if asset["id"] == "gen2")
        for _ in range(80):
            simulation.tick(simulation.S["bharati"])
        self.assertGreater(generator["vib"], simulation._settings["vibWarn"])
        self.assertIn(generator["status"], {"warning", "critical"})


if __name__ == "__main__":
    unittest.main()
