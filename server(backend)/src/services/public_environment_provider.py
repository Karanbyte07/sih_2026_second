"""Official NCPOR public environment provider.

The endpoint is configuration-driven because the public NCPOR site currently exposes
no verified machine-readable Maitri/Bharati weather endpoint in its public homepage.
Only official NCPOR hosts are accepted.
"""
import csv
import io
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.services.environment_provider import NormalizedEnvironmentObservation


class PublicProviderError(RuntimeError):
    pass


class PublicEnvironmentProvider:
    name = "NCPOR"

    def __init__(self, url: str, timeout_seconds: int = 10, opener=urlopen):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.opener = opener
        parsed = urlparse(url) if url else None
        self.allowed = bool(parsed and parsed.scheme == "https" and (parsed.hostname or "").lower().endswith("ncpor.res.in"))

    def _datetime(self, value) -> datetime:
        if not value:
            raise PublicProviderError("Observation is missing a source timestamp")
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _number(row: dict, *keys, divisor: float = 1.0):
        for key in keys:
            if row.get(key) is not None and row.get(key) != "":
                return float(row[key]) / divisor
        return None

    def _normalize(self, row: dict) -> NormalizedEnvironmentObservation:
        station = str(row.get("stationId", row.get("station", ""))).lower()
        if station not in {"maitri", "bharati"}:
            raise PublicProviderError(f"Unsupported station: {station}")
        source_time = self._datetime(row.get("sourceTimestamp", row.get("timestamp", row.get("time"))))
        temperature = self._number(row, "temperature", "temp")
        if str(row.get("temperatureUnit", "C")).upper() in {"K", "KELVIN"} and temperature is not None:
            temperature -= 273.15
        pressure = self._number(row, "pressure", "pressure_hpa")
        if str(row.get("pressureUnit", "hPa")).lower() in {"pa", "pascal", "pascals"} and pressure is not None:
            pressure /= 100
        wind_speed = self._number(row, "windSpeed", "wind_speed", "wind")
        if str(row.get("windSpeedUnit", "m/s")).lower() in {"km/h", "kmh"} and wind_speed is not None:
            wind_speed /= 3.6
        return NormalizedEnvironmentObservation(
            station_id=station, timestamp=source_time, temperature=temperature,
            wind_speed=wind_speed, wind_direction=self._number(row, "windDirection", "wind_direction"),
            pressure=pressure, humidity=self._number(row, "humidity", "relativeHumidity", "rh"),
            visibility=self._number(row, "visibility"), snow=self._number(row, "snow", "snowDepth"),
            source_type="PUBLIC", source_name=self.name, source_timestamp=source_time, raw_data=row,
        )

    def fetch(self) -> list[NormalizedEnvironmentObservation]:
        if not self.allowed:
            raise PublicProviderError("PUBLIC_ENVIRONMENT_URL must be an HTTPS official NCPOR host")
        request = Request(self.url, headers={"Accept": "application/json, text/csv"})
        with self.opener(request, timeout=self.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
        if "csv" in content_type or self.url.lower().endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(payload)))
        else:
            parsed = json.loads(payload)
            rows = parsed if isinstance(parsed, list) else parsed.get("observations", parsed.get("data", [parsed]))
        return [self._normalize(row) for row in rows]
