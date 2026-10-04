"""SQLAlchemy engine, session factory, and declarative Base."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import inspect, text

from src.config.settings import get_settings

_settings = get_settings()

_connect_args = {}
if _settings.DATABASE_URL.startswith("sqlite"):
    # Required for SQLite to work correctly with FastAPI's multi-threaded I/O
    _connect_args = {"check_same_thread": False}

engine = create_engine(_settings.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session, closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_energy_schema() -> None:
    """Apply the small Phase 6 SQLite compatibility upgrade when services run directly."""
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("energy_snapshots")}
    required = {
        "base_load_kw": "FLOAT", "heating_load_kw": "FLOAT", "water_load_kw": "FLOAT",
        "lab_load_kw": "FLOAT", "communications_load_kw": "FLOAT", "lighting_load_kw": "FLOAT",
        "other_load_kw": "FLOAT", "energy_status": "VARCHAR(30)",
    }
    with engine.begin() as connection:
        for column, column_type in required.items():
            if column not in columns:
                connection.execute(text(f"ALTER TABLE energy_snapshots ADD COLUMN {column} {column_type}"))
