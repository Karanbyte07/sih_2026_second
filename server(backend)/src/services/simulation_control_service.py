"""Temporary per-station controls; never written to operational tables."""

CONTROLS: dict[str, dict] = {}


def get_controls(station_id: str) -> dict:
    return CONTROLS.get(station_id, {}).copy()


def set_controls(station_id: str, controls: dict) -> dict:
    CONTROLS[station_id] = controls.copy()
    return CONTROLS[station_id].copy()


def reset_controls(station_id: str) -> dict:
    CONTROLS.pop(station_id, None)
    return {}
