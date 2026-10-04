"""
Simulation engine — Phase 1 (in-memory, compatible with original JS logic).

This module is a faithful Python port of the original server(backend)/index.js
simulation. It keeps:
  - tick()         environmental drift + asset health update (runs every 3 s)
  - calc()         energy balance derivation
  - make_alerts()  rule-based alert generation
  - inv_out()      inventory serialisation for the frontend
  - snap()         snapshot for before/after simulation comparisons
  - chain_info()   cause-effect chain data
  - env_now()      current environment reading dict

Global state
------------
S              : dict[str, station_dict] — keyed by station ID
_settings      : dict — shared threshold configuration (loaded from DB on startup)
last_tick      : datetime — timestamp of the most recent tick

Phase 2 will replace this module with real sensor ingestion.
"""

import asyncio
import copy
import math
import random
from datetime import datetime, timedelta
from typing import Any

from src.services.energy_service import calculate_energy, update_battery
from src.services.environment_service import update_environment
from src.services.inventory_service import consume


# ---------------------------------------------------------------------------
# Module-level mutable state (shared across all routes)
# ---------------------------------------------------------------------------
S: dict[str, dict] = {}

_settings: dict[str, float] = {
    "vibWarn": 4.5,
    "vibCrit": 6.0,
    "batteryWarn": 30.0,
    "tempWarn": -35.0,
    "windWarn": 22.0,
}

last_tick: datetime = datetime.now()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def R(a: float, b: float) -> float:  # noqa: N802
    return a + random.random() * (b - a)


def cl(v: float, a: float, b: float) -> float:
    return min(b, max(a, v))


def r1(v: float) -> float:
    return round(v * 10) / 10


def day(n: float) -> str:
    """Return ISO date string n days from now (n may be negative)."""
    return (datetime.utcnow() + timedelta(days=n)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Energy balance
# ---------------------------------------------------------------------------
def calc(s: dict) -> dict:
    return calculate_energy(s)


# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------
def rate_of(s: dict, item: dict) -> float:
    if item["k"] == "fuel":
        return calc(s)["genOut"] * 0.3 * 24
    return item["rate"]


def days_of(s: dict, item: dict) -> float:
    r = rate_of(s, item)
    return item["stock"] / r if r > 0 else 999.0


def risk(s: dict, d: float) -> str:
    if d < s["resupplyIn"]:
        return "critical"
    if d < s["resupplyIn"] + 7:
        return "warning"
    return "ok"


def inv_out(s: dict) -> list[dict]:
    result = []
    for item in s["inv"]:
        d = days_of(s, item)
        pct = item["stock"] / item["cap"] * 100
        result.append(
            {
                "k": item["k"],
                "name": item["name"],
                "unit": item["unit"],
                "stock": round(item["stock"]),
                "cap": item["cap"],
                "pct": r1(pct),
                "rate": r1(rate_of(s, item)),
                "daysLeft": r1(d),
                "min": item["min"],
                "belowMin": pct < item["min"],
                "risk": risk(s, d),
            }
        )
    return result


def snap(s: dict) -> dict:
    """Snapshot of current operational metrics (used in before/after simulation)."""
    m = calc(s)
    d = days_of(s, s["inv"][0])
    battery_hours = None
    if m["deficit"] > 0:
        battery_hours = r1(s["battery"]["kwh"] * s["battery"]["pct"] / 100 / m["deficit"])
    return {
        "capacity": r1(m["cap"]),
        "demand": r1(m["demand"]),
        "deficit": r1(m["deficit"]),
        "batteryHours": battery_hours,
        "fuelDays": r1(d),
        "fuelGap": r1(d - s["resupplyIn"]),
        "resupplyIn": s["resupplyIn"],
    }


def env_now(s: dict) -> dict:
    return {k: r1(v) for k, v in s["env"].items()}


def chain_info(s: dict) -> list[dict]:
    m = calc(s)
    f = s["inv"][0]
    return [
        {"k": "Temperature", "v": f"{r1(s['env']['temp'])} °C"},
        {"k": "Heating demand", "v": f"{r1(m['heat'])} kW"},
        {"k": "Total demand", "v": f"{r1(m['demand'])} kW"},
        {"k": "Fuel burn", "v": f"{round(rate_of(s, f))} L/day"},
        {"k": "Fuel left", "v": f"{r1(days_of(s, f))} days"},
    ]


# ---------------------------------------------------------------------------
# tick() — called every 3 s to advance the simulation
# ---------------------------------------------------------------------------
def tick(s: dict) -> None:  # noqa: C901
    cfg = _settings
    e = s["env"]

    # Environment is a gradual simulated provider, not independent random samples.
    e = update_environment(s)

    m = calc(s)
    b = s["battery"]

    # One tick represents roughly 30 seconds of operational time.
    update_battery(s, m, interval_hours=1 / 120)
    consume(s, m, interval_hours=1 / 120)

    fuel = s["inv"][0]
    fd = days_of(s, fuel)

    # Per-asset readings and status
    for a in s["assets"]:
        rd: list[tuple] = []
        st = "normal"

        if a["type"] == "generator":
            load = (
                cl(m["genOut"], 0, m["capGen"]) / m["capGen"] * 100
                if a["online"] and m["capGen"] > 0
                else 0.0
            )
            if not a["online"]:
                a["vib"] = 0.0
            elif a.get("drift"):
                a["vib"] = min(9.0, a["vib"] + R(0.03, 0.1))
            else:
                a["vib"] = 2.2 + R(-0.2, 0.3)
            if a["online"]:
                a["hours"] += 1 / 120
            t = 62.0 + load * 0.3 + R(-1, 1) if a["online"] else -5.0
            rd = [
                ("Vibration", a["vib"], "mm/s"),
                ("Temperature", t, "°C"),
                ("Power output", a["cap"] * load / 100, "kW"),
                ("Load", load, "%"),
                ("Operating hours", a["hours"], "h"),
            ]
            if not a["online"]:
                st = "offline"
            elif a["vib"] > cfg["vibCrit"]:
                st = "critical"
            elif a["vib"] > cfg["vibWarn"] or t > 95:
                st = "warning"

        elif a["type"] == "battery":
            net = (
                -m["deficit"]
                if m["deficit"] > 0
                else min(20, m["cap"] - m["demand"]) * 0.5
            )
            rd = [
                ("Charge", b["pct"], "%"),
                ("Voltage", 48 + b["pct"] * 0.08 + R(-0.1, 0.1), "V"),
                ("Net flow", net, "kW"),
            ]
            if b["pct"] < 10:
                st = "critical"
            elif b["pct"] < cfg["batteryWarn"]:
                st = "warning"

        elif a["type"] == "heating":
            rd = [
                ("Heat output", m["heat"], "kW"),
                ("Supply temp", 55 + m["heat"] * 0.6, "°C"),
            ]
            st = "warning" if m["deficit"] > 0 else "normal"

        elif a["type"] == "water":
            w = s["inv"][4]
            p = w["stock"] / w["cap"] * 100
            pump_online = a["online"]
            s["waterStatus"] = "normal" if pump_online else "degraded"
            rd = [("Level", p, "%"), ("Flow", R(8, 12) if pump_online else 0, "L/min")]
            st = "warning" if p < w["min"] else "normal"

        elif a["type"] == "living":
            rd = [
                ("Indoor temp", 21 - min(8, m["deficit"] * 0.3), "°C"),
                ("Power draw", s["baseLoad"] * 0.3, "kW"),
            ]
            st = "warning" if m["deficit"] > 0 else "normal"

        elif a["type"] == "lab":
            rd = [
                ("Indoor temp", 20 - min(8, m["deficit"] * 0.3), "°C"),
                ("Power draw", s["baseLoad"] * 0.35, "kW"),
            ]
            st = "warning" if m["deficit"] > 0 else "normal"

        elif a["type"] == "comms":
            q = cl(92 - e["wind"] * 0.9 + R(-2, 2), 0, 100)
            rd = [
                ("Link quality", q, "%"),
                ("Latency", 500 + (100 - q) * 12 + R(-30, 30), "ms"),
            ]
            st = "warning" if q < 60 else "normal"

        elif a["type"] == "fuel":
            rd = [
                ("Level", fuel["stock"] / fuel["cap"] * 100, "%"),
                ("Days remaining", fd, "d"),
            ]
            r = risk(s, fd)
            st = "normal" if r == "ok" else r

        a["readings"] = [{"k": k, "v": r1(v), "u": u} for k, v, u in rd]
        a["status"] = st
        a["hist"] = (a["hist"] + [a["readings"][0]["v"]])[-30:]

    # Append to station history ring-buffer (last 40 entries)
    s["hist"] = (
        s["hist"]
        + [
            {
                "t": datetime.now().strftime("%H:%M:%S"),
                "gen": r1(m["output"]),
                "demand": r1(m["demand"]),
                "cap": r1(m["cap"]),
                "battery": r1(b["pct"]),
                "temp": r1(e["temp"]),
                "wind": r1(e["wind"]),
                "pressure": r1(e["pressure"]),
                "snow": r1(e["snow"]),
            }
        ]
    )[-40:]


# ---------------------------------------------------------------------------
# make_alerts() — rule-based alert generation
# ---------------------------------------------------------------------------
def make_alerts(s: dict) -> list[dict]:  # noqa: C901
    out: list[dict] = []
    m = calc(s)
    b = s["battery"]
    cfg = _settings

    def add(key, severity, title, source, asset_id, link, desc, impact, action, why):
        full_id = f"{s['id']}:{key}"
        s["seen"].setdefault(full_id, datetime.now().isoformat())
        out.append(
            {
                "id": full_id,
                "severity": severity,
                "title": title,
                "source": source,
                "assetId": asset_id,
                "link": link,
                "desc": desc,
                "impact": impact,
                "action": action,
                "why": why,
                "time": s["seen"][full_id],
                "acked": bool(s["acked"].get(full_id)),
            }
        )

    for a in s["assets"]:
        if a["status"] == "normal" or a["type"] in ("battery", "fuel"):
            continue
        sev = "warning" if a["status"] == "warning" else "critical"
        r0 = a["readings"][0] if a["readings"] else None

        if a["type"] == "generator":
            if not a["online"]:
                add(
                    f"{a['id']}-off", "critical", "Generator offline", a["name"],
                    a["id"], f"/twin?asset={a['id']}",
                    f"{a['name']} is not running.",
                    "Reduced generation capacity; higher load on remaining units.",
                    "Check fault logs and restart or isolate the unit.",
                    "Rule: asset status = offline.",
                )
            elif r0:
                add(
                    f"{a['id']}-vib", sev, "Abnormal vibration", a["name"],
                    a["id"], f"/twin?asset={a['id']}",
                    f"Vibration {r0['v']} mm/s vs baseline ~2.2 mm/s.",
                    "Reduced reliability of power generation.",
                    "Inspect the asset and review its operating parameters.",
                    f"Rule: vibration > {cfg['vibWarn']} mm/s (warning) or > {cfg['vibCrit']} mm/s (critical).",
                )
        elif r0:
            add(
                a["id"], sev, f"{a['name']} needs attention", a["name"],
                a["id"], f"/twin?asset={a['id']}",
                f"{r0['k']}: {r0['v']} {r0['u']}.",
                "Possible effect on station comfort or operations.",
                "Review the asset and linked systems.",
                "Rule: reading outside its normal operating range or linked to an energy deficit.",
            )

    if b["pct"] < cfg["batteryWarn"]:
        sev = "critical" if b["pct"] < 10 else "warning"
        add(
            "battery", sev, "Low battery reserve", "Battery Bank", "bat", "/energy",
            f"Battery at {r1(b['pct'])}%.",
            "Less buffer for generator faults.",
            "Reduce non-critical loads; check generation.",
            f"Rule: battery < {cfg['batteryWarn']}%.",
        )

    fd = days_of(s, s["inv"][0])
    if risk(s, fd) != "ok":
        add(
            "fuel", risk(s, fd), "Fuel may not last until resupply", "Logistics",
            "fuel", "/logistics",
            f"{r1(fd)} days of fuel at current burn; resupply in {s['resupplyIn']} days.",
            "Generators may stop before resupply.",
            "Reduce non-critical loads or request an earlier resupply.",
            "Forecast: days left = stock ÷ burn rate (burn grows as heating demand grows).",
        )

    pd = days_of(s, s["inv"][3])
    if pd < s["resupplyIn"]:
        add(
            "parts", "warning", "Spare parts running low", "Logistics",
            "fuel", "/logistics",
            f"{r1(pd)} days of spare parts at current usage.",
            "Repairs (e.g. generator bearings) may be delayed.",
            "Prioritise critical spares in the next resupply.",
            "Forecast: stock ÷ average usage < days to resupply.",
        )

    if m["deficit"] > 0:
        add(
            "deficit", "critical", "Generation shortfall", "Energy", "bat", "/energy",
            f"Demand exceeds capacity by {r1(m['deficit'])} kW.",
            "Battery discharging; critical loads at risk.",
            "Shed non-critical loads and restore generation.",
            "Rule: demand > available capacity.",
        )

    if s["env"]["temp"] < cfg["tempWarn"]:
        add(
            "cold", "warning", "Extreme cold", "Environment", None, "/environment",
            f"Temperature {r1(s['env']['temp'])} °C.",
            "Heating demand and fuel burn will rise.",
            "Review energy forecast.",
            f"Rule: temperature < {cfg['tempWarn']} °C.",
        )

    if s["env"]["wind"] > cfg["windWarn"]:
        add(
            "wind", "warning", "High winds", "Environment", "comms", "/environment",
            f"Wind {r1(s['env']['wind'])} m/s.",
            "Comms degradation and drifting snow.",
            "Limit outdoor work.",
            f"Rule: wind > {cfg['windWarn']} m/s.",
        )

    # Purge stale seen/acked entries
    current_ids = {a["id"] for a in out}
    for k in list(s["seen"].keys()):
        if k not in current_ids:
            del s["seen"][k]
            s["acked"].pop(k, None)

    rank = {"critical": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda a: rank.get(a["severity"], 2))


def station_status(s: dict) -> str:
    al = make_alerts(s)
    if any(a["severity"] == "critical" for a in al):
        return "Critical"
    if al:
        return "Attention"
    return "Operational"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
_ASSET_DEFS = [
    ("gen1",   "Generator 01",    "generator",  6,  4,  16,  9, ["bat"],                                  30),
    ("gen2",   "Generator 02",    "generator",  6,  16, 16,  9, ["bat"],                                  30),
    ("gen3",   "Generator 03",    "generator",  6,  28, 16,  9, ["bat"],                                  30),
    ("fuel",   "Fuel Tank Farm",  "fuel",       6,  41, 16,  9, ["gen1", "gen2", "gen3"],                  0),
    ("bat",    "Battery Bank",    "battery",    34,  4, 16, 10, ["heat", "living", "lab", "comms", "water"], 0),
    ("heat",   "Heating Plant",   "heating",    34, 20, 16, 10, [],                                        0),
    ("water",  "Water Plant",     "water",      34, 36, 16, 10, [],                                        0),
    ("living", "Living Module",   "living",     62,  4, 18, 12, [],                                        0),
    ("lab",    "Science Lab",     "lab",        62, 22, 18, 12, [],                                        0),
    ("comms",  "Comms Hub",       "comms",      62, 40, 18, 10, [],                                        0),
]

_STATION_PARAMS = {
    "maitri": {
        "t": -14, "w": 9,  "p": 985, "sn": 8,  "base": 36, "occupancy": 24,
        "solar": 6, "bat": 84, "res": 24, "fuel": 14000, "spare": 90, "cold": False,
    },
    "bharati": {
        "t": -18, "w": 12, "p": 975, "sn": 14, "base": 42, "occupancy": 31,
        "solar": 4, "bat": 63, "res": 20, "fuel": 9000,  "spare": 38, "cold": True,
    },
}


def _make_assets() -> list[dict]:
    return [
        {
            "id": key, "name": name, "type": atype,
            "x": x, "y": y, "w": w, "h": h, "links": links,
            "cap": cap, "online": True,
            "hours": round(R(1500, 9000)),
            "last": day(-R(20, 80)),
            "next": day(R(8, 60)),
            "vib": 2.2, "hist": [], "readings": [], "status": "normal",
        }
        for key, name, atype, x, y, w, h, links, cap in _ASSET_DEFS
    ]


def _make_inv(fuel_stock: float, spare_stock: float) -> list[dict]:
    return [
        {"k": "fuel",  "name": "Fuel (diesel)",      "unit": "L",     "stock": fuel_stock, "cap": 20000, "rate": 0,   "min": 25},
        {"k": "food",  "name": "Food",                "unit": "kg",    "stock": 1500,       "cap": 3000,  "rate": 24,  "min": 20},
        {"k": "med",   "name": "Medical supplies",    "unit": "units", "stock": 420,        "cap": 600,   "rate": 4,   "min": 25},
        {"k": "parts", "name": "Spare parts",         "unit": "units", "stock": spare_stock,"cap": 100,   "rate": 3.2, "min": 30},
        {"k": "water", "name": "Water reserve",       "unit": "L",     "stock": 52000,      "cap": 90000, "rate": 1500,"min": 20},
    ]


def _build_station(sid: str, params: dict) -> dict:
    return {
        "id": sid,
        "name": sid.capitalize(),
        "t": params["t"], "w": params["w"], "p": params["p"],
        "env": {
            "temp": params["t"], "wind": params["w"], "dir": 200,
            "pressure": params["p"], "snow": params["sn"], "vis": 9.0,
        },
        "assets": _make_assets(),
        "baseLoad": params["base"],
        "occupancy": params["occupancy"], "occupancyCapacity": 50,
        "solar": params["solar"],
        "capFactor": 1.0,
        "battery": {"kwh": 400, "pct": params["bat"]},
        "resupplyIn": params["res"],
        "inv": _make_inv(params["fuel"], params["spare"]),
        "hist": [],
        "cold": params["cold"],
        "acked": {},
        "seen": {},
        "nextTask": 3,
        "tasks": [
            {
                "id": 1, "assetId": "gen2",
                "title": "Vibration analysis & bearing inspection",
                "status": "Open", "due": day(3), "parts": "Bearing kit", "by": "system",
            },
            {
                "id": 2, "assetId": "comms",
                "title": "Antenna alignment check",
                "status": "Open", "due": day(9), "parts": "-", "by": "system",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Initialise / re-initialise the simulation
# ---------------------------------------------------------------------------
def init_simulation(
    settings: dict | None = None,
    asset_overrides: dict | None = None,
) -> None:
    """
    Build or rebuild the in-memory station state.

    Parameters
    ----------
    settings : optional dict with keys vibWarn, vibCrit, batteryWarn, tempWarn, windWarn
        When provided (loaded from DB on startup), overrides the defaults.
    asset_overrides : optional dict mapping (station_id, asset_key) → {hours, last, next}
        When provided (loaded from DB on startup), preserves persisted service dates.
    """
    global S, last_tick

    if settings:
        _settings.update(settings)

    for sid, params in _STATION_PARAMS.items():
        state = _build_station(sid, params)

        if asset_overrides:
            for a in state["assets"]:
                override = asset_overrides.get((sid, a["id"]))
                if override:
                    if override.get("hours"):
                        a["hours"] = override["hours"]
                    if override.get("last"):
                        a["last"] = override["last"]
                    if override.get("next"):
                        a["next"] = override["next"]

        S[sid] = state

    # Bharati Generator 02 has a known drifting vibration fault
    gen2 = next((a for a in S["bharati"]["assets"] if a["id"] == "gen2"), None)
    if gen2:
        gen2["drift"] = True
        gen2["vib"] = 3.4

    # Prime simulation with 30 ticks so the frontend doesn't see empty history
    for _ in range(30):
        for s in S.values():
            tick(s)

    last_tick = datetime.now()


# ---------------------------------------------------------------------------
# Background tick loop (started by app.py on_event('startup'))
# ---------------------------------------------------------------------------
async def tick_loop() -> None:
    global last_tick
    while True:
        for s in S.values():
            tick(s)
        last_tick = datetime.now()
        await asyncio.sleep(3)
