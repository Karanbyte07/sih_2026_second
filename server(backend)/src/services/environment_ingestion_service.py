"""Idempotent public environment ingestion and provider health tracking."""
from datetime import datetime

from sqlalchemy.orm import Session

from src.db.models import EnvironmentProviderStatus, PublicEnvironmentObservation
from src.services.environment_provider import NormalizedEnvironmentObservation


class PublicDataIngestionService:
    provider_name = "NCPOR"

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def validate(observation: NormalizedEnvironmentObservation) -> None:
        checks = {
            "temperature": observation.temperature is None or -90 <= observation.temperature <= 20,
            "humidity": observation.humidity is None or 0 <= observation.humidity <= 100,
            "wind_speed": observation.wind_speed is None or observation.wind_speed >= 0,
            "wind_direction": observation.wind_direction is None or 0 <= observation.wind_direction <= 360,
            "pressure": observation.pressure is None or observation.pressure > 0,
            "visibility": observation.visibility is None or observation.visibility >= 0,
            "snow": observation.snow is None or observation.snow >= 0,
        }
        invalid = [key for key, valid in checks.items() if not valid]
        if invalid:
            raise ValueError(f"Invalid public environment values: {', '.join(invalid)}")

    def ingest(self, observations: list[NormalizedEnvironmentObservation]) -> int:
        inserted = 0
        latest = None
        for observation in observations:
            self.validate(observation)
            duplicate = self.db.query(PublicEnvironmentObservation).filter(
                PublicEnvironmentObservation.station_id == observation.station_id,
                PublicEnvironmentObservation.source_name == observation.source_name,
                PublicEnvironmentObservation.source_timestamp == observation.source_timestamp,
            ).first()
            if duplicate:
                continue
            self.db.add(PublicEnvironmentObservation(
                station_id=observation.station_id, timestamp=observation.timestamp,
                temperature=observation.temperature, wind_speed=observation.wind_speed,
                wind_direction=observation.wind_direction, pressure=observation.pressure,
                humidity=observation.humidity, visibility=observation.visibility, snow=observation.snow,
                source_type="PUBLIC", source_name=observation.source_name,
                source_timestamp=observation.source_timestamp, ingested_at=datetime.utcnow(),
                raw_data=observation.raw_data,
            ))
            inserted += 1
            latest = observation
        status = self.db.query(EnvironmentProviderStatus).filter_by(provider=self.provider_name).first()
        if not status:
            status = EnvironmentProviderStatus(provider=self.provider_name)
            self.db.add(status)
        status.status = "CONNECTED"
        status.last_successful_fetch = datetime.utcnow()
        if latest:
            status.last_source_timestamp = latest.source_timestamp
        status.last_error = None
        self.db.commit()
        return inserted

    def record_failure(self, error: Exception) -> None:
        status = self.db.query(EnvironmentProviderStatus).filter_by(provider=self.provider_name).first()
        if not status:
            status = EnvironmentProviderStatus(provider=self.provider_name)
            self.db.add(status)
        status.status = "STALE" if status.last_successful_fetch else "UNAVAILABLE"
        status.last_error = str(error)[:500]
        status.updated_at = datetime.utcnow()
        self.db.commit()
