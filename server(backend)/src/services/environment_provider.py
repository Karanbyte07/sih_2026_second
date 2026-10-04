"""Normalized environment provider contracts."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class NormalizedEnvironmentObservation:
    station_id: str
    timestamp: datetime
    temperature: float | None
    wind_speed: float | None
    wind_direction: float | None
    pressure: float | None
    humidity: float | None
    visibility: float | None
    snow: float | None
    source_type: str
    source_name: str
    source_timestamp: datetime
    raw_data: dict | None = None


class EnvironmentProvider(Protocol):
    name: str

    def fetch(self) -> list[NormalizedEnvironmentObservation]:
        """Fetch and normalize observations without writing to the database."""
