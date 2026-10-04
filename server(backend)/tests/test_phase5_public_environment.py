import unittest
from datetime import datetime

from src.db.database import Base, SessionLocal, engine
from src.db.models import EnvironmentProviderStatus, PublicEnvironmentObservation
from src.services.environment_ingestion_service import PublicDataIngestionService
from src.services.environment_provider import NormalizedEnvironmentObservation
from src.services.public_environment_provider import PublicEnvironmentProvider, PublicProviderError
from src.services.digital_twin_service import DigitalTwinService
from src.services.simulation_control_service import reset_controls, set_controls


class Phase5PublicEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        self.timestamp = datetime(2099, 1, 2, 3, 4, 5)
        self.observation = NormalizedEnvironmentObservation(
            station_id="maitri", timestamp=self.timestamp, temperature=-18.0,
            wind_speed=5.0, wind_direction=180.0, pressure=978.0, humidity=None,
            visibility=None, snow=None, source_type="PUBLIC", source_name="NCPOR",
            source_timestamp=self.timestamp, raw_data={"fixture": True},
        )

    def tearDown(self):
        self.db.query(PublicEnvironmentObservation).filter(
            PublicEnvironmentObservation.source_timestamp == self.timestamp
        ).delete(synchronize_session=False)
        self.db.query(EnvironmentProviderStatus).filter_by(provider="NCPOR").delete()
        self.db.commit()
        self.db.close()

    def test_normalization_and_official_host_validation(self):
        provider = PublicEnvironmentProvider("https://data.ncpor.res.in/weather.json")
        row = provider._normalize({"station": "bharati", "timestamp": "2026-10-04T12:00:00Z",
                                   "temperature": 300.15, "temperatureUnit": "K",
                                   "pressure": 97810, "pressureUnit": "Pa",
                                   "windSpeed": 18, "windSpeedUnit": "km/h"})
        self.assertAlmostEqual(row.temperature, 27.0, places=1)
        self.assertAlmostEqual(row.pressure, 978.1, places=1)
        self.assertAlmostEqual(row.wind_speed, 5.0, places=1)
        self.assertEqual(row.source_type, "PUBLIC")
        with self.assertRaises(PublicProviderError):
            PublicEnvironmentProvider("https://example.com/weather.json").fetch()

    def test_missing_values_and_duplicate_protection(self):
        ingestion = PublicDataIngestionService(self.db)
        self.assertEqual(ingestion.ingest([self.observation]), 1)
        self.assertEqual(ingestion.ingest([self.observation]), 0)
        row = self.db.query(PublicEnvironmentObservation).filter_by(source_timestamp=self.timestamp).one()
        self.assertIsNone(row.humidity)
        self.assertIsNone(row.visibility)
        self.assertEqual(row.source_type, "PUBLIC")

    def test_invalid_public_value_is_rejected(self):
        ingestion = PublicDataIngestionService(self.db)
        invalid = self.observation.__class__(**{**self.observation.__dict__, "humidity": 120})
        with self.assertRaises(ValueError):
            ingestion.ingest([invalid])

    def test_provider_failure_keeps_status_explicit(self):
        ingestion = PublicDataIngestionService(self.db)
        ingestion.record_failure(RuntimeError("source unavailable"))
        status = self.db.query(EnvironmentProviderStatus).filter_by(provider="NCPOR").one()
        self.assertEqual(status.status, "UNAVAILABLE")
        self.assertIn("unavailable", status.last_error)

    def test_public_baseline_survives_simulation_overlay(self):
        PublicDataIngestionService(self.db).ingest([self.observation])
        baseline = DigitalTwinService(self.db).latest_environment("maitri")
        set_controls("maitri", {"temperatureOffset": -8})
        overlay = DigitalTwinService(self.db).latest_environment("maitri")
        self.assertEqual(baseline["sourceType"], "PUBLIC")
        self.assertEqual(overlay["sourceType"], "SIMULATED")
        self.assertEqual(overlay["baseline"]["sourceType"], "PUBLIC")
        self.assertEqual(overlay["temp"], baseline["temp"] - 8)
        reset_controls("maitri")


if __name__ == "__main__":
    unittest.main()
