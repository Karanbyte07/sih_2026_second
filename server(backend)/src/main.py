"""
Main application entry point — Phase 1.

Hooks up routes, configures CORS, handles DB initialisation
and starts the async simulation tick loop.
"""
import asyncio
import os
import time
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from sqlalchemy import inspect, text
from src.db.database import engine, Base, SessionLocal, ensure_logistics_schema
from src.config.settings import get_settings
from src.db.models import Station, Asset, SystemSettings
from src.routes import auth_routes, station_routes
from src.services.operational_service import ensure_operational_seed, load_inventory, persist_station_snapshot, sync_alerts
from src.services.environment_ingestion_service import PublicDataIngestionService
from src.services.public_environment_provider import PublicEnvironmentProvider
import src.utils.simulation as sim


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist (Phase 1 simplistic migration)
    Base.metadata.create_all(bind=engine)
    ensure_logistics_schema()
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(engine).get_columns("energy_snapshots")}
        if "fuel_consumption_l" not in columns:
            connection.execute(text("ALTER TABLE energy_snapshots ADD COLUMN fuel_consumption_l FLOAT"))
        if "generator_load_pct" not in columns:
            connection.execute(text("ALTER TABLE energy_snapshots ADD COLUMN generator_load_pct FLOAT"))
        energy_columns = {
            "base_load_kw": "FLOAT", "heating_load_kw": "FLOAT", "water_load_kw": "FLOAT",
            "lab_load_kw": "FLOAT", "communications_load_kw": "FLOAT", "lighting_load_kw": "FLOAT",
            "other_load_kw": "FLOAT", "energy_status": "VARCHAR(30)",
        }
        for column, column_type in energy_columns.items():
            if column not in columns:
                connection.execute(text(f"ALTER TABLE energy_snapshots ADD COLUMN {column} {column_type}"))
        alert_columns = {column["name"] for column in inspect(engine).get_columns("alerts")}
        if "resolved_at" not in alert_columns:
            connection.execute(text("ALTER TABLE alerts ADD COLUMN resolved_at DATETIME"))

    # Load persistent settings and asset states from SQLite to seed the in-memory simulation
    with SessionLocal() as db:
        ensure_operational_seed(db)
        # Load settings for Maitri (assuming global or first station)
        settings = db.query(SystemSettings).filter(SystemSettings.station_id == "maitri").first()
        settings_dict = None
        if settings:
            settings_dict = {
                "vibWarn": settings.vib_warn,
                "vibCrit": settings.vib_crit,
                "batteryWarn": settings.battery_warn,
                "tempWarn": settings.temp_warn,
                "windWarn": settings.wind_warn,
            }

        # Load persisted asset states (hours, last service, next service)
        assets = db.query(Asset).all()
        asset_overrides = {}
        for a in assets:
            asset_overrides[(a.station_id, a.asset_key)] = {
                "hours": a.operational_hours,
                "last": a.last_service_date,
                "next": a.next_service_date,
            }
            inventory_overrides = load_inventory(db)

    # Initialize the simulation with DB overrides
    sim.init_simulation(settings_dict, asset_overrides)
    for station in sim.S.values():
        for item in station["inv"]:
            override = inventory_overrides.get((station["id"], item["k"]))
            if override is not None:
                item["stock"] = override

    # Persist the primed state so charts have durable history immediately.
    with SessionLocal() as db:
        from src.db.models import EnergySnapshot
        for station in sim.S.values():
            if not db.query(EnergySnapshot).filter(EnergySnapshot.station_id == station["id"]).first():
                # A compact deterministic history makes charts useful on first boot.
                for minutes_ago in range(24 * 60, -1, -10):
                    persist_station_snapshot(db, station, datetime.utcnow() - timedelta(minutes=minutes_ago))

    settings = get_settings()
    public_task = None
    if settings.PUBLIC_ENVIRONMENT_ENABLED and settings.PUBLIC_ENVIRONMENT_URL:
        public_task = asyncio.create_task(public_environment_loop(settings))

    # Start the simulator loop in the background
    task = asyncio.create_task(persist_tick_loop())
    yield
    # Shutdown
    task.cancel()
    if public_task:
        public_task.cancel()


async def public_environment_loop(settings):
    provider = PublicEnvironmentProvider(settings.PUBLIC_ENVIRONMENT_URL, settings.PUBLIC_ENVIRONMENT_TIMEOUT_SECONDS)
    while True:
        with SessionLocal() as db:
            ingestion = PublicDataIngestionService(db)
            try:
                observations = await asyncio.to_thread(provider.fetch)
                ingestion.ingest(observations)
            except Exception as error:
                ingestion.record_failure(error)
        await asyncio.sleep(settings.PUBLIC_ENVIRONMENT_REFRESH_SECONDS)


async def persist_tick_loop():
    """Advance the simulator and persist each observation batch."""
    interval = float(os.getenv("SIMULATION_INTERVAL_SECONDS", "3"))
    persistence_interval = float(os.getenv("PERSISTENCE_INTERVAL_SECONDS", "15"))
    last_persisted = 0.0
    while True:
        for station in sim.S.values():
            with SessionLocal() as inventory_db:
                current_inventory = load_inventory(inventory_db)
            for item in station["inv"]:
                persisted_stock = current_inventory.get((station["id"], item["k"]))
                if persisted_stock is not None:
                    item["stock"] = persisted_stock
            sim.tick(station)
        sim.last_tick = datetime.now()
        now = time.monotonic()
        if now - last_persisted >= persistence_interval:
            with SessionLocal() as db:
                for station in sim.S.values():
                    persist_station_snapshot(db, station)
                    sync_alerts(db, station)
            last_persisted = now
        await asyncio.sleep(interval)


app = FastAPI(
    title="Antarctic Twin Backend",
    version="1.0.0",
    description="Phase 5: Public environment provider and Digital Twin integration",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exactly (e.g., ["http://localhost:5173"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(station_routes.router)
app.include_router(station_routes.api_router)

# Health endpoint (root)
@app.get("/")
async def root():
    return {"status": "ok", "message": "Antarctic Twin API running. Go to /api/health"}
