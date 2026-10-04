-- Phase 7 auditable logistics transaction metadata.
ALTER TABLE inventory_transactions ADD COLUMN station_id VARCHAR(50);
ALTER TABLE inventory_transactions ADD COLUMN previous_quantity FLOAT;
ALTER TABLE inventory_transactions ADD COLUMN transaction_type VARCHAR(50) NOT NULL DEFAULT 'ADJUSTMENT';
ALTER TABLE inventory_transactions ADD COLUMN source_type VARCHAR(50) NOT NULL DEFAULT 'SIMULATED';
CREATE INDEX IF NOT EXISTS ix_inventory_transactions_station ON inventory_transactions(station_id);
