-- Phase 5 normalized public environment observations and provider health.
CREATE TABLE IF NOT EXISTS environment_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id VARCHAR(50) NOT NULL REFERENCES stations(id),
    timestamp DATETIME NOT NULL,
    temperature FLOAT,
    wind_speed FLOAT,
    wind_direction FLOAT,
    pressure FLOAT,
    humidity FLOAT,
    visibility FLOAT,
    snow FLOAT,
    source_type VARCHAR(50) NOT NULL DEFAULT 'PUBLIC',
    source_name VARCHAR(255) NOT NULL,
    source_timestamp DATETIME NOT NULL,
    ingested_at DATETIME NOT NULL,
    raw_data JSON,
    UNIQUE(station_id, source_name, source_timestamp)
);
CREATE INDEX IF NOT EXISTS ix_environment_observations_station_time
    ON environment_observations(station_id, timestamp);
CREATE TABLE IF NOT EXISTS environment_provider_status (
    provider VARCHAR(100) PRIMARY KEY,
    status VARCHAR(30) NOT NULL DEFAULT 'UNAVAILABLE',
    last_successful_fetch DATETIME,
    last_source_timestamp DATETIME,
    last_error TEXT,
    updated_at DATETIME NOT NULL
);
