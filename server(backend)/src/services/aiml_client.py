"""
Thin HTTP client that calls the AI/ML microservice.

Every method returns a dict on success or None on failure so callers
can gracefully fall back to rule-based logic.
"""
import json
import logging
import urllib.request
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = 2  # seconds


def _get(path: str, params: dict | None = None) -> dict | None:
    url = get_settings().AIML_SERVICE_URL + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url += f"?{qs}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.debug("AI/ML GET %s failed: %s", path, exc)
        return None


def _post(path: str, body: dict) -> dict | None:
    url = get_settings().AIML_SERVICE_URL + path
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.debug("AI/ML POST %s failed: %s", path, exc)
        return None


# ── public helpers ────────────────────────────────────────────────

def ml_health() -> dict | None:
    return _get("/health")


def ml_anomaly(asset_id: str, temperature: float, vibration: float,
               load_kw: float, power_kw: float, pressure: float,
               operating_hours: float) -> dict | None:
    return _post("/ml/anomaly", {
        "assetId": asset_id,
        "temperature": temperature,
        "vibration": vibration,
        "load_kw": load_kw,
        "power_consumption_kw": power_kw,
        "pressure": pressure,
        "operating_hours": operating_hours,
    })


def ml_energy_forecast(station_id: str, temperature: float = -15.0,
                       load_kw: float = 50.0) -> dict | None:
    return _get("/ml/energy-forecast", {
        "station_id": station_id, "temperature": temperature, "load_kw": load_kw
    })


def ml_inventory_forecast(station_id: str, current_stock: float = 10000.0,
                          temperature: float = -15.0,
                          load_kw: float = 50.0) -> dict | None:
    return _get("/ml/inventory-forecast", {
        "station_id": station_id, "current_stock": current_stock,
        "temperature": temperature, "load_kw": load_kw
    })


def ml_station_health(station_id: str) -> dict | None:
    return _get(f"/ml/station-health/{station_id}")


def ml_asset_health(asset_id: str) -> dict | None:
    return _get(f"/ml/asset-health/{asset_id}")


def ml_recommendations(station_id: str) -> dict | None:
    return _get(f"/ml/recommendations/{station_id}")


def ml_simulate(station_id: str, scenario: str, value=None) -> dict | None:
    return _post("/ml/simulate", {
        "stationId": station_id, "scenario": scenario, "value": value
    })
