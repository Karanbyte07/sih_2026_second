"""Simulation-only Antarctic environment provider."""
from random import random


def update_environment(station: dict) -> dict:
    """Apply gradual weather drift; values are prototype simulated observations."""
    env = station["env"]
    noise = lambda amount: (random() * 2 - 1) * amount
    env["temp"] = max(-48, min(2, env["temp"] + (station["t"] - env["temp"]) * 0.03 + noise(0.5)))
    env["wind"] = max(0, min(40, env["wind"] + (station["w"] - env["wind"]) * 0.05 + noise(1.2)))
    env["dir"] = (env["dir"] + noise(6) + 360) % 360
    env["pressure"] = max(930, min(1010, env["pressure"] + (station["p"] - env["pressure"]) * 0.02 + noise(0.8)))
    env["snow"] = max(0, min(60, env["snow"] + noise(0.4)))
    env["vis"] = max(0.3, min(10, env["vis"] + (9 - env["vis"]) * 0.05 + noise(0.6) - (0.3 if env["wind"] > 20 else 0)))
    return env


def severity(env: dict) -> str:
    if env["temp"] < -35 or env["wind"] > 28 or env["vis"] < 1.5:
        return "critical"
    if env["temp"] < -25 or env["wind"] > 20 or env["vis"] < 3:
        return "warning"
    return "normal"
