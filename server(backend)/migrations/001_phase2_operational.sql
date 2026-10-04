-- Phase 2 operational persistence migration for SQLite.
-- The application startup also uses SQLAlchemy metadata for local development.
CREATE TABLE IF NOT EXISTS asset_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    timestamp DATETIME NOT NULL,
    metric VARCHAR(50) NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(20),
    source_type VARCHAR(50) NOT NULL DEFAULT 'SIMULATED'
);
CREATE INDEX IF NOT EXISTS ix_asset_readings_asset_time ON asset_readings(asset_id, timestamp);
CREATE TABLE IF NOT EXISTS energy_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id VARCHAR(50) NOT NULL REFERENCES stations(id),
    timestamp DATETIME NOT NULL,
    generation_kw FLOAT NOT NULL,
    demand_kw FLOAT NOT NULL,
    capacity_kw FLOAT NOT NULL,
    battery_pct FLOAT NOT NULL,
    fuel_consumption_l FLOAT,
    generator_load_pct FLOAT,
    source_type VARCHAR(50) NOT NULL DEFAULT 'SIMULATED'
);
CREATE INDEX IF NOT EXISTS ix_energy_snapshots_station_time ON energy_snapshots(station_id, timestamp);
CREATE TABLE IF NOT EXISTS environment_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id VARCHAR(50) NOT NULL REFERENCES stations(id),
    timestamp DATETIME NOT NULL,
    temperature FLOAT NOT NULL,
    wind_speed FLOAT NOT NULL,
    wind_direction FLOAT NOT NULL,
    pressure FLOAT NOT NULL,
    snow FLOAT NOT NULL,
    visibility FLOAT NOT NULL,
    source_type VARCHAR(50) NOT NULL DEFAULT 'SIMULATED'
);
CREATE INDEX IF NOT EXISTS ix_environment_readings_station_time ON environment_readings(station_id, timestamp);
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id VARCHAR(50) NOT NULL REFERENCES stations(id),
    item_key VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    stock FLOAT NOT NULL DEFAULT 0,
    capacity FLOAT NOT NULL,
    daily_rate FLOAT NOT NULL DEFAULT 0,
    min_pct FLOAT NOT NULL DEFAULT 20,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE(station_id, item_key)
);
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES inventory_items(id),
    timestamp DATETIME NOT NULL,
    quantity_change FLOAT NOT NULL,
    resulting_quantity FLOAT NOT NULL,
    reason VARCHAR(255),
    user_name VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS resupply_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id VARCHAR(50) NOT NULL REFERENCES stations(id),
    expected_date VARCHAR(20) NOT NULL,
    cargo_description VARCHAR(500) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'SCHEDULED',
    notes TEXT,
    source_type VARCHAR(50) NOT NULL DEFAULT 'SIMULATED'
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id VARCHAR(50) NOT NULL REFERENCES stations(id),
    alert_key VARCHAR(255) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL,
    asset_id VARCHAR(50),
    description TEXT NOT NULL,
    impact TEXT NOT NULL,
    action TEXT NOT NULL,
    why TEXT NOT NULL,
    first_seen DATETIME NOT NULL,
    acked BOOLEAN NOT NULL DEFAULT 0,
    acked_by VARCHAR(255),
    acked_at DATETIME,
    resolved_at DATETIME,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(station_id, alert_key, status)
);
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id VARCHAR(50) NOT NULL REFERENCES stations(id),
    asset_id VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Open',
    due_date VARCHAR(20),
    parts VARCHAR(255),
    created_by VARCHAR(255) NOT NULL DEFAULT 'system',
    created_at DATETIME NOT NULL,
    completed_at DATETIME
);
CREATE INDEX IF NOT EXISTS ix_maintenance_tasks_station ON maintenance_tasks(station_id);
