"""Small simulated occupancy model used by station demand calculations."""


def current_occupancy(station: dict) -> int:
    return int(station.get("occupancy", station.get("occupancyBase", 24)))


def occupancy_factor(station: dict) -> float:
    return current_occupancy(station) / max(1, int(station.get("occupancyCapacity", 50)))
