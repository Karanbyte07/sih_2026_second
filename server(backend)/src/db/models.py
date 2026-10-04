"""
SQLAlchemy ORM Models — Phase 1 foundational entities.

Tables created here:
  users, user_station_access, stations, assets, system_settings, audit_log

Schema is designed for SQLite now and PostgreSQL compatibility later.
All datetimes are stored in UTC.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    JSON, ForeignKey, UniqueConstraint, Index, Text,
)
from sqlalchemy.orm import relationship

from src.db.database import Base


# ---------------------------------------------------------------------------
# Station
# ---------------------------------------------------------------------------
class Station(Base):
    __tablename__ = "stations"

    id = Column(String(50), primary_key=True)           # 'maitri', 'bharati'
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    established_year = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assets = relationship("Asset", back_populates="station", cascade="all, delete-orphan")
    settings = relationship("SystemSettings", back_populates="station")


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)            # admin | ops | maintenance | logistics
    password_hash = Column(String(255), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    station_access = relationship(
        "UserStationAccess", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="user")

    @property
    def stations(self) -> list[str]:
        """Returns station IDs this user can access."""
        return [usa.station_id for usa in self.station_access]


Index("ix_users_email", User.email)


# ---------------------------------------------------------------------------
# UserStationAccess  (junction table — many-to-many User ↔ Station)
# ---------------------------------------------------------------------------
class UserStationAccess(Base):
    __tablename__ = "user_station_access"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    station_id = Column(String(50), ForeignKey("stations.id"), primary_key=True)

    user = relationship("User", back_populates="station_access")
    station = relationship("Station")


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------
class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("station_id", "asset_key", name="uq_station_asset"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False)
    # asset_key = the frontend-facing id ('gen1', 'bat', 'comms', …)
    asset_key = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)   # generator | battery | heating | fuel | water | living | lab | comms
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    w = Column(Float, nullable=False)
    h = Column(Float, nullable=False)
    # links: JSON list of connected asset_keys, e.g. ["bat", "gen1"]
    links = Column(JSON, nullable=False, default=list)
    capacity_kw = Column(Float, default=0.0)
    operational_hours = Column(Integer, default=0)
    last_service_date = Column(String(20), nullable=True)   # ISO date string
    next_service_date = Column(String(20), nullable=True)
    online = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    station = relationship("Station", back_populates="assets")


# ---------------------------------------------------------------------------
# SystemSettings
# ---------------------------------------------------------------------------
class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # station_id = NULL means global / applies to all stations
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=True)
    vib_warn = Column(Float, default=4.5)
    vib_crit = Column(Float, default=6.0)
    battery_warn = Column(Float, default=30.0)
    temp_warn = Column(Float, default=-35.0)
    wind_warn = Column(Float, default=22.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    station = relationship("Station", back_populates="settings")


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_name = Column(String(255), nullable=False, default="system")   # denormalized for display
    action = Column(String(500), nullable=False)
    entity_type = Column(String(50), nullable=True)     # 'user', 'inventory', 'alert', …
    entity_id = Column(String(255), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True) # renamed to avoid clash with SQLAlchemy Base.metadata

    user = relationship("User", back_populates="audit_logs")


# ---------------------------------------------------------------------------
# AssetReading
# ---------------------------------------------------------------------------
class AssetReading(Base):
    __tablename__ = "asset_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    metric = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)
    source_type = Column(String(50), nullable=False, default="SIMULATED")

    asset = relationship("Asset")


Index("ix_asset_readings_asset_time", AssetReading.asset_id, AssetReading.timestamp)


# ---------------------------------------------------------------------------
# EnergySnapshot
# ---------------------------------------------------------------------------
class EnergySnapshot(Base):
    __tablename__ = "energy_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    generation_kw = Column(Float, nullable=False)
    demand_kw = Column(Float, nullable=False)
    capacity_kw = Column(Float, nullable=False)
    battery_pct = Column(Float, nullable=False)
    fuel_consumption_l = Column(Float, nullable=True)
    generator_load_pct = Column(Float, nullable=True)
    source_type = Column(String(50), nullable=False, default="SIMULATED")

    station = relationship("Station")


# ---------------------------------------------------------------------------
# EnvironmentReading
# ---------------------------------------------------------------------------
class EnvironmentReading(Base):
    __tablename__ = "environment_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    temperature = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    wind_direction = Column(Float, nullable=False)
    pressure = Column(Float, nullable=False)
    snow = Column(Float, nullable=False)
    visibility = Column(Float, nullable=False)
    source_type = Column(String(50), nullable=False, default="SIMULATED")

    station = relationship("Station")


# ---------------------------------------------------------------------------
# Inventory & InventoryTransaction
# ---------------------------------------------------------------------------
class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("station_id", "item_key", name="uq_station_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False)
    item_key = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=False)
    stock = Column(Float, nullable=False, default=0.0)
    capacity = Column(Float, nullable=False)
    daily_rate = Column(Float, nullable=False, default=0.0)
    min_pct = Column(Float, nullable=False, default=20.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    station = relationship("Station")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    quantity_change = Column(Float, nullable=False)
    resulting_quantity = Column(Float, nullable=False)
    reason = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)

    item = relationship("InventoryItem")


# ---------------------------------------------------------------------------
# ResupplySchedule
# ---------------------------------------------------------------------------
class ResupplySchedule(Base):
    __tablename__ = "resupply_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False, index=True)
    expected_date = Column(String(20), nullable=False)  # YYYY-MM-DD
    cargo_description = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="SCHEDULED") # SCHEDULED, IN_TRANSIT, ARRIVED
    notes = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=False, default="SIMULATED")

    station = relationship("Station")


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------
class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("station_id", "alert_key", "status", name="uq_station_alert_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False, index=True)
    alert_key = Column(String(255), nullable=False) # e.g., maitri:gen2-vib
    severity = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    source = Column(String(255), nullable=False)
    asset_id = Column(String(50), nullable=True)
    description = Column(Text, nullable=False)
    impact = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    why = Column(Text, nullable=False)
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    acked = Column(Boolean, nullable=False, default=False)
    acked_by = Column(String(255), nullable=True)
    acked_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE") # ACTIVE, RESOLVED

    station = relationship("Station")


# ---------------------------------------------------------------------------
# MaintenanceTask
# ---------------------------------------------------------------------------
class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False, index=True)
    asset_id = Column(String(50), nullable=True)
    title = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="Open") # Open, Completed
    due_date = Column(String(20), nullable=True) # YYYY-MM-DD
    parts = Column(String(255), nullable=True)
    created_by = Column(String(255), nullable=False, default="system")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    station = relationship("Station")
